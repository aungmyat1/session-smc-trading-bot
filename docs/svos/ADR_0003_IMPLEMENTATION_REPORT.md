# ADR-0003 Implementation Report

- Date: 2026-07-03
- Status: Implemented
- ADR: `docs/svos/ADR-0003-SINGLE-RUNTIME-AUTHORITY.md`
- Scope: System 2 runtime lifecycle authority only

## Outcome

`production.engine.RuntimeAuthority` now owns canonical package preflight, single-runtime locking, broker/risk component selection identifiers, lifecycle state, event emission, runtime invocation, and safe shutdown.

`scripts/run_portfolio.py` delegates startup to this authority and requires `strategy-package/v2`. No strategy, broker, risk-calculation, order-execution, or live-authorization behavior was changed.

## Changed files

- `production/engine/runtime.py` — canonical authority, lifecycle, lock, state, and events.
- `production/engine/__init__.py` — public runtime-authority surface.
- `scripts/run_portfolio.py` — canonical command delegates lifecycle ownership.
- `bot.py`, `scripts/run_st_a2_demo.py`, `scripts/run_d2_e3_demo.py` — explicit legacy markers only.
- `tests/production/test_runtime_authority.py` — startup, rejection, duplicate ownership, shutdown, and state tests.
- `tests/production/test_engine_facade.py` and `tests/architecture/test_package_boundaries.py` — authority and boundary contracts.
- `tests/portfolio/test_strategy_package_cli.py` and `tests/integration/test_canonical_package_handoff.py` — canonical command migration.
- `docs/svos/ADR-0003-SINGLE-RUNTIME-AUTHORITY.md` — accepted decision.
- `ARCHITECTURE_STABILIZATION_ROADMAP.md` — owner sequencing amendment.

## Acceptance criteria

| Criterion | Result | Evidence |
|---|---|---|
| One canonical runtime authority exists | PASS | `production.engine.RuntimeAuthority` is exported by the Production engine. |
| Duplicate runtime ownership is rejected | PASS | Atomic exclusive lock and concurrent-owner test. |
| Runtime requires valid strategy-package/v2 | PASS | Authority calls the ADR-0002 verifier before invoking its runtime callback. |
| Invalid, expired, unsigned, revoked packages are rejected | PASS | Parameterized pre-runtime negative tests. |
| Safe shutdown | PASS | Normal and cancellation paths release ownership and persist `STOPPED`. |
| Runtime state is observable | PASS | Persistent JSON state and append-only JSONL events are tested. |
| Live trading remains disabled | PASS | No live adapter is registered and existing live-mode rejection is unchanged. |

## Validation evidence

- Focused ADR-0003 and package-command tests: **37 passed**.
- Combined BTCUSDT/ADR regression suite: **63 passed**.
- Full repository pytest: **1485 passed, 4 skipped, 8 failed**. The eight failures are the pre-existing SMC adapter assertion (1) and SVOS robustness/pipeline defect (7); no ADR-0003 test failed.
- Targeted Ruff: **PASS**.
- Targeted mypy: **PASS**.
- Repository-wide Ruff remains blocked by **664 pre-existing violations**.
- Repository-wide mypy remains blocked by the pre-existing untyped `metaapi_cloud_sdk` import and duplicate `scripts.health_check` module mapping.
- `git diff --check`, documentation drift, dead-link, and orphan checks: **PASS**.

## Rollback

1. Stop `scripts/run_portfolio.py` and verify no active broker session remains.
2. Preserve `runtime-state.json`, `runtime-events.jsonl`, lock diagnostics, and the v2 package.
3. Revert the command adapter to its prior disabled/demo-only implementation.
4. Do not restore legacy package formats or weaken ADR-0002 verification.
5. If a stale lock exists after a confirmed process stop, archive it with incident evidence before removal.

## Follow-up work

- Broker-truth risk feedback formerly proposed as ADR-0003 remains unimplemented and must be renumbered.
- Default-deny broker-write work and later ADRs were not implemented.
- A later operational PR may add heartbeat integration and stale-lock recovery policy after explicit approval.
