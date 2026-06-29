# ST_A2_D1_COMPARISON_REPORT.md
# TRIAL_ST_A2_D1_001 — Comparison Report
# Run date: 2026-06-25
# Runner: scripts/replay_st_a2_d1.py

---

## §1 — Run Parameters

| Parameter | Value |
|---|---|
| Trial ID | TRIAL_ST_A2_D1_001 |
| Period | 2026-05-01 → 2026-06-19 (data-limited; requested end 2026-06-30) |
| Trading days | ~34 (7 weeks) |
| Symbols | EURUSD + GBPUSD |
| ST-A2 exec params | rr=3.0, sl_buffer=2pip, disp_mult=1.2×ATR, min_sl=5pip |
| Cost model | EURUSD 1.4pip std / 2.8pip 2× | GBPUSD 1.8pip std / 3.6pip 2× |
| D1 swing_n | 3 (matches ST-A2 HTF bias config) |
| D1 lookback_swings | 3 |
| Gate C (POI) | DISABLED — stub only |

---

## §2 — Results

### Combined (EURUSD + GBPUSD)

| Metric | BASELINE | D1_BIAS | D1_LOCATION | D1_ALL |
|---|---|---|---|---|
| **Trades (n)** | **2** | **1** | **1** | **0** |
| PF (std) | ∞ | ∞ | ∞ | — |
| PF (2×) | ∞ | ∞ | ∞ | — |
| Win rate | 100.0% | 100.0% | 100.0% | — |
| Avg R (std) | 1.598 | 2.927 | 0.269 | — |
| Max DD (R) | 0.00 | 0.00 | 0.00 | — |
| Signals removed | 0 (0.0%) | 1 (50.0%) | 1 (50.0%) | 2 (100.0%) |

### Individual trades (BASELINE)

| Date | Symbol | Session | Dir | Entry | SL (pip) | Exit reason | Net R (std) | D1 bias | D1 location |
|---|---|---|---|---|---|---|---|---|---|
| 2026-06-16 | EURUSD | London | Long | 1.15870 | 14.5 | SESSION_END | +0.269 | bearish | equilibrium |
| 2026-06-18 | GBPUSD | London | Short | 1.33020 | 24.7 | TP1 | +2.927 | bearish | equilibrium |

### Per-variant gate actions

| Trade | Gate A result | Gate B result | D1_BIAS | D1_LOCATION | D1_ALL |
|---|---|---|---|---|---|
| EURUSD 2026-06-16 (Long) | **BLOCK** — D1 bearish vs 4H bullish | PASS — equilibrium | Removed | Kept | Removed |
| GBPUSD 2026-06-18 (Short) | PASS — D1 bearish agrees with 4H | **BLOCK** — bearish but price in discount (needs premium) | Kept | Removed | Removed |

---

## §3 — Statistical Assessment

**n=2 is statistically meaningless.** The 7-week window produces approximately 2 trades
at ST-A2's historical frequency (~2.8 trades/month combined from 5yr Phase-0 data).
The PF of ∞ (two wins) reflects only the absence of losses in this tiny sample,
not an edge signal.

No statistical inference can be drawn from n=2.

**Validity of individual gate observations:**

| Observation | Valid? |
|---|---|
| Gate A removed EUR long (D1 bearish vs 4H bullish) | Mechanically correct |
| Gate B removed GBP short (bearish trade in discount zone) | Mechanically correct |
| D1_ALL removed 100% of trades | Mechanically expected (each gate removes one) |
| PF comparisons between variants | NOT VALID — sample too small |

---

## §4 — Context: Prior Evidence (ST-D2-6M)

The same hypothesis was tested in `ST-D2-6M` (VERDICT_LOG) over 6 months
(2026-01-01 to 2026-06-19), which overlaps this trial's window.

| | BASELINE | D2_COMBINED (= D1_ALL equivalent) |
|---|---|---|
| n | 16 | 5 |
| PF (std) | 2.224 | 0.181 |
| PF (2×) | 1.909 | 0.135 |
| WR% | 50.0% | 20.0% |
| Signals removed | — | 68.8% |

**The 6-month window result is statistically more meaningful than this 7-week run.**
The pattern is consistent across both windows:
- Gate A + Gate B combined remove 69–100% of signals
- Remaining trades deteriorate (n=5, PF_2x=0.135 on 6 months vs n=0 on 7 weeks)
- No improvement in any quality metric

---

## §5 — Per-Gate Analysis

### Gate A (`d1_bias_filter`): D1 structure must agree with HTF bias

- Removed: EURUSD 2026-06-16 long (D1 bearish, 4H bullish — conflict)
- Kept: GBPUSD 2026-06-18 short (D1 bearish, 4H bearish — agree)
- The kept trade was the better trade (TP1 = 3R vs SESSION_END = 0.27R)
- Isolated Gate A finding: n=1 after filter, n=1 baseline kept
- Inconclusive: 1 trade each side

### Gate B (`d1_location_filter`): Price in premium/discount zone

- Removed: GBPUSD 2026-06-18 short (bearish trade but price in discount vs PDH/PDL mid — needs premium)
- Kept: EURUSD 2026-06-16 long (equilibrium → neither premium nor discount → no block)
- The removed trade was the better trade (TP1 = 3R vs SESSION_END = 0.27R)
- Gate B removed the winning trade and kept the break-even runner
- Isolated Gate B finding: quality-negative

### Combined Gates A + B

- Gate A and Gate B filtered different trades (complementary blocking, not redundant)
- Combined result: 0/2 trades pass
- Consistent with ST-D2-6M where 68.8% were removed

---

## §6 — Monthly Breakdown (BASELINE)

| Month | n | PF | WR% | Avg R |
|---|---|---|---|---|
| 2026-06 | 2 | ∞ | 100.0% | 1.598 |
| 2026-05 | 0 | — | — | — |

Note: No trades fired in May 2026. All 2 trades occurred in the final week of the
dataset (June 16–18). This further confirms the extreme sparsity of the sample.

---

## §7 — Key Finding for Gate Decision

1. The 7-week window (2026-05-01 to 2026-06-19) is insufficient for statistical analysis.
   n=2 baseline trades falls below the n=10 floor defined in the trial spec.

2. Both gates independently remove exactly 50% of trades, and their effects are
   orthogonal (they block different trades). Combined, they remove 100%.

3. Gate B specifically removed the better-quality trade (TP1) while keeping the
   lower-quality one (SESSION_END). This is quality-negative in this sample.

4. The accumulated evidence from ST-D2-6M (n=16 baseline, n=5 D2_combined, PF_2x 1.909→0.135)
   and this trial (n=2 baseline, n=0 D1_ALL) consistently points in one direction:
   the D1 context gates as configured do not improve ST-A2.

---

*ST_A2_D1_COMPARISON_REPORT.md | Written 2026-06-25 | TRIAL_ST_A2_D1_001*
