# Traceability Matrix

Date: 2026-07-02
Status: Draft — traceability matrix for the repository consistency audit

## Purpose

This matrix links high-level requirements, architecture, implementation modules, tests, reports, and deployment artifacts. It is intended as a starting point for explicit traceability coverage.

| Requirement / Document | Code Module(s) | Tests | Reports / Outputs | Deployment / Runtime | Traceability Gap |
|---|---|---|---|---|---|
| `docs/PROJECT_OBJECTIVE.md` — demo-only research platform, no live trading | `svos/`, `execution/`, `dashboard/`, `production/` | `tests/test_svos_sample.py`, `tests/test_demo_execution_safety.py` | `docs/PROJECT_READINESS_V1_REVALIDATION.md`, `docs/PROJECT_READINESS_V2.md` | `scripts/run_st_a2_demo.py`, `bot.py` | No explicit document linking objective to runtime code path |
| `docs/SYSTEM_ARCHITECTURE.md` — two-system split | `svos/`, `execution/`, `core/`, `dashboard/` | `tests/architecture/test_package_boundaries.py`, `tests/architecture/test_lifecycle_authority.py` | `docs/architecture/system_architecture.md`, `docs/REPOSITORY_AUDIT.md` | deployment service files / systemd units (not yet fully documented) | Runtime topology not fully mapped to docs |
| `docs/SVOS_DESIGN_REFERENCE.md` — SVOS lifecycle stages | `svos/lifecycle/manager.py`, `svos/application/`, `strategy_validation/` | `tests/strategy_validation/test_pipeline.py`, `tests/test_validation_gate.py` | `docs/svos/STRATEGY_ENGINEERING_PLATFORM_IMPLEMENTATION_PLAN.md`, `docs/svos/DOC_AUDIT_2026-06-29.md` | `scripts/run_current_strategy_svos.py`, `scripts/run_svos_pipeline.py` | Missing direct mapping of stage docs to specific implementation modules |
| `docs/VALIDATION_GATE_ENGINE.md` — gate definitions | `svos/application/backtest.py`, `svos/application/robustness.py`, `strategy_validation/validators/` | `tests/test_validation_gate.py`, `tests/strategy_validation/test_pipeline.py` | `docs/VERDICT_LOG.md`, `docs/BACKTEST_RESULTS.md` | `scripts/run_current_strategy_svos.py` | Reporting path is not consistently documented for each gate output |
| `docs/EXECUTION_LAYER_VALIDATION_SPEC.md` — execution validation | `execution/`, `bot.py`, `adaptive/`, `dashboard/` | `tests/test_demo_execution_safety.py`, `tests/test_dashboard_app.py`, `tests/test_broker_interface_and_gate.py` | `reports/live_vs_backtest.md`, `docs/DEPLOYMENT_READINESS.md` | `scripts/run_st_a2_demo.py`, `scripts/run_portfolio.py` | Execution path diverges from documented stop/halt enforcement |
| `docs/RISK_SPEC.md` — risk parameters | `execution/risk_manager.py`, `execution/demo_risk_manager.py`, `core/circuit_breaker.py` | `tests/test_risk_manager.py`, `tests/portfolio/test_limits.py` | `docs/DEPLOYMENT_READINESS.md`, `docs/OPERATING_MANUAL.md` | `scripts/run_st_a2_demo.py`, `dashboard/strategy_service.py` | Risk config wiring is under-documented and partially unimplemented |
| `docs/REPORT_SYSTEM.md` — report domain model | `approval_package/package_report.py`, `dashboard/report_service.py`, `scripts/generate_reports.py`, `reports/` | `tests/test_generate_reports.py`, `tests/scripts/test_registry_audit.py` | `reports/`, `docs/VERDICT_LOG.md` | `scripts/generate_reports.py` | Report schema and generation mapping are not fully documented |
| `docs/STRATEGY_PORTFOLIO_ROADMAP.md` — portfolio deployment | `config/strategy_portfolio.yaml`, `scripts/run_portfolio.py`, `dashboard/strategy_service.py` | `tests/portfolio/test_portfolio_runner.py`, `tests/test_dashboard_app.py` | `docs/PROJECT_READINESS_V1_REVALIDATION.md`, `reports/production_readiness_report.md` | `scripts/run_portfolio.py` | Portfolio config and deployment path are not fully reconciled |
| `docs/00_Project/GLOSSARY.md` — terminology | multiple modules | none | none | none | No single source-of-truth glossary mapping code terms to docs |

## Traceability Observations

- Several requirements are covered by code and tests, but no single document currently aggregates those mappings.
- The `svos/` and `execution/` domains have the strongest traceability, while `approval_package/` and `reports/` lack explicit mapping documents.
- The current test suite demonstrates many runtime behaviors, but the audit lacks a documented evidence trail from requirement to report output.

## Recommended next step

Formalize this draft matrix into a living traceability document and add cross-links in the relevant authoritative docs. At minimum, each stage document should include:

- the canonical implementing module(s)
- the primary validation test(s)
- the produced report(s)
- the deployment artifact / runtime entrypoint
