# cronpulse-lite: cron job monitoring with failure alerts in one Python file

**Cron jobs fail silently. This tells you when they do.**

A single-file, zero-dependency Python wrapper that helps with cron job monitoring: it runs your command, records the exit code, duration and the last lines of output, kills it if it hangs, and posts an alert to Slack, Discord or any webhook when it fails.

- One file, Python 3.8+ standard library only. Nothing to `pip install`.
- Your job's exit code is passed through, so existing cron/CI logic keeps working.
- Runs are kept in a local JSONL log you can `grep` or `jq`.

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

For that, the full **[CronPulse CLI](https://py-forge.com/products/cronpulse-cli?utm_source=github&utm_medium=readme&utm_campaign=cronpulse-lite)** adds:

- missed check-in detection (`--every 1d --grace 30m`) for jobs that silently stop running
- a self-hosted heartbeat server (`curl .../ping/<job>`) for containers and other machines, plus an HTML dashboard
- Slack, Discord, Telegram and generic webhooks, with one alert per failure streak and a recovery alert
- overrun and peak-memory limits, SQLite history, JSON/Markdown reports
- still a single file using only the standard library

One-time payment, yours to keep. No subscription. [Get CronPulse CLI →](https://py-forge.com/products/cronpulse-cli?utm_source=github&utm_medium=readme&utm_campaign=cronpulse-lite)

More small self-hosted Python tools: [py-forge.com](https://py-forge.com/?utm_source=github&utm_medium=readme&utm_campaign=cronpulse-lite)

## Tests

```bash
python3 test_cronpulse_lite.py
```

## License

MIT (this lite version). The full CronPulse CLI is sold separately under its own license.
