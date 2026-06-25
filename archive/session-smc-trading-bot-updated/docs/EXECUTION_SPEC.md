# EXECUTION_SPEC.md
# Execution Layer Specification
# v1.0 | DO NOT MODIFY without explicit task approval

---

## Status

Execution layer is **strategy-agnostic** and must remain so.
No execution-layer changes until Strategy A passes Phase-0 gate.

---

## Broker

- **Broker:** VT Markets (standard account)
- **Pairs:** EURUSD (magic 21001), GBPUSD (magic 21002)
- **Spread:** EURUSD 0.8–1.2 pip + 0.6 pip commission RT = ~1.4 pip total
- **Connection:** MetaAPI Cloud SDK (`metaapi-cloud-sdk>=29`)
- **Auth:** `METAAPI_TOKEN` + `METAAPI_ACCOUNT_ID` from `.env`
- **Mode:** `LIVE_TRADING=false` (demo until owner flips)

---

## Signal Contract (strategy → execution)

The execution layer reads exactly these fields from `Signal`:

```python
signal.side          # 'long' | 'short'
signal.entry         # float — entry price
signal.stop_loss     # float — stop loss price
signal.take_profit   # float — take profit price
signal.reason        # str   — log message
signal.session       # str   — 'london' | 'new_york'
signal.timestamp     # datetime
```

The strategy module must not add fields that execution depends on.
Execution must not reach into strategy internals.

---

## Order Manager

- Place market order at `signal.entry` (best available)
- Set SL and TP on the same order
- Magic number identifies pair/strategy
- Log every order attempt and outcome to `logs/`

---

## Position Manager

- Track open positions per (pair, session)
- Block new orders if position already open for that session
- Close position at SL/TP hit (broker-side) or session end (market order)
- Report result in R-multiples to journal

---

## Journal

- Write one row per closed trade to `logs/trades.csv`
- Fields: `timestamp, pair, session, side, entry, sl, tp, exit, pips, r_outcome, reason`

---

## Circuit Breakers

| Trigger | Action |
|---|---|
| Daily loss ≥ 3R | Halt trading for the day |
| Drawdown ≥ 10% from peak | Kill switch — halt until reset |
| Consecutive losses ≥ 5 | Halt until next trading day |
| Connection error × 3 | Alert + halt |
| Order rejected × 2 | Alert + halt |

---

## Telegram Alerts

- Token: `TELEGRAM_BOT_TOKEN` from `.env`
- Chat: `TELEGRAM_CHAT_ID` from `.env`
- Events: signal fired, trade opened, trade closed, circuit breaker triggered, error

---

## VPS Requirements

- OS: Linux (Ubuntu 22.04+)
- RAM: ≥ 1 GB
- Uptime: 99%+
- NTP sync: required (time-sensitive session windows)
- Timezone: UTC system clock

---

## Recovery Logic

- On restart: reload open positions from MetaAPI
- Do not re-enter a position that is already open
- Do not trade if unable to verify current positions

---

## Files

```
execution/
  executor.py          MetaAPI order placement
  risk_manager.py      Circuit breakers + position sizing
  journal.py           Trade logging
  alerts.py            Telegram fire-and-forget
bot.py                 Main loop (strategy → execution)
```
