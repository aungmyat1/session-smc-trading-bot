# E6_DECISION_MATRIX.md
# ST-A2 — E6 Cost Revalidation Decision Matrix
# Written: 2026-06-24

---

## Purpose

This matrix translates E6 backtest results into a single, unambiguous action.
Apply it immediately after `python3 scripts/compare_e6_to_baseline.py` runs.

No subjective interpretation. The rules are fixed. Apply them mechanically.

---

## Primary Gate: Net PF (2×) at RR 5

This is the only metric that determines the E6 outcome. Everything else is context.

| PF_2x Result | Outcome | Action |
|---|---|---|
| ≥ 1.05 | ✅ **PASS** | Proceed to E1–E4 execution gate |
| 1.02–1.05 | ✅ **PASS** | Proceed to E1–E4; no special monitoring needed |
| 1.00–1.02 | ⚠️ **REVIEW** | Proceed to E1–E4; activate GBPUSD spread monitoring |
| < 1.00 | ❌ **REJECT** | STOP. Do not proceed to demo. Write ST_A3_RECOVERY_OPTIONS.md |

### Rationale for Each Band

**≥ 1.05 (PASS — comfortable)**
The strategy has a 5% buffer above the gate after measured costs. Normal market
variation in spreads (up to 15%) would not erode the edge. No additional monitoring
required beyond standard demo tracking.

**1.02–1.05 (PASS — standard)**
Sufficient margin. The PRE_E6_BASELINE was at 1.025 with placeholder costs.
If measured costs are slightly lower, landing here is the expected outcome.
Proceed normally.

**1.00–1.02 (REVIEW — thin margin)**
The strategy survives measured costs but by a narrow margin (< 2 pip-equivalent buffer).
This means execution slippage, spread widening at news events, or one bad month could
push live performance below breakeven. The edge exists, but robustness is reduced.

Proceed to E1–E4 with these additional checks during the execution gate:
- Log actual spread at every trade entry (via MetaAPI fill price vs signal price)
- If actual trade costs exceed modeled costs by >0.2 pip for 5+ consecutive trades, pause
- Monitor GBPUSD specifically — it carries the combined pass; any spread widening matters

**< 1.00 (REJECT)**
The strategy does not have a measurable edge after real transaction costs.
Phase-0 gate requires PF_2x > 1.00. This result means the PLACEHOLDER assumption
was too optimistic and the real account would be expected to lose money over time.

Do NOT proceed to demo. Register in VERDICT_LOG.md as a FAIL outcome for E6,
then evaluate recovery options (see Recovery section below).

---

## Secondary Checks (context only — do not override the primary gate)

Run these AFTER the primary gate passes. They inform monitoring priorities
during E1–E4, not the E6 pass/fail decision.

### Trade Count Integrity

| Result | Interpretation | Action |
|---|---|---|
| Exactly 169 | ✅ Normal — costs don't affect signals | None |
| ≠ 169 | ❌ Pipeline error | STOP — investigate before proceeding |

If trade count changes, the cost injection likely failed or there was a data issue.
Do not proceed until the cause is understood.

### Win Rate Stability

| Result | Interpretation | Action |
|---|---|---|
| ≈ 32.0% (±0.5pp) | ✅ Normal | None |
| Outside ±0.5pp | ⚠️ Unexpected | Investigate; should not happen from cost change alone |

Win rate is determined by signal quality (sweeps, CHoCH, BOS) — not by spread cost.
Any material change indicates a code or data problem, not a strategy issue.

### EURUSD Pair Viability

| EURUSD PF_2x | Interpretation | Action during E1–E4 |
|---|---|---|
| ≥ 1.00 | Both pairs viable | Trade both pairs normally |
| 0.90–1.00 | EURUSD marginal drag; GBPUSD compensates | Trade both; note EUR underperformance |
| < 0.90 | EURUSD material drag | Trade both for E1–E4; flag EUR for ST-A3 review |

See `docs/E6_PAIR_ANALYSIS.md` for full pair breakdown.

### London Session Viability

| London PF (std) | Interpretation | Action during E1–E4 |
|---|---|---|
| ≥ 1.00 | London self-sustaining | Trade both sessions normally |
| 0.90–1.00 | Marginal drag; NY compensates | Trade both; note London underperformance |
| < 0.90 | London material drag | Trade both for E1–E4; flag NY-only for ST-A3 |

See `docs/E6_SESSION_ANALYSIS.md` for full session breakdown.

---

## E6 Verdict Recording

After applying this matrix, record the outcome in two places:

### 1. docs/VERDICT_LOG.md — sub-entry under ST-A2

```
ST-A2 (E6 revalidation) | <date> | Same signal spec as ST-A2.
Cost profile: PLACEHOLDER → vantage_measured
(EURUSD std=X.XX pip / GBPUSD std=X.XX pip, measured 2026-06-24 to 2026-06-30)
Results: n=169, PF_std=X.XXX, PF_2x=X.XXX | PASS / REVIEW / REJECT
Action: [proceed to E1 | proceed with monitoring | stop — ST_A3]
```

### 2. docs/BACKTEST_COST_REVALIDATION_REPORT.md — populate the template

Fill the "E6 Decision" section with the outcome from this matrix.

---

## Recovery Options (if REJECT)

If PF_2x < 1.00, prepare `docs/ST_A3_RECOVERY_OPTIONS.md` with these candidates
(each requires a new trial registration — none are authorized here):

| Option | Hypothesis | Risk |
|---|---|---|
| ST-A3a: NY-only | Remove London (PF_std 0.949 at placeholder). NY alone: PF_std=1.731, n=51 (5yr) | n=51 is below the 100-trade gate; ~10 trades/year — thin statistics |
| ST-A3b: GBPUSD-only | GBPUSD PF_2x=1.168 at placeholder costs. Measured costs likely improve this | n=64 over 3.3yr — marginal count |
| ST-A3c: Raw account switch | Vantage Raw ECN: ~0.7–0.9 pip all-in vs 1.4–1.8 pip Standard. Backtest with raw costs | Requires re-measuring on Raw account |
| ST-A3d: Spread filter | Only enter when live spread ≤ threshold pip | Reduces trade count further; needs new backtest |

None of these are a "fix" to ST-A2. Each is a new strategy specification requiring
Phase-0 re-registration and new backtest before any execution.

---

## What This Matrix Does NOT Authorize

- Modifying strategy code (entries, exits, filters, indicators)
- Changing risk parameters (RR, SL, TP, position sizing)
- Re-optimizing parameters to make PF_2x ≥ 1.00 if the E6 result is REJECT
- Proceeding to demo on a REJECT verdict regardless of other considerations

If PF_2x < 1.00, the correct response is to stop and start a new trial.
Optimizing parameters to pass the gate would repeat the ag-auto-trade graveyard pattern
(29 tuned variants, none of which had a real edge).

---

## Current E6 Status

| Item | Status |
|---|---|
| Gate (E5 collection) | ⏳ OPEN 2026-06-30 (~4 London + 4 NY sessions remaining) |
| E6 pipeline | ✅ READY (`bash scripts/run_e6_revalidation.sh`) |
| PRE_E6_BASELINE | ✅ FROZEN (docs/PRE_E6_BASELINE.md) |
| This matrix | ✅ READY — apply on 2026-06-30 after E6 runs |
| compare_e6_to_baseline.py | ✅ READY — auto-applies primary gate and classifies metrics |

---

*E6_DECISION_MATRIX.md | Written 2026-06-24 | Apply after E6 pipeline completes (~2026-06-30)*
