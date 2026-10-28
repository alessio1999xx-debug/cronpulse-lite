import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

import cronpulse_lite as cp

PY = sys.executable


class Hook(BaseHTTPRequestHandler):
    received = []

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        Hook.received.append(json.loads(body))
        self.send_response(204)
        self.end_headers()

    def log_message(self, *a):
        pass


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.log = os.path.join(self.tmp.name, "runs.jsonl")
        Hook.received = []

    def tearDown(self):
        self.tmp.cleanup()

    def test_parse_duration(self):
        self.assertEqual(cp.parse_duration("90"), 90)
        self.assertEqual(cp.parse_duration("15m"), 900)
        self.assertEqual(cp.parse_duration("2h"), 7200)
        self.assertEqual(cp.parse_duration("1d"), 86400)
        self.assertIsNone(cp.parse_duration(None))
        with self.assertRaises(Exception):
            cp.parse_duration("abc")

    def test_valid_name(self):
        self.assertEqual(cp.valid_name("db-backup.v2"), "db-backup.v2")
        with self.assertRaises(Exception):
            cp.valid_name("bad name;rm")

    def test_success_is_logged_and_exit_code_passed(self):
        rc = cp.main(["--log", self.log, "run", "--name", "ok", "--", PY, "-c", "print('hello')"])
        self.assertEqual(rc, 0)
        rec = cp.read_log(self.log)[-1]
        self.assertEqual(rec["status"], "ok")
        self.assertIn("hello", rec["output"])

    def test_failure_passes_exit_code(self):
        rc = cp.main(["--log", self.log, "run", "--name", "bad", "--", PY, "-c", "import sys; sys.exit(3)"])
        self.assertEqual(rc, 3)
        self.assertEqual(cp.read_log(self.log)[-1]["status"], "failed")

    def test_timeout_kills_job(self):
        rc = cp.main(["--log", self.log, "run", "--name", "slow", "--timeout", "1", "--",
                      PY, "-c", "import time; time.sleep(30)"])
        self.assertEqual(rc, 124)
        rec = cp.read_log(self.log)[-1]
        self.assertEqual(rec["status"], "timeout")
        self.assertLess(rec["duration"], 15)

    def test_missing_command(self):
        rc = cp.main(["--log", self.log, "run", "--name", "x", "--", "/nonexistent/binary-xyz"])
        self.assertEqual(rc, 127)

    def test_webhook_alert_only_on_failure(self):
        srv = HTTPServer(("127.0.0.1", 0), Hook)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{srv.server_address[1]}/hook"
        try:
            cp.main(["--log", self.log, "run", "--name", "ok", "--webhook", url, "--", PY, "-c", "pass"])
            self.assertEqual(Hook.received, [])
            cp.main(["--log", self.log, "run", "--name", "bad", "--webhook", url, "--",
                     PY, "-c", "print('boom'); raise SystemExit(1)"])
            self.assertEqual(len(Hook.received), 1)
            self.assertEqual(Hook.received[0]["job"], "bad")
            self.assertIn("boom", Hook.received[0]["output"])
        finally:
            srv.shutdown()

    def test_slack_and_discord_payload_shapes(self):
        rec = {"job": "j", "status": "failed", "host": "h", "exit_code": 1, "duration": 1.0, "output": "x"}
        self.assertIn("text", cp.build_payload("https://hooks.slack.com/services/a", rec))
        self.assertIn("content", cp.build_payload("https://discord.com/api/webhooks/a", rec))

    def test_status_exit_code(self):
        cp.main(["--log", self.log, "run", "--name", "a", "--", PY, "-c", "pass"])
        self.assertEqual(cp.main(["--log", self.log, "status"]), 0)
        cp.main(["--log", self.log, "run", "--name", "b", "--", PY, "-c", "raise SystemExit(2)"])
        self.assertEqual(cp.main(["--log", self.log, "status"]), 1)
        self.assertEqual(cp.main(["--log", self.log, "history", "b"]), 0)


if __name__ == "__main__":
    unittest.main()
