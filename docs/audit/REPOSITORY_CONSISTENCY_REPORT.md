# Repository Consistency Report

## Summary

This report compares the current repository implementation against the declared project objective, architecture, structure, tests, dashboard, reports, and deployment artifacts.

The repository is architecturally aligned with the Strategy Engineering Platform objective and the Phase 5 implementation ceiling. The core SVOS lifecycle, governance, registry, and reporting foundations are implemented. However, there are several consistency gaps in stage vocabulary, execution wiring, deployment separation, and test coverage.

## Project Objective vs. Implementation

### Consistent items

- The repository targets Python 3.12 and defines a modular Strategy Engineering Platform in `docs/SYSTEM_ARCHITECTURE.md` and `docs/svos/STRATEGY_ENGINEERING_PLATFORM_IMPLEMENTATION_PLAN.md`.
- The platform objective is to accept a strategy input, qualify it through audit/replay/backtest/robustness/virtual demo, and optionally produce a versioned approval package.
- `svos/lifecycle/manager.py`, `svos/governance/service.py`, `svos/registry/service.py`, and `svos/orchestration/service.py` embody the governance and lifecycle authority described in the architecture documents.
- A canonical pipeline runner exists in `application/strategy_service.py` via `svos_main()` (`agtrade strategy svos`), which executes all six SVOS phases and writes approval package artifacts.
- Live trading remains disabled by project policy: `scripts/run_st_a2_demo.py` and `scripts/run_portfolio.py` both enforce `LIVE_TRADING=false` / `DEMO_ONLY=true` or exit on `live` mode.
- `config/strategy_catalog.yaml` and `config/strategy_portfolio.yaml` are present as declarative strategy and deployment projections.
- The approval package builder exists in `approval_package/package_builder.py` and enforces approval artifacts before signing.

### Discrepancies

- `docs/SYSTEM_ARCHITECTURE.md` and `docs/svos/CORE_ARCHITECTURE.md` use different lifecycle stage vocabularies. The code in `svos/lifecycle/manager.py` is authoritative for runtime stage names, while `SYSTEM_ARCHITECTURE.md` includes target stages beyond current implementation.
- `CLAUDE.md` uses a stale Phase / stage numbering and omits `INTAKE` / `REVALIDATION` compared to the code.
- The actual execution runtime is split between legacy runtime scripts (`scripts/run_st_a2_demo.py`) and the multi-strategy runner (`scripts/run_portfolio.py`). The live deployment is not actually using the catalog-driven runner.
- `dashboard/strategy_service.py` maintains an overlay file that may diverge from authoritative SVOS registry state.
- `svos/deployment/`, `svos/monitoring/`, `svos/notifications/`, `svos/ui/`, and `svos/experiments/` are placeholders or partial; the architecture documents describe them as full subsystems.
- `data/svos/` is the current JSONL evidence directory in architecture, but the repository does not show a populated live control-plane dataset in this audit.

## Repository Structure vs. Implemented Modules

### Core implemented modules

- `svos/lifecycle/` — Canonical lifecycle and transition validation.
- `svos/governance/` — Qualification and approval gate enforcement.
- `svos/registry/` — Strategy state, evidence, and transition records.
- `svos/orchestration/` — Platform integration, persistence mode detection, record evidence and audited transitions.
- `svos/application/` — Intake, audit, replay, backtest, robustness, and virtual demo stage wrappers.
- `svos/reports/` — Artifact store and report metadata service.
- `svos/api/` — Operational API facade.
- `approval_package/` — Strategy approval package builder and signature logic.
- `db/` — PostgreSQL control plane implementation and Alembic migrations.
- `execution/` and `execution_simulator/` — broker and virtual execution layers.
- `dashboard/` — Flask API, status server, control state, report integration.

### Fragmentation and duplication

- `research/svos/engine.py` and `research/validation/engine.py` duplicate pipeline orchestration logic separate from `svos/application/pipeline.py`.
- `strategy_audit/` and `strategy_validation/` both provide audit engines.
- `pipeline/` scripts and `scripts/` replay/backtest scripts duplicate execution logic.
- `strategy/` and `strategies/` both exist as strategy adapter modules.

### Deployment and dashboard

- `deploy/gcp-vm1/docker-compose.yml` is present and includes Postgres and Adminer. The deployment artifacts align with the documented two-node goal, but the actual runtime topology remains a single-host mix of research and production code.
- `dashboard/app.py` is a real Flask control-plane API. It reads reports, strategy catalog YAML, and demo runner state. It is integrated with report index and status payloads.
- `dashboard/strategy_service.py` is a dashboard-specific mapper and overlay writer, meaning the UI has a separate representation layer for strategy stages.

## Tests vs. Implementation

- `tests/` contains 297 test files and 23 top-level directories. Many architecture and integration tests exist.
- Core tests cover lifecycle authority and `svos` modules in CI.
- Empty scaffolds exist at `tests/integration/`, `tests/regression/`, `tests/replay/`, `tests/strategy/`, and `tests/unit/`.
- The full repository test suite has never been shown green as a collective run; only subset validation has been executed.
- `tests/architecture/test_lifecycle_authority.py` enforces the legacy catalog mutation bypass fix.
- The actual demo runtime and multi-strategy runner are not covered by a dedicated end-to-end test in the `tests/` tree.

## Reports vs. Evidence

- `svos/reports/service.py` implements a standardized artifact index and content-addressed report store.
- `svos/application/pipeline.py` writes an approval package artifact when all phases pass.
- `dashboard/report_service.py` and `dashboard/app.py` expose report index and generation endpoints.
- `dashboard/strategy_service.py` reads SVOS reports and overlays strategy metadata for UI consumption.
- The report system is implemented, but the report index and content-addressed store are only as reliable as the evidence write path. A canonical pipeline runner exists, but there is no clearly documented CI/production workflow that executes the full intake→reporting path end to end in a single live run.

## Deployment Consistency

- Deployment artifacts exist in `deploy/gcp-vm1/`: `docker-compose.yml`, systemd unit wrappers, and shell entrypoints.
- Postgres is configured in containers and bound to `127.0.0.1:5432` by default.
- The platform documents a two-node separation (`docs/svos/DEPLOYMENT_TOPOLOGY.md`), but the actual repository state reflects a single host running research and execution code together.
- `deploy/gcp-vm1/` is a deployment artifact, not a confirmed active production deployment. The systemd units in this repo are consistent with the demo runtime but may not match live orchestration.

## Conclusions

- The repository is largely consistent with the declared Strategy Engineering Platform objective and the Phase 5 architecture ceiling.
- The primary consistency gaps are:
  - stale stage vocabularies across docs and code,
  - duplicated/fragmented pipeline engines,
  - a mismatch between cataloged strategy deployment and actual runtime rollout,
  - partial dashboard integration with an overlay file that can diverge from authoritative registry state,
  - deployment topology described in docs is not yet fully realized in the runnable repository.
- These are validation issues, not feature requests. They should be closed by aligning implementation, consolidating duplicate pipelines, and hardening the end-to-end evidence path.
