# Demo Readiness Backlog

## Goal

Rank remaining work by impact on stable demo trading and platform readiness.

## High-impact backlog

1. Harmonize the runtime path for strategy portfolio execution
   - Fix `scripts/run_portfolio.py` so `config/strategy_portfolio.yaml` is the canonical source of truth.
   - Remove or document legacy `scripts/run_st_a2_demo.py` if it is no longer the active runner.
   - Add a verification test that the portfolio runner can start and stop using the catalog.

2. Close the end-to-end SVOS pipeline execution path
   - Standardize `application/strategy_service.py` (`agtrade strategy svos`) as the documented canonical command for intake → audit → replay → backtest → robustness → virtual demo.
   - Add a CI step or regression test that exercises this path on a sample strategy spec.

3. Align dashboard state with authoritative SVOS registry
   - Replace overlay-only stage/status mappings in `dashboard/strategy_service.py` with live state from `svos/registry/service.py`.
   - Verify `POST /api/svos/run` and report generation endpoints use the same state machine.

4. Harden approval package deployment / registry integration
   - Add a package registry ingest or acceptance check for `approval_package/package_builder.py` output.
   - Document the approval package lifecycle and required evidence artifacts.

## Medium-impact backlog

5. Validate governance confirm-token policy enforcement
   - Ensure `CONFIRM-*` actions are enforced consistently in dashboard APIs and execution control.
   - Add a no-op regression test for token validation paths.

6. Close the research vs production deployment boundary
   - Make `deploy/gcp-vm1/` reflect a runnable separation between research/SVOS and execution assets.
   - Document the two-node topology and identify which repository services belong on each node.

7. Improve artifacts and report evidence storage
   - Add a documented artifact index for strategy runs in `svos/reports/service.py`.
   - Ensure content-addressed paths are reproducible and accessible from dashboard report endpoints.

8. Recover docs & architecture drift
   - Fix stale stage vocabulary in `CLAUDE.md`, `docs/SYSTEM_ARCHITECTURE.md`, and `docs/svos/CORE_ARCHITECTURE.md` if needed.
   - Resolve broken links and doc header issues surfaced by docs linting.

## Low-impact backlog

9. Strengthen testing coverage
   - Add end-to-end tests for the demo runner and strategy portfolio loading.
   - Add report-index smoke tests to `tests/`.

10. Clarify strategy catalog metadata
   - Document the governance meaning of `enabled`, `execution_mode`, and `approved` in `config/strategy_catalog.yaml`.
   - Add comments in the YAML describing the difference between `demo` and `shadow` execution.

## Recommended next step

Implement a canonical sample run with a minimal strategy spec, then add a CI regression test for that path.
