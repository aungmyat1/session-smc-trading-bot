# Risk Management

**Document:** Risk Management Rules & Platform Enforcement
**Last updated:** 2026-06-30

---

## Position Sizing

Position size is calculated from account balance, risk percentage, and SL distance:

```
Lots = (Account_Balance × Risk_Pct) / (SL_pips × pip_value_per_lot)
```

Default risk per trade: **1.0% of account balance**.

The formula is applied at signal time using the current balance (not starting balance). This means compounding applies to winning streaks but position size reduces automatically during drawdown.

---

## Stop-Loss Placement

- SL is placed at a structurally significant level (below OB low, beyond swing, beyond liquidity sweep)
- A buffer of 2–3 pips is applied beyond the structural reference
- **Minimum SL:** 8 pips (prevents excessive lot-size inflation on tight SLs)
- **Maximum SL:** 25 pips (trades with wider SL are skipped — RR ratio too poor)
- SL is fixed at entry; no manual movement during the trade (other than break-even after TP1)

---

## Take-Profit Rules

- **TP1:** 1R (50% of position closed; SL moved to break-even)
- **TP2:** Structural target (next liquidity pool, session extreme, swing level)
- Minimum R:R ratio: **1:2** (trade skipped if TP2 distance < 2 × SL distance)
- No trailing stop during early trade; trailing only after 2R threshold is reached

---

## Daily Loss Limit

- **Hard limit:** 3% of account OR 3R (whichever comes first)
- When hit: close all open positions, stop new trades until next UTC trading session
- Limit resets at 00:00 UTC

---

## Weekly & Monthly Drawdown

| Threshold | Action |
|-----------|--------|
| Weekly DD > 5% | Reduce risk to 0.5% per trade for remainder of week |
| Monthly DD > 10% | Suspend new trades; review pipeline |
| Monthly DD > 15% | Hard stop; re-enter qualification pipeline |

---

## Concurrency Rules

- **Maximum 1 position per symbol at any time** (SVOS §0 Rule 7)
- Maximum 2 total positions simultaneously (one EURUSD, one GBPUSD)
- No pyramiding (no adding to an existing open position)

---

## Session Trading Hours

New trades are entered **only** during high-liquidity sessions:

| Session | UTC Window | Notes |
|---------|------------|-------|
| London Kill Zone | 07:00–10:00 UTC | Primary session |
| NY Kill Zone | 12:00–15:00 UTC | Secondary session |
| No trading | 00:00–06:59 UTC | Asian low-liquidity |
| No trading | After 20:00 UTC Friday | Weekend rollover |

---

## Fee Model (Vantage Standard Account)

| Symbol | Spread (Standard) | Spread (2× Stress) |
|--------|-------------------|--------------------|
| EURUSD | 1.0 pip RT | 2.0 pip RT |
| GBPUSD | 1.5–1.8 pip RT | 3.0–3.6 pip RT |

Commission: zero for spread-inclusive accounts. If commission-based, add to RT cost.

All backtest results must be **net-of-fees**. Gross PF results are not accepted.

---

## Phase 3 Backtest Hard Gates

| Gate | Threshold |
|------|-----------|
| Trade count | ≥ 50 |
| Net PF (standard spread) | > 1.0 |
| Net PF (2× stress spread) | > 1.0 |

Single-spread PASS is insufficient. Both gates must hold simultaneously.

---

## Emergency Stop Protocol

The deployment bot monitors for:
- Position outside expected SL/TP range
- Drawdown exceeding daily limit
- Disconnection from MetaAPI
- Unexpected position count (> max_concurrent)

On trigger: all positions closed at market; Telegram alert sent; bot halts until manual restart.
