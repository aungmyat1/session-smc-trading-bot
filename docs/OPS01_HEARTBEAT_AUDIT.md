# OPS01_HEARTBEAT_AUDIT.md
# OPS-01 — Heartbeat Validation Audit
# Date: 2026-06-21

---

## Verdict

### ✅ PASS — heartbeat implementation verified

All 7 required fields present. Interval: 300s (5 minutes). Telegram + log delivery confirmed.

---

## Implementation

**Location:** `bot.py:_send_heartbeat()` (called from `run_bot()` main loop)

**Trigger:** `elapsed = (now - last_heartbeat).total_seconds() >= 300`
No threads — evaluated at the top of each 60s poll cycle.

**Fields emitted (OPS-01 spec vs actual):**

| Required Field | bot.py Field | Source | Status |
|---|---|---|---|
| `timestamp` | `now.strftime('%Y-%m-%dT%H:%M UTC')` | `datetime.now(UTC)` | ✅ |
| `uptime_seconds` | `int((now - _BOT_START_TIME).total_seconds())` | global `_BOT_START_TIME` set at `run_bot()` entry | ✅ |
| `connection_status` | `"CONNECTED"` or `"DISCONNECTED"` | `client.connection_status()["connected"]` | ✅ |
| `balance` | `info.balance` | `client.get_account_info()` | ✅ |
| `equity` | `info.equity` | `client.get_account_info()` | ✅ |
| `open_positions` | `len(positions)` | `client.get_open_positions()` | ✅ |
| `last_signal_time` | `_LAST_SIGNAL_TIME.strftime("%H:%MZ")` or `"none"` | global `_LAST_SIGNAL_TIME` set on each successful signal | ✅ |

---

## Sample Heartbeat Message

```
[HEARTBEAT] 2026-06-21T08:05 UTC
uptime=300s  connection_status=CONNECTED  live=False
balance=100000.00  equity=100000.00  open_positions=0
last_signal=none
```

Sent to:
- `logger.info()` → `logs/bot.log`
- `telegram.send()` → `@aungpro1bot` / `TELEGRAM_CHAT_ID`

---

## Error Handling

If `get_account_info()` or `get_open_positions()` throws (e.g. connection momentarily
lost), `_send_heartbeat()` falls back to `balance=0.0, equity=0.0, n_pos=-1` and
still sends the heartbeat. `n_pos=-1` is the signal that the fetch failed.

---

## Uptime Tracking

`_BOT_START_TIME` is set at the top of `run_bot()` (not module import time), so it
resets on every restart. `uptime_seconds` counts from the current process start,
not from the total OPS-01 run.

---

## Known SDK Warning (benign)

`packet queue is empty, aborting` appears in MetaAPI SDK logs during RPC close.
This is a cleanup race condition in SDK v29.1.1. It does not affect heartbeat
delivery or account data accuracy.

---

## Interval Verification (during run)

```bash
grep HEARTBEAT logs/bot.log | awk '{print $1, $2}' | head -20
# Expected: entries 5 minutes apart during active session
```

Between sessions (off-hours), the bot sleeps `min(wait_to_next_session, 300s)`.
If next session is >5 min away, a heartbeat fires during the sleep.

---

## Test Coverage

`tests/test_ops01_safety.py::TestHeartbeatFields`:
- `test_all_seven_fields_present` — asserts all 7 required keys present ✅
- `test_connection_status_values` — validates `CONNECTED`/`DISCONNECTED` enum ✅
- `test_uptime_seconds_non_negative` — validates uptime math ✅

*OPS-01 | Heartbeat Audit | 2026-06-21*
