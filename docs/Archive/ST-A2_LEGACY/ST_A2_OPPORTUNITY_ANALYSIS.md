# ST-A2 Opportunity Analysis
# Research-07 — Backtest Segment Decomposition
# Based on: ST_A2_CONFIRMATION.md | BACKTEST_RESULTS.md | EXPERIMENT_RESULTS.md
# Date: 2026-06-23 | Strategy version locked — no modifications

---

## Purpose

Decompose the ST-A2 combined result (169 trades, PF_2x=1.025) into its constituent
segments to understand which pairs and sessions are generating edge, which are
consuming it, and where monitoring focus should be concentrated during the
30-day paper trade (DEP-02).

**Source data only.** No strategy code was run. No parameters were changed.
All figures are drawn from existing backtest outputs.

---

## 1. EURUSD-Only Performance

| Metric | Standard Spread | 2× Spread Stress |
|---|---|---|
| Trades | 105 | 105 |
| Win Rate | 29.5% | 29.5% |
| Average R | +0.044 | −0.045 |
| Net PF | 1.059 | **0.945** |
| Max DD | 14.00 R | 18.20 R |
| Total R | +4.61 | −4.67 |

**Assessment: MARGINAL — fails Phase-0 gate independently.**

EURUSD clears standard spread (1.059 > 1.0) but falls below at 2× stress (0.945 < 1.0).
Average R of +0.044 at standard spread is thin: a single basis-point increase in effective
spread cost erodes it entirely. EURUSD's contribution to the combined PF is real but fragile.

**Implication for paper trade:** Monitor EURUSD separately. If paper-trade win rate falls
below 25% over ≥20 EURUSD trades, flag immediately. Max DD of 14R at standard spread
is already high given a 1% risk-per-trade account.

---

## 2. GBPUSD-Only Performance

| Metric | Standard Spread | 2× Spread Stress |
|---|---|---|
| Trades | 64 | 64 |
| Win Rate | 35.9% | 34.4% |
| Average R | +0.214 | +0.124 |
| Net PF | 1.313 | **1.168** |
| Max DD | 9.70 R | 11.02 R |
| Total R | +13.67 | +7.96 |

**Assessment: STRONG — passes gate independently at both spread levels.**

GBPUSD is the strategy's primary profit engine. It contributes 13.67 R vs EURUSD's
4.61 R on 40% fewer trades. PF_2x=1.168 comfortably exceeds the 1.0 threshold with
margin. Lower max DD (9.70 R) despite RR5 suggests the win-rate of 35.9% is meaningfully
above the minimum required for RR5 profitability (~18%).

**Implication for paper trade:** GBPUSD performance is what the combined result depends on.
A GBPUSD win rate below 30% over ≥20 trades would be the primary concern.

---

## 3. London Session-Only Performance

| Metric | Standard Spread |
|---|---|
| Trades | 118 |
| Win Rate | 28.0% |
| Net PF (std) | **0.949** |

*(2× spread data not explicitly available for London isolation; derivable as worse.)*

**Assessment: NET LOSER at standard spread (PF < 1.0).**

London generates 70% of all ST-A2 trades (118/169) but produces a net-losing result
at standard spread (0.949). This means the London session is a consistent drag:
without NY, the strategy fails. The 28.0% win rate on a 5R target is below the
theoretical minimum for breakeven after fees (~22% at 0 fees, higher with spread).

**Known sub-segment drag:** GBPUSD London is identified by EXP-04 as the single
largest drag (44 trades). Removing GBPUSD London alone is sufficient to bring the
combined PF_2x from 0.965 (ST-A) to 1.059 (EXP-04). See Section 7.

---

## 4. New York Session-Only Performance

| Metric | Standard Spread |
|---|---|
| Trades | 51 |
| Win Rate | 41.2% |
| Net PF (std) | **1.731** |

*(EXP-03 NY-only result at RR5: Net PF std 1.571, 2× 1.381, n=53 — from ST-A base;
ST-A2 NY trades = 51 due to 2 trades removed by ≥5pip SL floor.)*

**Assessment: STRONG EDGE. The New York session is where the strategy's edge lives.**

PF of 1.731 at standard spread is robust. Win rate of 41.2% on RR5 is significantly
above the minimum for profitability. Even at 2× spread stress (EXP-03 base: 1.381),
the NY edge is durable. The NY session contributes +13.67 R in total (matching GBPUSD
total R — suggesting GBPUSD NY is the dominant profit source).

**Implication:** NY session trades deserve priority attention. If NY stops working
(win rate drops below 35% over 20+ trades), the entire strategy edge is gone.

---

## 5. EURUSD + New York Combined Performance

No explicit cross-tabulated figure (EURUSD NY only) exists in backtest outputs.
However, it can be bounded by reasoning from available data:

| Segment | Trades | Direction |
|---|---|---|
| NY total (all pairs) | 51 | High-edge session |
| EURUSD total | 105 | Low-edge pair |
| GBPUSD total | 64 | High-edge pair |
| GBPUSD London | ~44 | Primary drag |
| GBPUSD NY | ~20 (derived: 64 − 44) | — |
| EURUSD London | ~74 (derived: 118 − 44) | — |
| EURUSD NY | ~31 (derived: 51 − 20) | — |

**Derivation note:** GBPUSD London = 44 from EXP-04 (44 trades removed, all from London).
These figures are approximate — the backtest outputs do not cross-tabulate symbol × session.

**EURUSD NY estimate:** ~31 trades of 51 NY total.
- NY PF=1.731 is the combined EURUSD+GBPUSD NY result.
- GBPUSD is the stronger pair (PF 1.313 overall vs 1.059 EURUSD).
- EURUSD NY is likely below the 1.731 combined NY figure but above EURUSD London.
- A conservative estimate: EURUSD NY PF is between 1.1–1.4 (positive, but not dominant).

**Conclusion:** EURUSD NY is a positive contributor but not the segment to optimize.
The actionable insight is the clear hierarchy: GBPUSD NY > EURUSD NY > EURUSD London >
GBPUSD London.

---

## 6. Which Segment Contributes Most Profit?

**Answer: New York session, driven by GBPUSD.**

Evidence:
1. **NY session: PF 1.731** vs London 0.949 (net loser at standard spread).
2. **GBPUSD: +13.67 R total** vs EURUSD +4.61 R — on 40% fewer trades.
3. **EXP-03 (NY only)**: removing London entirely improved PF_2x from 0.965 → 1.381.
4. **GBPUSD NY** (~20 trades, per derivation) is the highest R/trade segment in the data.

The strategy's PF is essentially: NY edge pays for London losses, leaving a net
positive of PF_2x=1.025. This is a thin margin — 2.5% above breakeven.

---

## 7. Which Segment Contributes Most Drawdown?

**Answer: GBPUSD London (absolute), EURUSD 2× stress (ratio).**

### Drawdown by segment (from backtest data)

| Segment | Max DD | Context |
|---|---|---|
| EURUSD | 14.00 R (std) / 18.20 R (2×) | 105 trades; stress worsens significantly |
| GBPUSD | 9.70 R (std) / 11.02 R (2×) | 64 trades; lower DD despite winning pair |
| Combined | 18.72 R (std) | Sequential ordering of losses across pairs |

### EXP-04 reveals the structural cause

EXP-04 (exclude GBPUSD London) reduced Max DD from 28.14 R (ST-A base) to 21.49 R
while improving PF_2x from 0.965 to 1.059. This implies GBPUSD London draws down
significantly before occasionally recovering — consistent with a 28% win rate on
a 5R target in a session where the pair lacks clean range structure.

### Key risk: EURUSD under stress

EURUSD average R flips from +0.044 (std) to −0.045 (2× stress). This means at 2×
spread, EURUSD is negative expectancy. During live spread widening events (news,
low liquidity), EURUSD trades will underperform the backtest materially.

---

## 8. Segment Priority Matrix

| Segment | Edge | DD Risk | Paper-Trade Priority |
|---|---|---|---|
| GBPUSD NY | HIGH | LOW | 🟢 Primary edge — monitor for continuation |
| EURUSD NY | MEDIUM | MEDIUM | 🟡 Positive, thin margin |
| EURUSD London | LOW | HIGH | 🟠 Watch closely; EURUSD 2× = negative |
| GBPUSD London | NEGATIVE | HIGH | 🔴 Primary drag — consider ST-A3 filter |

---

## 9. Risks Discovered

### RISK-A: Strategy is NY-dependent

If NY session characteristics change (increased volatility, lower sweep frequency,
regulatory changes), the combined result deteriorates below gate even if London is stable.
The strategy has no redundant source of edge — it's a single-session driver.

### RISK-B: GBPUSD London is load-bearing (negatively)

The strategy currently "uses" GBPUSD London trades as frequency padding. The 44
GBPUSD London trades reduce PF but increase n toward the statistical requirement.
If GBPUSD London is ever filtered (as EXP-04 proposes), n drops to 137 — still
above the 100-trade gate, but frequency falls further (~27/year).

### RISK-C: EURUSD fragility at 2× spread

EURUSD PF_2x=0.945 means any live spread widening above 1.4 pip (VT standard)
on EURUSD will push it into net-negative territory. High-impact news events, Asian
open liquidity gaps, or VT Markets spread widening could make EURUSD consistently
unprofitable in live trading.

### RISK-D: Low sample count per segment

| Segment | Annual trades (estimated) |
|---|---|
| GBPUSD NY | ~4–5 |
| EURUSD NY | ~6–7 |
| EURUSD London | ~15–16 |
| GBPUSD London | ~9 |

At 3–5 trades per segment per year, detecting segment-level underperformance in a
30-day paper trade is statistically impossible. Paper-trade monitoring can only catch
catastrophic failure (win rate near 0%) — not marginal drift.

---

## 10. Recommended Next Steps

1. **Register paper-trade monitoring thresholds** — per segment alerts when n ≥ 10:
   - GBPUSD NY win rate < 35% → ALERT
   - London win rate < 20% → ALERT (already expected ~28%)
   - EURUSD streak of 5 losses → ALERT

2. **Potential ST-A3 trial (DO NOT implement now):** Filter GBPUSD London when
   ADX(14) > 25 (strong trend — EXP-04 rationale). Register in VERDICT_LOG before
   any backtest. This is PENDING ST-A2 paper trade results.

3. **Do not run NY-only optimization** — EXP-03 passed gate (n=53) but trade count
   is too low for statistical validity. Optimizing for NY only would create a narrow,
   overfitted signal that may not generalize.

---

*Data sources: BACKTEST_RESULTS.md | ST_A2_CONFIRMATION.md | EXPERIMENT_RESULTS.md*
*Run IDs: ST-A2 = 20260621T100458-183aaa | ST-A = 20260621T060745-f6ac57*
*No strategy code modified. Research only.*
