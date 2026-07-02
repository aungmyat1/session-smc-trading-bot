# Implementation Priority Backlog

Date: 2026-07-02
Status: Draft — prioritized backlog for repository consistency and readiness

This backlog ranks implementation tasks by their impact on repository consistency, safety, and readiness for the current demo-only research platform.

## Highest priority

1. `FIX RISK CONFIG LOADING` — ensure `config/strategy_portfolio.yaml` is loadable at runtime by the deployed demo path and replace hardcoded defaults with config-driven values.
   - Impact: restores the documented risk model and prevents silent demo-path drift.
   - Dependencies: `execution/demo_risk_manager.py`, `execution/governance_guard.py`, `dashboard/strategy_service.py`.

2. `IMPLEMENT STRATEGY PACKAGE BUNDLE` — build the approved strategy artifact package and enforce checksum verification at production import.
   - Impact: aligns code with documented package-based production approval.
   - Dependencies: `approval_package/package_builder.py`, `approval_package/package_validator.py`, `bot.py`, `production/importer.py`.

3. `UNIFY SVOS ORCHESTRATION` — consolidate the active strategy validation pipeline into one canonical implementation and archive the legacy path.
   - Impact: removes confusion and supports maintainable documentation.
   - Dependencies: `svos/application/*`, `research/svos/engine.py`, `research/validation/engine.py`, `strategy_validation/`.

4. `FIX ROBUSTNESS CALL-SITE` — correct the argument mismatch between the robustness gate caller and implementation so all robustness functions execute as intended.
   - Impact: restores the documented Phase-4 robustness validation gate.
   - Dependencies: `svos/application/robustness.py`, `research/robustness.py`, `tests/test_validation_gate.py`.

5. `CREATE TRACEABILITY MATRIX` — publish a living traceability doc mapping requirements → architecture → modules → tests → reports → deployment.
   - Impact: closes the highest documentation governance gap identified by the audit.
   - Dependencies: `docs/SYSTEM_ARCHITECTURE.md`, `docs/SVOS_DESIGN_REFERENCE.md`, `docs/REPORT_SYSTEM.md`, `tests/architecture/test_package_boundaries.py`.

## Medium priority

6. `DOCUMENT APPROVAL PACKAGE ARCHITECTURE` — add or extend docs to explain `approval_package/` code, package format, and import/runtime verification.
   - Impact: improves documentation and reduces the apparent gap between docs and implementation.
   - Dependencies: `docs/project_readiness_assessment.md`, `docs/REPOSITORY_AUDIT.md`, `docs/REPORT_SYSTEM.md`.

7. `RECONCILE PORTFOLIO CONFIG AND DEPLOYMENT` — document and validate the relationship between `config/strategy_catalog.yaml`, `config/strategy_portfolio.yaml`, and runtime portfolio practices.
   - Impact: removes a key consistency ambiguity.
   - Dependencies: `scripts/run_portfolio.py`, `dashboard/strategy_service.py`, `config/strategy_catalog.yaml`.

8. `UNIFY DASHBOARD SURFACES` — define one supported dashboard surface and document its deployment and API boundaries.
   - Impact: reduces UI surface drift and aligns dashboard docs with code.
   - Dependencies: `dashboard/app.py`, `dashboard/live_app.py`, `dashboard/status_server.py`, `New Dashborad/` assets.

9. `ADD INTEGRATION/REGRESSION TESTS` — populate empty integration/regression directories and make them part of the CI gate.
   - Impact: raises confidence and supports future refactoring.
   - Dependencies: `tests/`, CI configuration, `scripts/run_validation_gate.py`.

10. `REVIEW SIMULATOR DOCUMENTATION` — add explicit docs for `simulator/` code and the offline replay/forward-test path.
   - Impact: makes key validation code traceable and reduces the small but important documentation gap.
   - Dependencies: `docs/HISTORICAL_REPLAY.md`, `docs/FORWARD_TEST_VALIDATION.md`, `simulator/forward_test.py`.

## Lower priority

11. `ARCHIVE LEGACY STRATEGY AUDIT ENGINE` — move unused legacy audit files to `archive/` or explicitly mark them as historical.
12. `DOCUMENT REPORT GENERATION MAPPING` — tie each report type to the producing module and report artifact.
13. `ADD DEPLOYMENT TOPOLOGY DIAGRAM` — update deployment docs with actual runtime units and service names.
14. `STANDARDIZE DOCUMENTATION VOCABULARY` — define canonical terms for Phase/Stage/Pipeline/Production Approval and apply to key docs.
15. `AUTOGENERATE CONFIG/SCHEMA DOCS` — identify manual docs that should be generated from schemas or code.
