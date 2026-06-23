# BACKTEST_FAILURE_ANALYSIS.md
# Strategy A — Phase-0 FAIL — Root Cause Analysis
# Run: 20260621T060745-f6ac57  |  Date: 2026-06-21

---

## Failure Summary

| RR | Trades | Net PF (std) | Net PF (2×) | Failure reason |
|---|---|---|---|---|
| 2 | 181 | 0.992 | 0.824 | Fails std AND 2× |
| 3 | 181 | 1.014 | 0.859 | Fails 2× stress |
| 4 | 181 | 1.102 | 0.942 | Fails 2× stress |
| 5 | 181 | 1.126 | 0.965 | Fails 2× stress (gap = 0.035) |

Gate requires: Trades ≥ 100 AND Net PF (std) > 1.0 AND Net PF (2×) > 1.0

---

## Top Rejection Reason

**2× spread stress test — all RR variants fail.**

The strategy has measurable raw edge (gross PF 1.20–1.33) and passes standard spread
at RR 3, 4, 5. The gap between std and 2× performance reveals fragility to cost assumptions.

At 2× stress the spread doubles:
- EURUSD: 2.8 pip RT vs 1.4 pip RT standard
- GBPUSD: 3.6 pip RT vs 1.8 pip RT standard

With median SL of 18.5 pips, each trade absorbs an extra 0.076R (EURUSD) or 0.097R
(GBPUSD) under 2× vs standard. Across 181 trades with ~65% loss rate, the total drag
shifts combined net PF from 1.126 (std) to 0.965 (2×) — a 14% collapse.

---

## Trade Distribution

### Outcome Distribution (RR 5)

| Symbol | TP (win) | SL (loss) | Timeout | Total |
|---|---|---|---|---|
| EURUSD | 10 (9.0%) | 74 (66.7%) | 27 (24.3%) | 111 |
| GBPUSD |  8 (11.4%) | 45 (64.3%) | 17 (24.3%) | 70 |
| Combined | 18 (9.9%) | 119 (65.7%) | 44 (24.3%) | 181 |

TP hit rate is 10% — displacement confirmation gates entry but does not efficiently reach TP.
SL hit rate is 66% — two-thirds of trades stop out, maximising spread cost impact on losses.
Timeouts (24%) close near entry, contributing negligible positive or negative R.

### SL Size Distribution (all trades, RR 5)

| | Min | Median | Mean | Max |
|---|---|---|---|---|
| SL pips | 1.3 | 18.5 | 21.9 | 86.0 |

Extreme low (1.3 pip) SLs generate spread_cost_R of 1.08R per trade — catastrophic.
No minimum SL filter is applied in the current spec. This is a likely improvement target.

### Average Trade Duration

| Symbol | Avg Duration |
|---|---|
| EURUSD | 566 min (~9.4 hr) |
| GBPUSD | 634 min (~10.6 hr) |

Average duration approaches the 96-bar (24 hr) timeout. Most trades are not resolving
to TP within the session — the strategy holds through counter-moves.

---

## Session Distribution

| Session | Trades | Win% | Net PF (std) | Net PF (2×) |
|---|---|---|---|---|
| london   | 128 (70.7%) | 28.1% | 0.973 | 0.819 |
| new_york |  53 (29.3%) | 39.6% | 1.571 | 1.344 |

London generates 71% of trades but is below 1.0 at standard spread.
New York generates 29% of trades and passes 2× stress with strong edge (1.344).

### By Symbol × Session (RR 5)

| Symbol | Session | n | Win% | PF (std) | PF (2×) |
|---|---|---|---|---|---|
| EURUSD | london     | 84 | 27.4% | 1.045 | 0.891 |
| EURUSD | new_york   | 27 | 37.0% | 1.219 | 1.102 |
| GBPUSD | london     | 44 | 29.5% | 0.839 | 0.701 |
| GBPUSD | new_york   | 26 | 42.3% | 1.970 | 1.682 |

**GBPUSD London (PF std=0.839, PF 2×=0.701) is the single largest drag.**
Both NY sessions pass 2× stress independently.

---

## Likely Bottleneck

Three converging problems, ranked by estimated impact:

**1 — GBPUSD London is structurally negative (pf_std=0.839).**
London sweeps on GBPUSD produce low win rate (29.5% vs 42.3% in NY). This may reflect
London's role as a sweep session for GBPUSD rather than a reliable reversal session.
Removing GBPUSD London alone would increase combined PF meaningfully.

**2 — Low TP hit rate (10%) magnifies spread cost.**
With only 10% of trades reaching TP, the +RR win is diluted. Edge exists in the raw R
distribution but conversion to TP is insufficient. Displacement confirmation confirms
direction but the price path to TP is regularly interrupted by counter-moves before 96 bars.

**3 — No minimum SL filter.**
Setups with SL < 10 pip (narrow sweep wicks) generate spread_cost_R of 0.14–1.08R.
These trades pass all signal gates but are not viable at retail spreads. A 10 pip
minimum SL would eliminate the worst-ratio trades without changing signal generation.

---

## Per-Year Breakdown (combined, RR 5, std spread)

| Year | Trades | Win% | Net PF | Note |
|---|---|---|---|---|
| 2021 |  17 | 29.4% | 1.053 | EURUSD only (GBPUSD data from 2023) |
| 2022 |  25 | 36.0% | 1.416 | |
| 2023 |  53 | 26.4% | 0.854 ⚠ | First GBPUSD year; high London trade count |
| 2024 |  23 | 39.1% | 1.592 | |
| 2025 |  45 | 26.7% | 0.812 ⚠ | Low win rate — possible trending regime |
| 2026 |  18 | 44.4% | 2.182 | Partial year (Jan–Jun) |

2023 and 2025 are the two losing years. Both have win rates of 26–27%,
suggesting the strategy underperforms in trending regimes.

---

## Recommended Next Experiment

### ST-A2 Candidates — from Phase-1 Experiments (see EXPERIMENT_RESULTS.md)

Do NOT re-run ST-A. Any parameter change = new trial row in VERDICT_LOG.md.
Three variants crossed the Phase-0 gate in Phase-1 post-hoc testing:

| Option | Filter | n | PF (std) | PF (2×) | Trades removed |
|---|---|---|---|---|---|
| A (minimum change) | EXP-01 ≥ 5 pip SL floor @ RR5 | 169 | 1.151 | 1.025 | 12 (6.6%) |
| B | EXP-01 ≥ 7 pip SL floor @ RR4 | 166 | 1.142 | 1.020 | 15 (8.3%) |
| C (highest PF) | EXP-04 Exclude GBPUSD London @ RR5 | 137 | 1.226 | 1.059 | 44 (24.3%) |

**Option A — minimum invasive change:**
Add `min_sl_pips: 5.0` rejection gate in `build_signal()`. Removes only 12 trades
(very narrow sweep wicks). All other parameters held constant. Crosses gate at PF_2x=1.025.

Note: EXP-01 ≥10pip FAILS (PF_2x=0.943) — trades in the 5–10 pip SL range are net-positive
contributors. Do NOT use 10pip as the threshold.

**Option C — highest PF, structural change:**
Exclude GBPUSD London session entirely from scanning. Requires session-level filter in
`session_strategy.py`. GBPUSD London win rate (29.5%) and PF_2x=0.701 is confirmed drag.
This is a more structural change but produces PF_2x=1.059 (+0.094 vs baseline).

**Alternative path — data completeness:**
Complete GBPUSD download from 2021 (currently starts 2023-03-13) to raise GBPUSD
trade count from 70 to ~180. Combined n would reach ~290.
EXP-03 NY-only already shows PF_2x=1.381 but n=53 < gate. With full data, NY-only
variant may reach n≥100 and become the strongest candidate (no filter needed, just scope).

---

## Files

- `docs/BACKTEST_RESULTS.md` — full metrics breakdown
- `research/backtest_runs.csv` — 8 rows (4 RR × 2 symbols)
- `research/trades.csv` — 724 rows (181 signals × 4 RR variants)

*Run ID: 20260621T060745-f6ac57 | Generated: 2026-06-21*
