# RISK_SPEC.md
# Risk Management Specification
# v1.0 | DO NOT MODIFY without explicit task approval

---

## Position Sizing

```
lot_size = (account_equity × risk_pct) / (sl_pips × pip_value_per_lot)
```

- `risk_pct` = 0.01 (1% per trade)
- `pip_value_per_lot` = $10 for standard lot on EURUSD/GBPUSD
- Round down to 0.01 lot precision
- Minimum lot: 0.01

---

## Per-Trade Limits

| Parameter | Value |
|---|---|
| Risk per trade | 1% of account equity |
| Max SL (pips) | 50 pips (reject if wider — degenerate setup) |
| Min SL (pips) | 3 pips (reject if tighter — spread consumes it) |

---

## Session Gate

| Rule | Limit |
|---|---|
| Max trades per London session per day | 1 |
| Max trades per NY session per day | 1 |
| Concurrent open positions | 1 per pair |

---

## Daily Loss Limit

- **3R per day** (each R = risk per trade)
- On breach: halt all trading for remainder of calendar day (EST)
- Reset at 18:00 EST (start of new Asian session)

---

## Drawdown Kill Switch

- **10% from peak equity**
- On breach: halt all trading, send critical alert
- Require manual reset: owner reviews and sets `KILL_SWITCH_OVERRIDE=true` in `.env`

---

## Consecutive Loss Limit

- **5 consecutive losses**
- On breach: halt until start of next trading day
- Reset counter after first win or daily reset

---

## Weekly Loss Limit

- **6R per week**
- On breach: halt for remainder of calendar week
- Reset on Monday 18:00 EST

---

## Circuit Breaker Priority

```
Kill switch (10% DD)       ← highest priority, manual reset required
Daily loss limit (3R)      ← auto-reset next day
Weekly loss limit (6R)     ← auto-reset Monday
Consecutive losses (5)     ← auto-reset next day
Individual trade SL        ← broker-managed
```

---

## Implementation Notes

- All limits stored in `config/config.yaml` or loaded from env
- Risk manager checks limits BEFORE placing any order
- If any limit is active → return without placing order → log reason
- Kill switch state persisted in `logs/kill_switch.json`

---

## Files

```
execution/risk_manager.py    all circuit breaker logic
config/config.yaml           configurable limits (not hardcoded)
```
