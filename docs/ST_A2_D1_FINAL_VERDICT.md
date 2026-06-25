# ST_A2_D1_FINAL_VERDICT.md
# TRIAL_ST_A2_D1_001 — Final Verdict
# Date: 2026-06-25

---

## Verdict

```
┌─────────────────────────────────────────────────────┐
│                                                     │
│   FAIL                                              │
│                                                     │
│   D1 context layer (Gates A + B combined) does not  │
│   improve ST-A2. Over-filters to zero in 7-week     │
│   window. Consistent with ST-D2-6M (6-month) result.│
│                                                     │
└─────────────────────────────────────────────────────┘
```

**Choose one:**
- [ ] KEEP ST-A2 BASELINE
- [ ] ENABLE D1 CONTEXT
- [ ] REQUIRES MORE TESTING
- [x] **FAIL**

---

## Gate Decision Table

| Criterion | Target | D1_ALL Result | Verdict |
|---|---|---|---|
| PF_2x improves | > BASELINE PF_2x | n=0, undefined | ❌ FAIL |
| Trade count floor | n(D1_ALL) ≥ 10 | n=0 | ❌ FAIL |
| Trade frequency | n ≥ 0.5 × BASELINE | n=0 vs n=2 | ❌ FAIL (100% filtered) |
| Drawdown reduces | < BASELINE MaxDD | n=0, N/A | INCONCLUSIVE |

**Result: FAIL (three gate conditions breached simultaneously)**

---

## Evidence Summary

### This trial (7-week window, 2026-05-01 → 2026-06-19)

| Variant | n | PF_2x | Gate A action | Gate B action |
|---|---|---|---|---|
| BASELINE | 2 | ∞ | — | — |
| D1_BIAS | 1 | ∞ | Removed EUR long (D1 bearish vs 4H bullish) | — |
| D1_LOCATION | 1 | ∞ | — | Removed GBP short (bearish in discount zone) |
| D1_ALL | **0** | **—** | Both trades removed by joint filtering | |

Note: n=2 baseline is below the statistical floor (n<10). This window alone
cannot determine edge direction. The gates are mechanically correct; the n=0
outcome reflects trade sparsity AND joint over-filtering.

### Prior evidence (ST-D2-6M, 6-month window, 2026-01-01 → 2026-06-19)

| Variant | n | PF_2x | Change |
|---|---|---|---|
| BASELINE | 16 | 1.909 | — |
| D2_COMBINED (≡ D1_ALL) | 5 | 0.135 | ↓ −93% |

Over 6 months with n=16 baseline trades, the equivalent combined gate:
- Removed 68.8% of signals (11 of 16)
- Destroyed PF_2x from 1.909 to 0.135
- Reduced WR from 50.0% to 20.0%

The 6-month window is statistically more informative. Both windows show the
same directional result: combined D1 gates harm ST-A2.

---

## Why D1 Gates Over-Filter

Two independent mechanisms:

**Gate A (D1 bias vs 4H bias):** ST-A2 already has a 4H+1H bias filter.
The D1 structure adds a third timeframe requirement. The daily timeframe often
develops a different swing structure than the 4H+1H bias, especially around
key weekly levels. When the daily close sequence establishes a bearish structure,
the 4H may still be bullish — this produces a Gate A conflict that blocks
otherwise valid intraday setups. The conflict rate appears to be ~50% of trades
in the 6-month and 7-week windows.

**Gate B (location vs PDH/PDL midpoint):** This gate requires price to be in
discount (long) or premium (short) relative to the previous day's midpoint.
The problem: ST-A2 sweeps session lows (for longs) and session highs (for shorts).
A session low sweep can occur at ANY price level relative to the PDH/PDL range.
If price is trading between the PDH/PDL midpoint and the session high/low,
Gate B will block the trade even though the sweep is valid. The gate's logic
may be directionally inverted for sweep-based entries: a bullish sweep reversal
that occurs near the PDH (i.e., in the "premium" zone relative to yesterday's range)
is blocking — but PDH proximity is actually a valid area for a weekly range high
sweep targeting the discount below.

**Combined effect:** The two gates filter different trades, so their joint
application compounds the individual removal rates. With ~50% removal per gate
on independent signals, the combined removal approaches 75–100%.

---

## What This Does NOT Mean

- ST-A2 is still valid. The Phase-0 result (n=169, PF_2x=1.025) stands unchanged.
- D1 daily analysis is not inherently useless — the hypothesis is sound conceptually.
  The specific implementation (Gate A as written, Gate B as written, combined) is
  what fails.
- The framework built here (`session_smc/daily_context.py`) is correct and reusable
  for future trials with refined gate logic.

---

## What Changes (Authorized)

Nothing changes in the ST-A2 execution pipeline. The `BASELINE` config
(`d1_context_enabled=False`) remains the canonical ST-A2 behavior.

The E6 cost revalidation pipeline (`run_e6_revalidation.sh`) is unaffected.

---

## Recovery Path (if D1 hypothesis is to be re-tested)

The following are NEW trials — each requires a new VERDICT_LOG entry before running:

| Option | Description | Prerequisite |
|---|---|---|
| ST-D2-5YR | Run D1_ALL on full 5yr dataset (2021-2026) | Register `TRIAL_ST_A2_D2_5YR_001` |
| ST-A2-D1-GATE-A-ONLY-5YR | Gate A alone on 5yr | Lower priority: 6mo showed Gate A keeps 50% of trades, quality unclear |
| ST-A2-D1-LOC-REVISED | Revise Gate B logic: premium for shorts means price between session mid and PDH, not PDH/PDL mid | Rethink gate direction for sweep-based entries |
| TRIAL_ST_A2_D1_POI_001 | Gate C (POI) on top of revised A+B | After Gates A and B are individually validated |

No modification of existing code without registering the trial first.

---

## Appendix — Mechanically Tested Claim

The gates work correctly. The verdict is not that the code is wrong — it is that
the gates' logic, at these threshold settings, removes too many valid ST-A2 signals.

Gate A blocked the EURUSD long on 2026-06-16: D1 was bearish (D1 swing LL+LH confirmed)
while the 4H+1H intraday bias was bullish. The block is mechanically correct per the
gate definition. Whether the D1 bearish reading should override a valid 4H setup is
the strategic question — and the evidence says: no, it should not (not at this removal rate).

Gate B blocked the GBPUSD short on 2026-06-18: the short trade required a "premium"
D1 location (price above D1 midpoint), but price was in equilibrium/discount. The
block is mechanically correct. But the GBPUSD short hit TP1 at 3R — it was a high-
quality trade that the gate removed.

---

*ST_A2_D1_FINAL_VERDICT.md | Written 2026-06-25 | TRIAL_ST_A2_D1_001*
*See also: ST_A2_D1_COMPARISON_REPORT.md | ST_A2_D1_IMPLEMENTATION_REPORT.md | TRIAL_ST_A2_D1_SPEC.md*
