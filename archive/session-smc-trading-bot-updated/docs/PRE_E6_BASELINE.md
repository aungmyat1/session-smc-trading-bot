# PRE_E6_BASELINE.md
# ST-A2 Performance Snapshot — Pre-E6 Baseline
# Purpose: Comparison reference for E6 cost revalidation
# Snapshot date: 2026-06-24
# Do not modify. Do not rerun optimization against this document.

---

## Strategy Identity

| Field | Value |
|---|---|
| Strategy name | Session Liquidity Reversal |
| Trial ID | ST-A2 |
| Strategy ID | SA |
| Strategy version | 1.0.0 |
| Differentiating change from ST-A | `min_sl_pips = 5.0` (rejects 12 sub-5pip sweep wicks) |
| Operating RR | **5** (max PF_2x; both RR4 and RR5 pass gate) |
| Canonical run ID | `20260621T100458-183aaa` |
| Run date | 2026-06-21T10:04:58Z |

---

## Backtest Dataset

| Symbol | Timeframe | Start | End | Bars | Duration |
|---|---|---|---|---|---|
| EURUSD | M15 | 2021-06-21 | 2026-06-19 | 121,086 | 4.9 yr |
| GBPUSD | M15 | 2023-03-13 | 2026-06-19 | 79,339 | 3.3 yr |
| H4 bias filter | H4 | same range | same range | — | 4H bars |

Data source: Dukascopy historical (`scripts/fetch_data.py`).
Holdout: entire available range — no in-sample / out-of-sample split.

---

## Cost Assumptions (active at time of baseline)

| Field | Value |
|---|---|
| Active profile | `PLACEHOLDER_vt_markets_assumption` |
| Profile source | Inherited from CLAUDE.md VT Markets Standard estimate |
| EURUSD standard | **1.4 pip** |
| EURUSD stress 2× | 2.8 pip |
| GBPUSD standard | **1.8 pip** |
| GBPUSD stress 2× | 3.6 pip |
| Commission | 0.0 pip (embedded in spread — Standard STP model) |
| Validation status | **UNVALIDATED PLACEHOLDER** — E6 will replace with measured killzone values |

---

## Phase-0 Gate Result

Gate condition: Trades ≥ 100 AND Net PF (std) > 1.0 AND Net PF (2×) > 1.0

| RR | Trades | Net PF (std) | Net PF (2×) | Gate |
|---|---|---|---|---|
| 2 | 169 | 1.003 | 0.877 | ❌ FAIL |
| 3 | 169 | 1.078 | 0.954 | ❌ FAIL |
| 4 | 169 | 1.149 | 1.022 | ✅ PASS |
| **5** | **169** | **1.151** | **1.025** | **✅ PASS** |

**Verdict: PASS** — operating at RR=5.
**Margin above gate (PF_2x > 1.00): +0.025** — thin; E6 confirms whether it survives measured costs.

---

## Combined Performance (RR 5, EURUSD + GBPUSD)

| Metric | Standard spread | 2× Stress |
|---|---|---|
| Total trades | 169 | 169 |
| Win count | 54 | — |
| Win rate | **32.0%** | 32.0% |
| Gross PF | 1.299 | 1.299 |
| Net PF | **1.151** | **1.025** |
| Max drawdown | **18.72 R** | — |
| Total net R | 18.28 R | — |
| Expectancy | **0.108 R / trade** | — |
| CAGR | N/A — R-based simulation; no capital model | — |

---

## Per-Symbol (RR 5)

| Symbol | Trades | Win% | Gross PF | Net PF (std) | Net PF (2×) | Max DD | Total R |
|---|---|---|---|---|---|---|---|
| EURUSD | 105 | 29.5% | 1.196 | 1.059 | 0.945 | 14.00 R | 4.61 R |
| GBPUSD | 64 | 35.9% | 1.484 | 1.314 | 1.168 | 9.70 R | 13.67 R |
| **Combined** | **169** | **32.0%** | **1.299** | **1.151** | **1.025** | **18.72 R** | **18.28 R** |

Note: EURUSD fails 2× stress alone (PF_2x = 0.945). GBPUSD carries the combined pass.
This concentration in GBPUSD is the key sensitivity E6 must watch.

---

## Per-Session (RR 5, standard spread)

| Session | Trades | Win% | Net PF (std) |
|---|---|---|---|
| london | 118 | 28.0% | 0.949 |
| new_york | 51 | 41.2% | 1.731 |

New York drives profitability. London is sub-1.0 at standard spread.

---

## Per-Year (RR 5, combined, standard spread)

| Year | Trades | Win% | Net PF | Flag |
|---|---|---|---|---|
| 2021 | 15 | 26.7% | 0.830 | ⚠ sub-1.0 (n=15, low count) |
| 2022 | 25 | 36.0% | 1.416 | |
| 2023 | 48 | 27.1% | 0.878 | ⚠ sub-1.0 |
| 2024 | 20 | 40.0% | 1.659 | |
| 2025 | 43 | 27.9% | 0.886 | ⚠ sub-1.0 |
| 2026 | 18 | 44.4% | 2.182 | partial year |

3 of 5 complete years are sub-1.0 at standard spread. The combined PF is > 1.0
because winning years have higher magnitudes. Regime dependency is a known characteristic.

---

## Strategy Parameters (locked — no optimization)

| Parameter | Value |
|---|---|
| `min_sl_pips` | 5.0 |
| `rr` | 3.0 (DEFAULT_CONFIG default; operating RR = 5 is set per-run) |
| `atr_period` | 14 |
| `displacement_mult` | 1.2 |
| `sl_buffer_pips` | 2.0 |
| `sweep_timeout_bars` | 4 |
| `min_range_pips` EURUSD | 15.0 |
| `min_range_pips` GBPUSD | 20.0 |

Source: `strategy/session_liquidity/session_strategy.py DEFAULT_CONFIG`

---

## How E6 Uses This Document

When `bash scripts/run_e6_revalidation.sh` completes, compare each metric in
`docs/BACKTEST_RESULTS.md` (E6 run) against this baseline:

| Metric | This baseline | E6 result | Expected direction |
|---|---|---|---|
| Trade count | 169 | — | Must equal 169 |
| Win rate | 32.0% | — | Must equal 32.0% |
| Net PF (std) | 1.151 | — | Higher if measured cost < 1.4/1.8 pip |
| Net PF (2×) | **1.025** | — | Higher if measured cost < placeholder |
| Max DD | 18.72 R | — | Approximately same |
| EURUSD PF_2x | 0.945 | — | Key watch — already sub-1.0 |
| GBPUSD PF_2x | 1.168 | — | Key driver of combined pass |

**Trade count or win rate changing** = cost injection error. Stop and investigate.
**PF_2x dropping below 1.00** = E6 REJECT, strategy does not survive measured costs.

---

*PRE_E6_BASELINE.md | Snapshot 2026-06-24 | Source run: 20260621T100458-183aaa | Do not modify*
