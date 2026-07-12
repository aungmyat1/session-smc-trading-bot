# End-to-End Validation Report

## Scope

This report traces the current implemented flow from a strategy idea through SVOS validation, approval package construction, and demo runtime visibility.

## Current Path

1. Strategy idea / spec
   - Source: `strategy_input/strategy_spec_schema.py` and `config/strategy_catalog.yaml`
   - Input boundary: `strategy_input.validate_strategy` and `svos/application/intake.py`

2. Intake validation
   - Implemented in `svos/application/intake.py`
   - Records a strategy spec and enters `INTAKE` stage.
   - Evidence is persisted by `svos/orchestration/service.py`.

3. Audit stage
   - Implemented in `svos/application/audit.py`
   - Wraps legacy `StrategyValidationPipeline` from `strategy_validation` or `strategy_audit`.
   - Produces an audit report and stage transition.

4. Historical replay
   - Implemented in `svos/application/replay.py`
   - Uses `historical_replay` modules to replay a strategy’s logic against candle history.
   - Writes a stage report and can promote to `HISTORICAL_REPLAY`.

5. Backtest / statistical validation
   - Implemented in `svos/application/backtest.py`
   - Enforces gate evaluation and writes a validation summary.
   - Can promote to `STATISTICAL_VALIDATION` or back to `REFINEMENT`.

6. Robustness validation
   - Implemented in `svos/application/robustness.py`
   - Requires all four robustness checks to pass before promoting to `ROBUSTNESS_VALIDATION`.

7. Virtual demo
   - Implemented in `svos/application/virtual_demo.py`
   - Simulates strategy execution with synthetic ticks to validate drift and execution consistency.
   - Promotes to `VIRTUAL_DEMO` on pass.

8. Approval package creation
   - Implemented in `approval_package/package_builder.py`
   - Requires strategy spec, backtest, replay, risk report, and validation summary.
   - Enforces `PASS` for both `risk_check` and `validation`.

9. Reporting and dashboard exposure
   - `svos/reports/service.py` indexes artifacts and stores them in a content-addressed artifact store.
   - `dashboard/app.py` exposes report endpoints and strategy catalog status.
   - `dashboard/report_service.py` reads report indexes and provides latest report data.
- `application/strategy_service.py` implements a CLI runner for the full six-phase SVOS pipeline, making it a canonical path for validation execution.
### Confirmed implemented

- `svos/application/intake.py` → intake stage
- `svos/application/audit.py` → audit stage
- `svos/application/replay.py` → replay stage
- `svos/application/backtest.py` → statistical validation stage
- `svos/application/robustness.py` → robustness stage
- `svos/application/virtual_demo.py` → virtual demo stage
- `approval_package/package_builder.py` → approval artifact signing
- `svos/reports/service.py` → report artifact registration

### Partial / inferred only

- `svos/orchestration/service.py` persistence mode may choose JSONL or Postgres, but the actual production runtime choice is not confirmed by a dedicated deployment test.
- `dashboard/app.py` exposes an API, but no confirmed pipeline-triggered report generation through `POST /api/reports/generate/all` is verified.
- `dashboard/strategy_service.py` overlay logic does not prove canonical stage/state consistency with `svos/registry/service.py`.
- The demo runtime path in `scripts/run_portfolio.py` is not confirmed as the actual driver for `config/strategy_portfolio.yaml`.

## Missing or inconsistent links

- `application/strategy_service.py` implements a canonical runner for the full intake → virtual demo → approval package generation path, but the README/CI does not clearly designate it as the default validation workflow.
- `config/strategy_portfolio.yaml` may list strategies that are not actually live or approved.
- `dashboard/strategy_service.py` can show strategy-level UI state without guaranteeing the same state is used by the actual promotion and execution pipeline.
- Approval package sealing is implemented, but there is no explicit package registry or deployment ingestion check shown in the codebase.

## Validation status

- The repository supports an end-to-end evidence chain in principle.
- The chain is currently fractured by multiple duplicate pipelines and by lack of a single authoritative orchestrator that is exercised in a full, reproducible path.
- To validate end to end, the repository needs:
  - a canonical runner for SVOS pipeline execution,
  - explicit integration between the catalog, lifecycle registry, and demo runtime,
  - a documented command or CI step that executes the entire flow and verifies output artifacts.
