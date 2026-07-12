---
Date: 2026-07-12
Author: Lead Architect (Claude)
Authority: Level 8 — informational evidence. Does not supersede `docs/00_Project/DOC_AUTHORITY.md`.
Scope: Final summary of the ST-B1 Simple Trend Pullback mission.
---

# ST-B1 Mission Summary

## Status: DRAFT / INTAKE — not deployed, not validated, not a replacement for ST-A2 today

Per the mission's own gated structure ("If historical validation passes:
Deploy..."), and since historical validation (Task 4) is **blocked**, not
failed, Task 6 (Demo Deployment) was correctly not attempted. **ST-A2
remains the sole live demo strategy** (`smc-demo-runner.service`); nothing
in this mission touched `config/strategy_portfolio.yaml`,
`config/strategy_catalog.yaml`, or any execution-path code.

Important distinction: **"blocked" is not "failed."** ST-B1 has not been run
against real data and therefore has no PASS or FAIL verdict — it is
untested against the gate, not proven inadequate. The mission's own
"failure analysis" instruction applies only after a real run fails the
gate; that condition hasn't occurred.

## What was built (all tested, all real)

| Component | File | Tests |
|---|---|---|
| Strategy registry | `config/strategies/ST-B1_v1.yaml` | — (config) |
| Strategy engine | `strategies/st_b1_simple_pullback.py` | 36 |
| Backtest driver + CLI | `strategies/st_b1_backtest.py`, `scripts/backtest_st_b1.py` | 18 |
| **Total** | | **54 tests, all passing** |

The strategy engine produces `shared.strategy_api.signal.Signal` objects —
the same canonical contract `execution/trade_manager.py` already consumes —
so if ST-B1 ever clears validation, no execution-layer adapter work is
needed to run it. This was a deliberate design choice, not an accident.

## What was blocked (documented, not fabricated)

| Task | Status | Reason |
|---|---|---|
| 4. Historical Validation | BLOCKED | No real EURUSD/GBPUSD data reachable — Dukascopy returns 403 Forbidden from this environment (verified directly, two different months) |
| 5. Walk-Forward Validation | BLOCKED | Inherits Task 4's data dependency |
| 6. Demo Deployment | NOT ATTEMPTED (correctly) | Explicitly gated on Task 4 passing, per the mission's own instructions |

See `docs/audit/ST_B1_VALIDATION_REPORT.md` for full evidence and exact
owner next steps.

## PRs from this mission

| PR | Content |
|---|---|
| #44 | Strategy registry, engine, 36 unit tests |
| #45 | Backtest driver, CLI, 18 unit tests |
| *(this)* | Validation/walk-forward blocker report + this summary |

## Recommended next step

Owner runs the real Dukascopy fetch from an environment with network
access (VPS or local machine), places the resulting H1/M15 CSVs at
`data/historical/`, and runs `python3 scripts/backtest_st_b1.py`. That
single command produces the PASS/FAIL verdict this mission's Task 4-6 gate
depends on — everything upstream of that command is now built and tested.

## Explicit non-actions (so this isn't mistaken for silent scope-cutting)

- `config/strategy_portfolio.yaml` / `config/strategy_catalog.yaml`: not
  touched. ST-B1 is not enabled, not current, not approved.
- No integration with `research/research_queue.py` or the experiment
  framework — noted as unstarted work, not attempted and not claimed done.
- No parameter tuning or optimization performed or implied — the strategy
  spec matches the mission's definition exactly, unmodified.
