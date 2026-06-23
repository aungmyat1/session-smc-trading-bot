# OPS01_RECONNECT_AUDIT.md
# OPS-01 — Reconnect Behavior Audit
# Run: 2026-06-21T18:17:18 UTC

---

## Verdict

### ✅ PASS — all reconnect attempts succeeded

---

## Test Method

Each cycle: `client.disconnect()` → 3s wait → `client.connect()` → verify `get_account_info()`.
Four cycles map to production retry schedule: 30s / 60s / 120s / 300s.
Timing of retries is SDK-managed; this test validates the reconnect *path*, not the delay.

---

## Initial Connection

Connected in **6967 ms**

---

## Reconnect Attempts

| # | Label | Success | Balance | Elapsed |
|---|---|---|---|---|
| 1 | retry-30s | ✅ | 100,000 | 9.22s |
| 2 | retry-60s | ✅ | 100,000 | 9.16s |
| 3 | retry-120s | ✅ | 100,000 | 9.12s |
| 4 | retry-300s | ✅ | 100,000 | 9.06s |

---

## Production Retry Schedule

The MetaAPI Cloud SDK manages reconnection internally. On network loss:

| Event | SDK Behaviour |
|---|---|
| WebSocket drop | Immediate reconnect attempt |
| Reconnect fails | Exponential back-off (SDK-managed) |
| `wait_synchronized()` timeout | Raises; bot re-polls on next 60s tick |
| `get_candles()` failure | Returns `[]`; scan skipped; no order placed |
| `get_account_info()` failure | Skips equity fetch; next poll retries |

---

## bot.py Recovery Path

```
Connection drops during active session:
  → get_candles() returns []
  → _scan_pair() returns early (len(m15) < 20)
  → bot sleeps POLL_INTERVAL (60s)
  → SDK reconnects in background
  → next poll: get_candles() succeeds again
  → no signal missed (seen_signals dedup prevents re-processing)
```

Final state after test: ✅ OK

*OPS-01 | Reconnect | 2026-06-21T18:17:18 UTC*