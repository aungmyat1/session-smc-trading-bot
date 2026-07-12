---
Date: 2026-07-12
Author: Lead Architect / Quant (Claude)
Authority: Level 8 — informational evidence. Does not supersede `docs/00_Project/DOC_AUTHORITY.md`.
Scope: Phase 6 of the System2 Completion Mission. Preparation only — no
strategy modification, no backtest executed, per the mission's explicit
"Do NOT optimize strategy. Do NOT modify strategy... prepare deterministic
validation."
---

# ST-A2 Revalidation — Ready-to-Run Package

## Executive Summary

This document locks every parameter a revalidation run needs so it can be
executed deterministically by whoever has the environment to run it (real
market data, sufficient runtime). **No backtest was executed as part of this
phase.** The strategy itself is unmodified — this is a specification lock,
not new research.

## New Trial ID

```
ST-A2-REVAL-20260712-P0X
```

Following the existing convention (`YYYYMMDD` + a short suffix distinguishing
it from same-day trials). Per CLAUDE.md §0.2/§7, **this ID must be
pre-registered in `docs/VERDICT_LOG.md` before the run executes** — this
document is the specification for that registration, not the registration
itself (registration is a deliberate, separate act by whoever runs the
trial, consistent with "pre-register the spec BEFORE running the
backtest").

## Locked: Strategy specification (unmodified)

- **Code**: `strategy/session_liquidity/` (unchanged) — same chain that
  produced the `20260621T100458-183aaa` PASS-under-old-gate result.
- **Config**: `session_strategy.py` `DEFAULT_CONFIG` + `min_sl_pips=5.0`
  post-`build_signal()` reject gate (the exact spec of the last completed
  run, per `docs/VERDICT_LOG.md` line 32) — **no parameter changes**.
- **Backtest engine**: `scripts/backtest_session_liquidity.py`, unmodified
  by this mission (its hardcoded gate constants are a separate, documented
  issue — `SYSTEM2_VALIDATION_GATE_REPORT.md` — not touched here since this
  phase must not change gate values).

## Locked: Dataset

- **Symbols**: EURUSD, GBPUSD — matching `config/strategy_catalog.yaml`'s
  ST-A2 `symbols` list (note: this differs from `config/strategy_portfolio.yaml`,
  which also trades ST-A2 on XAUUSD in the deployed runner — an existing,
  separate inconsistency, not resolved here; the revalidation trial should
  match the catalog's registered symbol list, not the portfolio config,
  since the catalog is the approval source of truth per governance).
- **Timeframes**: M15, H4 (per `strategy_catalog.yaml`).
- **Window**: the prior authoritative PASS (`20260621T100458-183aaa`, n=169)
  used a 5-year EUR+GBP window. **n=169 < the current gate's n>200
  requirement** — reusing the identical window would not clear the trade-
  count bar on its own. Two options, neither decided here (owner/quant
  call):
  1. Extend the window beyond 5 years (exact extension needed to plausibly
     reach n>200 is not calculable without running it — flagged, not
     estimated, to avoid fabricating a number).
  2. Use `docs/VERDICT_LOG.md`'s own next-recommended step,
     "ST-A2-REPLAY-5YR" (2021-2023 Dukascopy expansion, mentioned but not
     yet executed as of the last log entry found) as the basis, once that
     data is actually available.
- **Data source**: Dukascopy via `scripts/download_dukascopy.py` /
  `scripts/fetch_data.py` — **not present in this sandbox** (no market data
  files found under `data/`); must be fetched in the environment that
  actually runs the trial.

## Locked: Cost profile — BLOCKED

Per `docs/audit/PHASE4_COST_MODEL_BLOCKER.md`, no measured Vantage cost data
exists. **The trial must not run against the placeholder profile
(`config/costs.json`'s `PLACEHOLDER_vt_markets_assumption`) and be reported
as gate evidence** — that would repeat exactly the pattern CLAUDE.md §0.2
exists to prevent. This is the one genuinely blocking prerequisite: Phase 4
must be unblocked (owner runs `scripts/capture_spreads.py` for real) before
this trial's result can be trusted as gate evidence. A run against the
placeholder is only useful as a pipeline/mechanics smoke test, and must be
labeled as such, not as a gate attempt.

## Locked: Validation gate (target — measured against, not modified)

Per CLAUDE.md §0.3/§0.6, unchanged by this mission (`SYSTEM2_VALIDATION_GATE_REPORT.md`):

```
n > 200
net PF > 1.25 at BOTH standard AND 2× spread stress
Sharpe > 1.2
MaxDD < 15%
```

**Sharpe is not currently computed anywhere in `scripts/backtest_session_liquidity.py`'s
`compute_metrics()`** (confirmed, prior sprint's audit) — this must be added
before the trial runs, or the trial cannot be evaluated against the full
gate. This is a code change to the backtest *engine's reporting*, not the
*strategy*, so it does not conflict with this phase's "do not modify
strategy" instruction — but it is not performed here either, since it's
outside Phase 6's own scope (preparation of the spec, not the tooling).

## Locked: Seed

**Not applicable.** `scripts/backtest_session_liquidity.py` contains no
randomness (confirmed: no `random`, `np.random`, or `seed` references
anywhere in the file) — the simulation is fully deterministic given fixed
input data and parameters. There is nothing to seed.

## Preconditions before this trial can actually run (checklist)

- [ ] Phase 4 cost model blocker resolved (real Vantage spread data captured)
- [ ] Sharpe added to `compute_metrics()`
- [ ] Dataset window decision made (extend 5yr window, or use the
      already-planned 5-year Dukascopy real-data replay once available)
- [ ] Trial ID `ST-A2-REVAL-20260712-P0X` (or a corrected version of it)
      pre-registered in `docs/VERDICT_LOG.md` with this exact locked spec,
      **before** execution
- [ ] Explicit owner go-ahead to execute (this document prepares; it does
      not authorize execution)

## Risk

Running this trial before the cost-model blocker clears would produce a
result that looks authoritative but isn't — the single highest risk this
document exists to prevent. The checklist above is ordered to make that
mistake structurally harder (cost model first, before "just run it").

## Recommendation

Do not execute until every checklist item is checked. Once checked, execution
itself is a single, previously-scoped step (`STA2_REVALIDATION_PLAN.md`'s
"Estimated effort" section, prior sprint: ~4-8 hours for the run + result
review, separate from preparation time).

## Priority

Medium-high — this is the specification that eventually produces the
"measurable validation evidence" the original project objective calls for,
but it is explicitly gated on Phase 4 (owner action) first.

## Estimated effort

Preparation (this document): complete. Remaining before execution: per
`STA2_REVALIDATION_PLAN.md`, ~6-9 hours of preparation work (spread capture,
Sharpe metric, dataset decision) plus the run itself.

## Rollback

N/A — no code or strategy changed in this phase. This document itself can
be revised without any runtime impact.

## Dependencies

- Phase 4 (cost model) — blocking.
- `SYSTEM2_VALIDATION_GATE_REPORT.md` — informs but does not block (the
  gate's *documented* value is used as the measurement target regardless of
  whether `config/validation.yaml` itself has been updated to match it).

## Acceptance criteria

- [x] New trial ID assigned, following the existing convention
- [x] Dataset, parameters, cost profile, validation gate, and seed each
      explicitly addressed — including stating plainly where a lock isn't
      yet possible (cost profile, dataset window) rather than fabricating one
- [x] No strategy modification, no optimization, no backtest executed
- [x] Explicit precondition checklist before execution is authorized
