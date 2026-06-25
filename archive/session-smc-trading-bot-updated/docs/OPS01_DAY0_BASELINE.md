# OPS01_DAY0_BASELINE.md
# OPS-01A — Day 0 Baseline Snapshot
# Captured: 2026-06-21T18:27 UTC

---

## Verdict

### ✅ Bot started — Day-0 baseline captured

---

## Process State

| Field | Value |
|---|---|
| Start command | `tmux new-session -d -s bot 'python3 bot.py 2>&1 | tee logs/bot.log'` |
| tmux session | `bot` — running |
| bot PID | 205435 |
| Start timestamp | 2026-06-21T18:26:37 UTC |
| Connect time | 6.2s (18:26:37 → 18:26:43) |
| First log line | `Connecting to MetaAPI (LIVE_TRADING=False)…` |
| Bot state | Off-hours sleep (next session: London 07:00 UTC 2026-06-22) |

---

## Account Snapshot

| Field | Value |
|---|---|
| MetaAPI Account ID | `026ea073-5241-4d53-9a87-b0cb791443af` |
| Broker | Vantage Markets Demo |
| Server | VantageMarkets-Demo |
| Platform | MT5 |
| Region | london (cloud-g2) |
| Balance | 100,000.00 USD |
| Equity | 100,000.00 USD |
| Leverage | 1:500 |
| Open positions | 0 |
| LIVE_TRADING | false |

*(Balance/equity from OPS-01 pre-flight run at 18:16 UTC, same session)*

---

## Connectivity

| Field | Value |
|---|---|
| MetaAPI status | CONNECTED |
| Replicas | 2 (london-a + london-b) |
| Authentication | true |
| First sync | 18:26:43 UTC |

---

## Market State at Startup

| Field | Value |
|---|---|
| UTC time | 18:27 |
| Active session | None (off-hours) |
| Next session | London 07:00 UTC 2026-06-22 |
| Seconds to session | 45,195s (~12.5h) |
| EURUSD spread | 7.2 pip (wide, off-hours) |
| GBPUSD spread | 19.2 pip (wide, off-hours) |

---

## Resources at Startup

| Field | Value |
|---|---|
| Bot RSS memory | 5 MB |
| System available RAM | 1,400 MB |
| Disk free | 13.4 GB (35.5%) |
| Log file | `logs/bot.log` — daily rotation active (backupCount=7) |

---

## Heartbeat

First heartbeat expected at: **18:31:37 UTC** (5 minutes after start).

Heartbeat fields: `timestamp`, `uptime_seconds`, `connection_status`, `balance`, `equity`, `open_positions`, `last_signal_time`

---

## Log Rotation

Method: `logging.handlers.TimedRotatingFileHandler`  
Schedule: `when='midnight'` (UTC)  
Retention: 7 days (`backupCount=7`)  
Naming: `logs/bot.log.YYYY-MM-DD` for rotated files

---

## Risk Manager State

| Field | Value |
|---|---|
| daily_loss_r | 0.0 |
| weekly_loss_r | 0.0 |
| consecutive_losses | 0 |
| halted | false |
| Daily reset | 2026-06-21 (fresh) |
| Weekly reset | 2026-W24 (fresh) |

---

## 7-Day Run Schedule

| Day | Date | London Session |
|---|---|---|
| Day 0 (start) | 2026-06-21 | Off-hours at start |
| Day 1 | 2026-06-22 | 07:00–10:00 UTC |
| Day 2 | 2026-06-23 | 07:00–10:00 UTC |
| Day 3 | 2026-06-24 | 07:00–10:00 UTC |
| Day 4 | 2026-06-25 | 07:00–10:00 UTC |
| Day 5 | 2026-06-26 | 07:00–10:00 UTC |
| Day 6 | 2026-06-27 | 07:00–10:00 UTC |
| Day 7 (end) | 2026-06-28 | Evaluate OPS-01 pass criteria |

London + NY sessions active Mon–Fri. Weekend: off-hours sleep.
First live signal window: Monday 2026-06-22 07:00 UTC.

*OPS-01A | Day-0 Baseline | 2026-06-21T18:27 UTC*
