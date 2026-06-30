# BACKTEST_SPEC.md
# Backtest Standards & Requirements
# v1.0

---

## Core Principles

1. **Walk-forward only.** Process bars in strict chronological order.
2. **No lookahead.** When computing signal at bar `i`, only `candles[:i]` is visible.
3. **Bar-close fills.** Entry = `candle[i].close`. No next-bar open slippage model.
4. **Chronological integrity.** Input CSV must be sorted ascending by time before use.

---

## Data Source

- **Provider:** Dukascopy public datafeed (no key required)
- **Script:** `scripts/fetch_data.py`
- **Format:** `data/historical/{PAIR}_{TF}.csv` with columns `time,open,high,low,close,volume`
- **Symbols:** EURUSD (`EUR_USD`), GBPUSD (`GBP_USD`)
- **Timeframes:** M15 (signal), H4 (bias)
- **Coverage:** 5 years minimum (≥ 4.5yr after audit gate)
- **Audit:** Must pass `scripts/data_audit.py` before backtest

---

## Spread Model

| Pair | Standard RT | 2× Stress RT |
|---|---|---|
| EURUSD | 1.4 pips | 2.8 pips |
| GBPUSD | 1.8 pips | 3.6 pips |

"RT" = round-trip (entry + exit combined).

**Application to each trade:**
```
spread_cost_R = spread_pips_RT / sl_pips
net_R = gross_R - spread_cost_R
```

A win at RR=3 with SL=20pip and spread=1.4pip:
`net_R = 3.0 - (1.4/20) = 2.93`

A loss with same spread:
`net_R = -1.0 - (1.4/20) = -1.07`

---

## Trade Simulation

For signal at bar `i` (entry = `candles[i].close`):
1. Walk bars `i+1, i+2, …` (up to max 96 bars = 24 hours)
2. For each bar, check (conservative — SL checked before TP within same bar):
   - Long: `bar.low ≤ SL` → LOSS (−1R)
   - Long: `bar.high ≥ TP` → WIN (+RR R)
   - If both hit in same bar → LOSS (SL assumed first)
3. If neither hit within 96 bars → close at last bar close (record as fractional R)

---

## Required Report Fields

Per symbol and across all symbols:

| Field | Definition |
|---|---|
| Trades | Total signals fired |
| Win Rate | Wins / Trades × 100 |
| Profit Factor | Σ(gross wins) / Σ(gross losses) — before spread |
| Net PF (std) | Σ(net wins) / Σ(net losses) — after standard spread |
| Net PF (2×) | Same with 2× spread |
| Avg R | Mean net R per trade |
| Max DD | Largest peak-to-trough R drawdown in cumulative R curve |
| Net R | Sum of all net R outcomes |

---

## Per-Year Breakdown

Report separately for each calendar year.
Flag with ⚠ if a year has PF < 1.0 AND n ≥ 5 (watch for regime-specific failure).

---

## Per-Session Breakdown

Report London and New York separately.
Flag if one session drives all the PF while the other is negative.

---

## RR Comparison Table

Run four independent backtests (same signals, different TP):

| RR | Trades | Win% | PF (std) | PF (2×) | Avg R | Max DD | Net R |
|---|---|---|---|---|---|---|---|
| 2 | | | | | | | |
| 3 | | | | | | | |
| 4 | | | | | | | |
| 5 | | | | | | | |

---

## Phase-0 Gate (non-bypassable)

Strategy passes if **ALL** of the following are true:

1. `Trades ≥ 50`
2. `Net PF (std) > 1.0`
3. `Net PF (2×) > 1.0`

All three must pass in the SAME RR variant. Report which RR(s) pass.

---

## Failure Handling

- `n < 50` → INVALID — insufficient sample. Do not report PF as a result.
- Any year with `n < 5` → exclude that year from per-year ⚠ flags.
- If no RR variant passes → FAIL. Do not proceed to demo.

---

## Audit Files Generated

- `DATA_AUDIT.md` — data quality gate (run before backtest)
- `LOOKAHEAD_AUDIT.md` — per-module lookahead verification
- `PERFORMANCE_AUDIT.md` — generated after backtest, contains full breakdown

---

## Scripts

| Script | Purpose |
|---|---|
| `scripts/fetch_data.py` | Download Dukascopy M15+H1+H4 |
| `scripts/data_audit.py` | DATA_AUDIT.md generation |
| `scripts/backtest_session_liquidity.py` | Strategy A backtest |
| `scripts/backtest.py` | Strategy B (SMC) backtest — PENDING |
