---
Date: 2026-07-12
Author: Lead Architect / Quant (Claude)
Authority: Level 8 — informational evidence. Does not supersede `docs/00_Project/DOC_AUTHORITY.md`.
Scope: ST-B1 mission Tasks 4 (Historical Validation) and 5 (Walk-Forward
Validation). Both BLOCKED — documented per the same discipline as
docs/audit/PHASE4_COST_MODEL_BLOCKER.md: stop, document exactly what's
blocked, never fabricate.
---

# ST-B1 Historical & Walk-Forward Validation — Blocked

## Executive Summary

Neither historical validation (Task 4) nor walk-forward validation (Task 5)
could be executed in this environment. Both require 3+ years of real
EURUSD/GBPUSD OHLC data; this session has no network access to Dukascopy
(the project's only configured historical data source) and no pre-existing
dataset files in the repository. **No trades, no metrics, no verdict were
fabricated.** `scripts/backtest_st_b1.py` was run for real against this
environment and correctly exited with a documented BLOCKED report rather
than inventing output.

## Evidence

1. **No pre-existing dataset**: `data/historical/` does not contain
   `EURUSD_H1.csv`, `EURUSD_M15.csv`, `GBPUSD_H1.csv`, or `GBPUSD_M15.csv`
   (confirmed: `scripts/backtest_st_b1.py`'s real execution reported all
   four as `exists=False`).
2. **Live fetch attempted and blocked**: `scripts/download_dukascopy.py`
   (the project's existing, unmodified data-acquisition tool) was run
   directly against Dukascopy's public feed. Result: `403, message='Forbidden'`
   on every tick-file request, for both a recent month (2026-06) and an
   older month (2023-01) — consistent, not intermittent. This matches the
   exact blocker pattern already documented for live broker access in
   `docs/audit/PHASE4_COST_MODEL_BLOCKER.md`, but for market-data access
   rather than broker credentials — this environment's outbound network
   path does not have standing access to Dukascopy's servers.
3. **The CLI runner behaves correctly under this condition**:
   `python3 scripts/backtest_st_b1.py` was executed for real, detected the
   missing CSVs, wrote a `BLOCKED` report, and exited with code 2 — verified
   directly, not assumed.

## What this means for each task

### Task 4 — Historical Validation: BLOCKED
Cannot run "EURUSD, GBPUSD, H1+M15, full available history, minimum 3
years" without real data. The pipeline that *would* run it
(`strategies.st_b1_backtest.run_backtest()` + `scripts/backtest_st_b1.py`)
is built, tested against synthetic data (54 passing tests across
`strategies/st_b1_simple_pullback.py` and `strategies/st_b1_backtest.py`),
and ready to execute the moment real CSV data is available at
`data/historical/{SYMBOL}_{H1,M15}.csv`.

### Task 5 — Walk-Forward Validation: BLOCKED (same root cause)
24-month train / 6-month test / 4+ rolling windows requires the same
historical dataset Task 4 needs, just sliced differently. Not attempted
independently since it inherits Task 4's blocker exactly — no separate
diagnosis needed.

## Risk

None from this report itself (nothing fabricated). The risk this report
exists to prevent — treating a synthetic-data smoke test as if it were real
validation evidence — is explicitly avoided: every test in
`tests/strategies/` is labeled as proving pipeline *mechanics*, not
producing *evidence*, both in code comments and in the two PRs that
introduced them.

## Recommendation — what the owner must do next

1. Resolve Dukascopy access from an environment that can actually reach
   `datafeed.dukascopy.com` (the deployed VPS, or a local machine) — run:
   ```bash
   python3 scripts/download_dukascopy.py --symbols EURUSD GBPUSD --start 2021-01 --end 2026-06
   ```
2. Convert/place the resulting data as `data/historical/EURUSD_H1.csv`,
   `EURUSD_M15.csv`, `GBPUSD_H1.csv`, `GBPUSD_M15.csv` (H1 aggregation from
   raw ticks not yet automated by this mission — `download_dukascopy.py`
   fetches ticks; an H1/M15 OHLC-building step, analogous to whatever
   ST-A2's own `data/historical/*.csv` pipeline uses, is a prerequisite not
   built as part of this mission and should reuse that existing pipeline
   rather than inventing a second one).
3. Run `python3 scripts/backtest_st_b1.py` for real.
4. Compare `reports/st_b1_metrics.json` against the gate in
   `config/strategies/ST-B1_v1.yaml`. If it passes, proceed to walk-forward
   (Task 5) using the same dataset, sliced into rolling windows. If it
   fails, per the mission's own instruction: "stop optimization and produce
   a failure analysis report" — do not iterate on parameters against the
   same evidence (the CLAUDE.md §0.2 trial-registration discipline applies
   to ST-B1 exactly as it does to ST-A2).

## Priority

High — this is the only remaining step between ST-B1 and either a PASS
(freeze as `ST-B1_v1_FROZEN`) or a documented FAIL, but it is entirely
owner/environment-gated, not an engineering task.

## Estimated effort

Owner time: data fetch (minutes to hours depending on connection, per
`download_dukascopy.py`'s own per-month rate limiting) plus an H1/M15
aggregation step. Once data exists: the backtest run itself is fast
(the pipeline is pure Python, no external calls) — realistically minutes,
not hours, for 3-5 years of two symbols.

## Rollback

N/A — no code changed by this report. `scripts/backtest_st_b1.py` and
`strategies/st_b1_backtest.py` are inert until pointed at real data.

## Dependencies

Task 4 blocks Task 5 (shares the same data dependency). Both block Task 6
(Demo Deployment), which the mission itself explicitly gates on Task 4
passing — not reached, correctly, per that gate.

## Acceptance criteria

- [x] Real fetch attempted against the project's existing, unmodified data tool — not assumed broken without trying
- [x] Exact error evidence captured (403 Forbidden, consistent across two different months)
- [x] The backtest CLI's missing-data behavior verified by an actual run, not assumed
- [x] No trades, metrics, or verdict fabricated for either task
- [x] Precise, actionable next steps for the owner
