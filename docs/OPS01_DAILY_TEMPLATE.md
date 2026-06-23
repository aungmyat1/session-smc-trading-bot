# OPS01_DAILY_TEMPLATE.md
# OPS-01 — Daily Report Template
# Copy this file to: docs/OPS01_DAY{N}_REPORT.md

---

## Date: ___________  (Day N of 7)

---

## Uptime

| Metric | Value |
|---|---|
| Start time | |
| End time | |
| Uptime % | |
| Planned downtime | |
| Unplanned downtime | |

---

## Connectivity

| Metric | Value |
|---|---|
| Reconnect count | |
| Longest disconnect (min) | |
| MetaAPI status EOD | CONNECTED / DISCONNECTED |

---

## Errors

| Metric | Value |
|---|---|
| ERROR lines in bot.log | |
| Fatal exceptions | |
| Uncaught exceptions | |
| Telegram delivery failures | |

```bash
grep ' ERROR ' logs/bot.log | grep $(date +%Y-%m-%d)
```

---

## Signals & Orders

| Metric | Value |
|---|---|
| Signals generated | |
| Orders submitted (DRY_RUN) | |
| Orders rejected | |
| Rejection reasons | |
| Duplicate signals caught | |
| Open position EOD | |

```bash
grep SIGNAL_CREATED logs/trades.jsonl | wc -l
grep ORDER_SUBMITTED logs/trades.jsonl | wc -l
grep ORDER_REJECTED logs/trades.jsonl | wc -l
```

---

## Heartbeats

| Metric | Value |
|---|---|
| Expected (every 5 min, 24h) | 288 |
| Actual received | |
| Gaps > 10 min | |

```bash
grep HEARTBEAT logs/bot.log | grep $(date +%Y-%m-%d) | wc -l
```

---

## Memory

| Metric | Value |
|---|---|
| Bot RSS at start (MB) | |
| Bot RSS at end (MB) | |
| System available (MB) | |
| Memory leak suspected | Yes / No |

```bash
python3 scripts/health_check.py | grep memory
```

---

## Disk

| Metric | Value |
|---|---|
| bot.log size (KB) | |
| trades.jsonl size (KB) | |
| Disk free % | |
| Log rotation fired | Yes / No |

```bash
ls -lh logs/
df -h /
```

---

## Notes

_Free text: unusual events, spread spikes, Telegram gaps, VPS issues._

---

## Health Check Output

```
# paste output of: python3 scripts/health_check.py
```

---

## Day Verdict

```
[ ] All heartbeats received
[ ] No critical errors
[ ] No duplicate orders
[ ] LIVE_TRADING=false confirmed
[ ] Memory within limits
[ ] Disk within limits
[ ] Logging valid

Day verdict: [ ] PASS  [ ] FAIL
```

---

*OPS-01 | Daily Report | Session SMC Trading Bot | ST-A2*
