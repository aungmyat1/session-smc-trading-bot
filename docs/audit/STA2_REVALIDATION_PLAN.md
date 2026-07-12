---
Date: 2026-07-12
Author: Lead Architect / Quant audit (Claude)
Authority: Level 8 — informational evidence. Does not supersede `docs/00_Project/DOC_AUTHORITY.md`.
Scope: Phase 7 of the System2-first reconciliation program. Preparation only — no live validation executed.
---

# ST-A2 Revalidation Plan

## Executive Summary

ST-A2's best available evidence (`docs/VERDICT_LOG.md`, run `20260621T100458-183aaa`,
n=169, PF_2x=1.025) predates the 2026-07-01 gate change (n>200, net PF>1.25 at
standard AND 2× stress, Sharpe>1.2, MaxDD<15%) and fails it on at least three
independent counts. This plan prepares the evidence pipeline to re-run
validation against the current gate — it does not execute the run. No
strategy parameters are touched; this is measurement infrastructure only.

## Current State

- **Backtest engine**: `scripts/backtest_session_liquidity.py` — real
  chronological bar-by-bar simulation, reuses the exact production
  `strategy.session_liquidity.session_strategy.run_strategy()`. Its own
  hardcoded gate (`PHASE0_MIN_TRADES=100, PHASE0_MIN_PF=1.0`) is stale — the
  pre-2026-07-01 threshold — and `compute_metrics()` does not compute Sharpe
  at all.
- **Cost model**: `config/costs.json` `active_profile: "PLACEHOLDER_vt_markets_assumption"`
  — explicitly labeled unverified; the `vantage_measured` profile exists in
  the schema but is empty (`null`/`null`). `scripts/capture_spreads.py`
  exists and can populate it but has not been run against live Vantage data.
- **Gate config drift**: `config/strategy_catalog.yaml`'s Phase-3 requirement
  fields exist per-strategy; `config/validation.yaml` (a separate, more
  general gate config) still encodes the **old** gate
  (`minimum_trade_count: 50, minimum_profit_factor: 1.0, maximum_drawdown: 10.0`,
  no Sharpe field). Any tooling reading `validation.yaml` instead of the
  current CLAUDE.md §0.3/§0.6 gate would wrongly pass a strategy.
- **Walk-forward / Monte Carlo**: `docs/WALK_FORWARD_RESEARCH_PLAN.md` is a
  plan, not a result — GBPUSD 2021-2023 data is still missing, walk-forward
  "has not run." No Monte Carlo output exists for ST-A2.
- **Trial registration**: `docs/VERDICT_LOG.md`'s last ST-A2 entry is
  2026-07-01. No new trial has been pre-registered since.

## Evidence

| Gate component | Best available evidence | Current gate | Status |
|---|---|---|---|
| n (trade count) | 169 | >200 | **FAIL** |
| PF standard | 1.151 | >1.25 | **FAIL** |
| PF 2× stress | 1.025 | >1.25 | **FAIL** |
| Sharpe | not computed | >1.2 | **FAIL (unmeasured)** |
| MaxDD | 18.72R (not expressed as %) | <15% | **UNKNOWN — needs re-expression** |
| Cost basis | placeholder (unverified) | measured Vantage spread | **FAIL (not measured)** |

## Risk

- Running validation against a placeholder cost model and reporting it as if
  it were gate evidence would be a repeat of the ag-auto-trade pattern
  CLAUDE.md §0.2 exists to prevent — measured costs must land **before** the
  revalidation trial, not be treated as a parallel/optional step.
- Adding Sharpe to `compute_metrics()` changes what the script reports, not
  what it does to the strategy — zero risk to the live deployed runner, which
  does not import this script.

## Recommendation (tasks to prepare, not execute)

1. **Capture measured spreads**: run `scripts/capture_spreads.py` against the
   live Vantage demo feed for EURUSD/GBPUSD/XAUUSD over a representative
   window; populate `config/costs.json`'s `vantage_measured` profile.
   Cross-check the result against CLAUDE.md §0.3's stated ~0.8–1.2 pip
   EURUSD / ~1.2–1.8 pip GBPUSD RT figures — if they disagree materially,
   flag for owner review before using either number.
2. **Verify/replace the cost profile**: switch `active_profile` in
   `config/costs.json` from the placeholder to `vantage_measured` once
   populated. One-line config change, easily reverted.
3. **Add Sharpe to `compute_metrics()`** in `scripts/backtest_session_liquidity.py`
   — additive, does not change trade simulation logic.
4. **Fix `config/validation.yaml`** to match the current gate (n>200, PF>1.25
   both stress levels, Sharpe>1.2, MaxDD<15%) — prevents any tool from
   silently using the stale threshold.
5. **Pre-register the new trial** in `docs/VERDICT_LOG.md` per CLAUDE.md §0.2/§7
   **before** running anything — trial ID, spec version, and the exact gate
   it will be measured against, committed first.
6. **Do not execute the run** as part of this plan — that is a separate,
   explicitly-approved step per CLAUDE.md's "never tune parameters mid-trial"
   discipline; this plan only prepares the measurement pipeline.

## Priority

High — this is the only path to satisfying the user's stated objective
("measurable validation evidence"), but it is research/evidence work, not a
System2 execution-safety fix, so it sequences **after** Phases 3–6 (which
protect and correct the already-running demo) per this program's stated
priority order.

## Estimated effort

| Task | Hours | Complexity |
|---|---|---|
| Capture + verify measured spreads | 2–4 | Low (script exists) |
| Switch cost profile | <1 | Trivial |
| Add Sharpe metric | 2–3 | Low |
| Fix `validation.yaml` gate | <1 | Trivial |
| Pre-register trial in VERDICT_LOG.md | <1 | Trivial |
| **Total (preparation only, excludes the actual backtest run)** | **~6–9 hours** | **Low** |

## Rollback

Every task here is additive or a config value swap (cost profile, gate
thresholds) — trivially revertible via `git revert`. No strategy code touched.

## Dependencies

- None blocking — all preparation tasks are independent of the branch
  reconciliation work in Phases 1–2 and 8.
- The actual backtest run (explicitly out of scope for this plan) depends on
  all five preparation tasks completing first.

## Acceptance criteria

- [x] Every gate component's current status stated with evidence, not assumed
- [x] Preparation tasks enumerated without executing any of them
- [x] No strategy parameters changed; no live validation run performed
