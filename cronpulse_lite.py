#!/usr/bin/env python3
"""cronpulse-lite: wrap a cron job, record how it ran, and alert a webhook when it fails.

Single file, Python 3.8+ standard library only.

    cronpulse_lite.py run --name backup --timeout 10m --webhook "$URL" -- ./backup.sh
    cronpulse_lite.py status
    cronpulse_lite.py history backup

Full version (heartbeat server, dashboard, missed-run detection, Slack/Discord/Telegram,
memory limits, recovery alerts, reports): https://py-forge.com/products/cronpulse-cli?utm_source=github&utm_medium=code&utm_campaign=cronpulse-lite
"""
from __future__ import annotations

import argparse
import json
import os
import re
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from collections import deque
from typing import List, Optional

__version__ = "0.1.0"

DEFAULT_LOG = os.environ.get("CRONPULSE_LITE_LOG", os.path.join(os.path.expanduser("~"), ".cronpulse-lite.jsonl"))
TAIL_LINES = 20
_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def parse_duration(value: Optional[str]) -> Optional[int]:
    """'90' / '90s' / '15m' / '2h' / '1d' -> seconds."""
    if value is None or value == "":
        return None
    m = re.fullmatch(r"\s*(\d+)\s*([smhd]?)\s*", str(value).lower())
    if not m:
        raise argparse.ArgumentTypeError(f"invalid duration {value!r} (examples: 90s, 15m, 2h, 1d)")
    return int(m.group(1)) * _UNITS[m.group(2) or "s"]


def valid_name(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", name):
        raise argparse.ArgumentTypeError(f"invalid job name {name!r}: use letters, digits, '.', '_' or '-'")
    return name


def run_job(command: List[str], timeout: Optional[int] = None, echo: bool = True) -> dict:
    """Run a command, stream its output, return exit code, duration, status and the output tail."""
    tail: deque = deque(maxlen=TAIL_LINES)
    start = time.time()
    kwargs = {"start_new_session": True} if os.name == "posix" else {}  # timeout kills the whole group
    try:
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, errors="replace", **kwargs)
    except OSError as exc:
        return {"status": "failed", "exit_code": 127, "duration": 0.0, "output": f"cannot start: {exc}"}

    def pump() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.rstrip("\n")
            tail.append(line)
            if echo:
                print(line, flush=True)

    reader = threading.Thread(target=pump, daemon=True)
    reader.start()
    timed_out = False
    try:
        proc.wait(timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill(proc)
    reader.join(2)

    duration = round(time.time() - start, 3)
    code = proc.returncode if proc.returncode is not None else -9
    status = "timeout" if timed_out else ("ok" if code == 0 else "failed")
    return {"status": status, "exit_code": code, "duration": duration, "output": "\n".join(tail)}


def _kill(proc: subprocess.Popen) -> None:
    try:
        if os.name == "posix":
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
        else:
            proc.kill()
        proc.wait(5)
    except (ProcessLookupError, subprocess.TimeoutExpired, OSError):
        pass


def append_log(path: str, record: dict) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_log(path: str) -> List[dict]:
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return out


def build_payload(url: str, record: dict) -> dict:
    text = (f"cronpulse-lite: job '{record['job']}' {record['status'].upper()} on {record['host']} "
            f"(exit {record['exit_code']}, {record['duration']}s)")
    if "hooks.slack.com" in url:
        return {"text": text + ("\n```" + record["output"][-1500:] + "```" if record["output"] else "")}
    if "discord.com/api/webhooks" in url or "discordapp.com/api/webhooks" in url:
        return {"content": (text + "\n" + record["output"][-1500:])[:1900]}
    return dict(record, text=text)


def send_alert(url: str, record: dict, timeout: float = 10.0) -> bool:
    data = json.dumps(build_payload(url, record)).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json",
                                                          "User-Agent": f"cronpulse-lite/{__version__}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except Exception as exc:  # alerting must never break the job's own exit code
        print(f"cronpulse-lite: alert failed: {exc}", file=sys.stderr)
        return False


def cmd_run(args: argparse.Namespace) -> int:
    command = args.cmd[1:] if args.cmd and args.cmd[0] == "--" else args.cmd
    if not command:
        print("cronpulse-lite: missing command, use: run --name JOB -- command [args]", file=sys.stderr)
        return 2
    result = run_job(command, args.timeout)
    record = {"job": args.name, "host": socket.gethostname(), "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
              "command": " ".join(command), **result}
    append_log(args.log, record)
    if result["status"] != "ok" and args.webhook:
        send_alert(args.webhook, record)
    if result["status"] != "ok":
        print(f"cronpulse-lite: {args.name} {result['status']} (exit {result['exit_code']}, {result['duration']}s)",
              file=sys.stderr)
    return 124 if result["status"] == "timeout" else result["exit_code"]


def cmd_status(args: argparse.Namespace) -> int:
    last = {}
    for rec in read_log(args.log):
        last[rec.get("job")] = rec
    if not last:
        print("no runs recorded yet")
        return 0
    print(f"{'JOB':<24} {'STATUS':<8} {'EXIT':>4} {'DURATION':>9}  LAST RUN")
    for job, rec in sorted(last.items()):
        print(f"{job:<24} {rec['status']:<8} {rec['exit_code']:>4} {rec['duration']:>8}s  {rec['started']}")
    return 1 if any(r["status"] != "ok" for r in last.values()) else 0


def cmd_history(args: argparse.Namespace) -> int:
    runs = [r for r in read_log(args.log) if r.get("job") == args.name][-args.limit:]
    for rec in runs:
        print(f"{rec['started']}  {rec['status']:<8} exit={rec['exit_code']} {rec['duration']}s")
    if not runs:
        print(f"no runs for {args.name}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cronpulse-lite",
                                description="Wrap a cron job, log how it ran, alert a webhook when it fails or hangs.",
                                epilog="Full version: https://py-forge.com/products/cronpulse-cli?utm_source=github&utm_medium=cli&utm_campaign=cronpulse-lite")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("--log", default=DEFAULT_LOG, help=f"JSONL run log (default {DEFAULT_LOG})")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("run", help="run a command and record exit code, duration and output tail")
    sp.add_argument("--name", required=True, type=valid_name, help="job name")
    sp.add_argument("--timeout", type=parse_duration, help="kill the job after this long (e.g. 10m)")
    sp.add_argument("--webhook", default=os.environ.get("CRONPULSE_LITE_WEBHOOK"),
                    help="Slack, Discord or generic JSON webhook (env CRONPULSE_LITE_WEBHOOK)")
    sp.add_argument("cmd", nargs=argparse.REMAINDER, help="-- command [args...]")
    sp.set_defaults(func=cmd_run)

    sp = sub.add_parser("status", help="last run of every job (exit 1 if any last run failed)")
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("history", help="recent runs of one job")
    sp.add_argument("name", type=valid_name)
    sp.add_argument("--limit", type=int, default=20)
    sp.set_defaults(func=cmd_history)
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
