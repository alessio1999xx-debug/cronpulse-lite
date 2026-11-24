# cronpulse-lite: cron job monitoring with failure alerts in one Python file

**Cron jobs fail silently. This tells you when they do.**

A single-file, zero-dependency Python wrapper that helps with cron job monitoring: it runs your command, records the exit code, duration and the last lines of output, kills it if it hangs, and posts an alert to Slack, Discord or any webhook when it fails.

- One file, Python 3.9+ standard library only. Nothing to `pip install`.
- Your job's exit code is passed through, so existing cron/CI logic keeps working.
- Runs are kept in a local JSONL log you can `grep` or `jq`.

Need missed-job detection, a small dashboard, or Telegram alerts? That is the full [CronPulse CLI](https://py-forge.com/products/cronpulse-cli?utm_source=github&utm_medium=readme&utm_campaign=cronpulse-lite) (one-time payment, yours to keep, no subscription). A table later in this README lists what lite does and what the paid tool adds. Or get every PyForge tool, current and future, with the [All-Access Pass](https://py-forge.com/pass?utm_source=github&utm_medium=readme&utm_campaign=cronpulse-lite) ($99, one payment).

## Install

```bash
curl -fsSLO https://raw.githubusercontent.com/alessio1999xx-debug/cronpulse-lite/main/cronpulse_lite.py
chmod +x cronpulse_lite.py
./cronpulse_lite.py --help
```

## Get a Slack or Discord alert when a cron job fails

```bash
export CRONPULSE_LITE_WEBHOOK=https://hooks.slack.com/services/XXX/YYY/ZZZ

# wrap a job: alert if it exits non-zero or runs longer than 10 minutes
./cronpulse_lite.py run --name db-backup --timeout 10m -- /opt/scripts/backup.sh

# last run of every job (exits 1 if any last run failed, handy for monitoring)
./cronpulse_lite.py status

# recent runs of one job
./cronpulse_lite.py history db-backup
```

Example output, recorded 25 Nov 2026 (Europe/Rome) on a throwaway failing command (no webhook was set, so nothing was posted). Exit code `1`. Duration is from that run.

```text
$ python3 cronpulse_lite.py --log ./cronpulse.jsonl run --name backup --timeout 5 -- /bin/sh -c 'echo backup starting; echo permission denied >&2; exit 1'
backup starting
permission denied
cronpulse-lite: backup failed (exit 1, 0.001s)

$ python3 cronpulse_lite.py --log ./cronpulse.jsonl status
JOB                      STATUS   EXIT  DURATION  LAST RUN
backup                   failed      1    0.001s  2026-11-25T00:23:00+0100
```

Crontab:

```cron
0 3 * * *  /usr/local/bin/cronpulse_lite.py run --name db-backup --timeout 1h -- /opt/scripts/backup.sh
```

### Cron job timeout: kill hung jobs

| Situation | What happens |
|---|---|
| Job exits non-zero | logged as `failed`, alert sent, same exit code returned |
| Job hangs past `--timeout` | process group killed, logged as `timeout`, alert sent, exit 124 |
| Command not found | logged as `failed`, exit 127 |
| Job succeeds | logged as `ok`, no alert |

Webhook payloads: Slack (`text`), Discord (`content`), anything else gets the JSON run record (`job`, `status`, `exit_code`, `duration`, `output`, `host`).

Log location: `~/.cronpulse-lite.jsonl` (override with `--log` or `CRONPULSE_LITE_LOG`).

## Detect missed cron jobs: cronpulse-lite vs CronPulse CLI

cronpulse-lite catches jobs that **fail or hang**. It cannot notice a job that **never started** (cron daemon down, server rebooted, crontab line deleted), because nothing runs to report it.

| Capability | Lite (free) | Paid CronPulse CLI |
| --- | --- | --- |
| Wrap a job (`run`): exit code, duration, output tail, timeout | Yes | Yes, plus peak memory (`--max-memory-mb`) |
| Local history | JSONL log, `status` and `history` | SQLite history, JSON or Markdown reports |
| Alert when a run fails or hangs | Slack, Discord or a generic webhook | Slack, Discord, Telegram or a webhook |
| Missed check-in (the job never started) | No | Yes (`add` registers the expected interval; a missing check-in triggers an alert) |
| Heartbeat endpoint and HTML dashboard | No | Yes (`ping` / `serve`) |

One-time payment, yours to keep. No subscription. [Get CronPulse CLI →](https://py-forge.com/products/cronpulse-cli?utm_source=github&utm_medium=readme&utm_campaign=cronpulse-lite). Or get every PyForge tool, current and future, with the [All-Access Pass](https://py-forge.com/pass?utm_source=github&utm_medium=readme&utm_campaign=cronpulse-lite) ($99, one payment).

More small self-hosted Python tools: [py-forge.com](https://py-forge.com/?utm_source=github&utm_medium=readme&utm_campaign=cronpulse-lite)

## Tests

```bash
python3 test_cronpulse_lite.py
```

## More free tools from the same author

- [agentconfig-audit-lite](https://github.com/alessio1999xx-debug/agentconfig-audit-lite) — Audit MCP config for secrets: plaintext tokens and unpinned npx/uvx servers in `.mcp.json` and `CLAUDE.md`.
- [agenttrail-scrub-lite](https://github.com/alessio1999xx-debug/agenttrail-scrub-lite) — Claude Code secret scanner: find API keys and tokens leaked in AI agent transcripts.
- [depcooldown-lite](https://github.com/alessio1999xx-debug/depcooldown-lite) — Dependency cooldown check: fail CI when a pinned PyPI or npm package is newer than N days.
- [homelab-doctor-lite](https://github.com/alessio1999xx-debug/homelab-doctor-lite) — Read-only homelab health check: stale images, exposed ports, expiring certs, silent cron, disk.
- [imagenudge-lite](https://github.com/alessio1999xx-debug/imagenudge-lite) — Docker image update checker: find running containers with a newer image (digest or tag).
- [pthguard-lite](https://github.com/alessio1999xx-debug/pthguard-lite) — Scan Python site-packages for malicious `.pth` files and startup backdoors.
- [pulseping-lite](https://github.com/alessio1999xx-debug/pulseping-lite) — Check SSL certificate expiry and URL/port uptime from cron.
- [secenv-lite](https://github.com/alessio1999xx-debug/secenv-lite) — Find `.env` files committed to git or missing from `.gitignore`, plus obvious API keys inside.

## License

MIT (this lite version). The full CronPulse CLI is sold separately under its own license.
