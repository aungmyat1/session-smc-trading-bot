# Demo Runtime Integration Report

- Date: 2026-07-02
- Status: IMPLEMENTED — PR CI PASS; merge policy pending
- Owner: Engineering
- Pull request: #19
- Sprint commit: `d1f7768`

## Outcome

The canonical portfolio runner now validates an approved, signed, unexpired strategy package and reconciles its strategy identity before any runtime coroutine or broker connection starts. A packaged run is scoped to that single approved strategy. Live mode remains unconditionally blocked.

## Implemented controls

- `scripts/run_portfolio.py` requires a valid package in demo mode.
- A supplied package is also validated in shadow/dry-run mode.
- Missing, invalid, unapproved, unsigned, expired, or failed-risk packages are rejected.
- `scripts/validate_strategy_identity.py` checks catalog, portfolio, approved-package, SVOS-registry, and runner identities.
- Identity mismatches raise before `asyncio.run(...)` and therefore before runtime startup.
- Runtime strategy selection uses the catalog's canonical identity spelling.
- Packaged execution is restricted to the package's approved strategy.
- `scripts/run_st_a2_demo.py` is explicitly marked as a legacy compatibility entrypoint and directs operators to `run_portfolio.py`.
- Dashboard status resolution remains SVOS-first, then catalog, then overlay fallback.

## Acceptance evidence

| Criterion | Result | Evidence |
|---|---|---|
| Reject unapproved packages | PASS | `test_rejects_unapproved_package` |
| Accept valid demo package | PASS | parameterized demo package CLI test |
| Accept valid dry-run package | PASS | parameterized dry-run package CLI test |
| Block live mode | PASS | live-mode tests; gate executes before package/runtime |
| Reject identity mismatch before runtime | PASS | package and SVOS mismatch tests |
| Preserve SVOS-first dashboard status | PASS | `tests/dashboard/test_strategy_status_resolution.py` |
| Mark ST-A2 runner legacy | PASS | `LEGACY_ENTRYPOINT = True` and regression test |
| Keep live trading disabled | PASS | environment assertion and unconditional live-mode rejection |

## Validation record

### GitHub PR #19

All checks passed: Quality and architecture, unit tests, integration tests, security and dependencies, documentation and package contracts, and Required CI.

### Local focused validation

- Portfolio, readiness, and dashboard focused suite: **86 passed**.
- New identity validator Ruff check: **PASS**.
- New identity validator mypy check: **PASS**.
- `validate_strategy_package.py --self-test`: **PASS**.
- `validate_strategy_identity.py --self-test`: **PASS**.
- `check_docs_drift.py --root .`: **PASS**.
- `lint_docs.py --root docs --index docs/index.md`: **PASS** with 201 non-blocking header warnings.

### Repository-wide baseline findings

- `ruff check .`: **FAIL**, 669 existing violations across legacy code and tests. No cleanup was included because it is outside PR #19.
- `mypy .`: **FAIL**, due to the existing untyped `metaapi_cloud_sdk` import and duplicate `scripts.health_check` module discovery.
- `pytest`: **INCOMPLETE**, after collecting 1,454 tests and reaching 25%. All sprint tests passed; one pre-existing SMC adapter assertion failed, followed by a native pandas segmentation fault in `tests/research_engine/test_pipeline.py`.

These baseline findings do not contradict the green scoped PR CI, but they remain repository-level remediation items.

## Safety verdict

**READY TO MERGE WHEN BRANCH POLICY IS SATISFIED.** This verdict covers demo runtime integration only. It does not authorize live trading.
