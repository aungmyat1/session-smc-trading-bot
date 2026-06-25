# OPS01_PREFLIGHT.md
# OPS-01 — Pre-flight Validation Report
# Run: 2026-06-21T18:16:35 UTC

---

## Verdict

### ✅ PASS — pre-flight complete, bot ready to start

---

## Account Details

| Field | Value |
|---|---|
| Account ID | `026ea073…` |
| Balance | 100,000.00 USD |
| Equity | 100,000.00 USD |
| Leverage | 1:500 |
| Open positions | 0 |
| LIVE_TRADING | false (enforced) |

---

## Symbol Prices

| Symbol | Bid | Ask | Spread | Status |
|---|---|---|---|---|
| EURUSD | `1.14708` | `1.14780` | `7.2` pip | ⚠️ wide (off-hours) |
| GBPUSD | `1.32194` | `1.32386` | `19.2` pip | ⚠️ wide (off-hours) |

---

## Full Check Log

| # | Check | Status | Value |
|---|---|---|---|
| 1 | LIVE_TRADING=false | ✅ | False |
| 2 | METAAPI_TOKEN present | ✅ | SET |
| 3 | METAAPI_ACCOUNT_ID present | ✅ | 026ea073… |
| 4 | METAAPI_ACCOUNT_ID is new account | ✅ | 026ea073 |
| 5 | connect() | ✅ | OK |
| 6 | is_connected | ✅ | True |
| 7 | connection_status CONNECTED | ✅ | True |
| 8 | connection_status live_trading=false | ✅ | False |
| 9 | get_account_info() | ✅ | OK |
| 10 | balance > 0 | ✅ | 100,000.00 USD |
| 11 | equity > 0 | ✅ | 100,000.00 USD |
| 12 | leverage set | ✅ | 1:500 |
| 13 | get_open_positions() | ✅ | 0 position(s) |
| 14 | EURUSD price | ✅ | bid=1.14708  ask=1.14780  spread=7.2pip |
| 15 | GBPUSD price | ✅ | bid=1.32194  ask=1.32386  spread=19.2pip |
| 16 | All 7 heartbeat fields present | ✅ | balance, connection_status, equity, last_signal_time, open_positions, timestamp, uptime_seconds |
| 17 | place_order DRY_RUN | ✅ | id=DRY_RUN  dry_run=True |

---

## Heartbeat Fields (startup)

| Field | Value |
|---|---|
| `timestamp` | `2026-06-21T18:16:35.637823+00:00` |
| `uptime_seconds` | `0` |
| `connection_status` | `CONNECTED` |
| `balance` | `100000` |
| `equity` | `100000` |
| `open_positions` | `0` |
| `last_signal_time` | `none` |

---

## Blockers

None.

---

## Next Step

```bash
tmux new-session -d -s bot 'python3 bot.py 2>&1 | tee logs/bot.log'
tmux attach -t bot
```

*OPS-01 | Pre-flight | 2026-06-21T18:16:35 UTC*