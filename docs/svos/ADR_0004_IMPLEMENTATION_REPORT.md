# ADR-0004 Implementation Report

- Date: 2026-07-03
- Status: Implemented
- ADR: `docs/svos/ADR-0004-CANONICAL-EXECUTION-PIPELINE.md`
- Scope: Canonical execution orchestration only
- Safety: Live mode remains unavailable; no real broker order path was added

## Outcome

`production.engine.CanonicalExecutionPipeline` now owns the invariant execution sequence: normalized intent, mandatory risk decision, mode-adapter invocation, and normalized result event. Replay, virtual demo, and demo use the same sequence and differ only through `ReplayExecutionAdapter`, `VirtualDemoExecutionAdapter`, or `DemoExecutionAdapter`.

`RuntimeAuthority.run_pipeline()` validates the signed package before constructing the pipeline. The portfolio and historical replay commands delegate to that method. The replay adapter has no broker dependency, a denied risk decision cannot invoke a demo adapter, and no live mode or adapter exists.

## Duplicate path inventory

- `historical_replay.replay_engine.ReplayEngine` produced replay-specific signal events without runtime or execution authority.
- `scripts/run_portfolio.py` performed risk checks and demo submission inline.
- `virtual_broker` and `execution_simulator` exposed lower-level submission implementations without a shared normalized envelope.
- `execution.order_manager.OrderManager` remains a legacy execution implementation and is not selected by canonical startup.
- `execution.trade_manager.TradeManager` remains the demo adapter implementation; its strategy and broker behavior were not changed.

Lower-level implementations remain available as adapters or comparison tools. Authoritative execution evidence now requires the runtime-owned pipeline.

## Changed files

- `production/engine/execution_pipeline.py` — canonical intent, risk, adapter, result, and `execution-event/v1` contracts; replay, virtual-demo, and demo adapters.
- `production/engine/runtime.py` — validation-first `run_pipeline()` authority method.
- `production/engine/__init__.py` — public canonical pipeline surface.
- `scripts/run_portfolio.py` — runtime-owned virtual-demo/demo pipeline adoption and normalized JSONL events.
- `historical_replay/replay_cli.py` — signed-package, runtime-authority, and non-writing replay pipeline adoption.
- `tests/production/test_canonical_execution_pipeline.py` — adapter, mode, risk, event, broker-isolation, and validation-order tests.
- `tests/architecture/test_canonical_execution_authority.py` — canonical entrypoint and live-unavailability contracts.
- `tests/integration/test_canonical_package_handoff.py` — updated authority-owned runtime invocation expectation.
- `docs/svos/ADR-0004-CANONICAL-EXECUTION-PIPELINE.md` — accepted decision.
- `ARCHITECTURE_STABILIZATION_ROADMAP.md` — owner sequencing amendment.

## Acceptance criteria

| Criterion | Result | Evidence |
|---|---|---|
| One canonical execution pipeline exists | PASS | `CanonicalExecutionPipeline` owns intent-to-result ordering. |
| RuntimeAuthority uses the pipeline | PASS | `run_pipeline()` validates before pipeline factory invocation. |
| Replay and demo use runtime authority | PASS | Both canonical CLI entrypoints call `authority.run_pipeline()`. |
| Replay cannot call a broker | PASS | `ReplayExecutionAdapter` has no callback or broker dependency. |
| Demo cannot bypass risk | PASS | Adapter invocation occurs only after an approving `RiskDecision`; denial test asserts zero calls. |
| Same normalized events in every mode | PASS | All modes emit the same `execution-event/v1` dataclass fields. |
| Invalid modes fail before operation | PASS | `live`, `shadow`, and unknown pipeline modes fail at construction. |
| Live remains unavailable | PASS | No live enum member or adapter exists; portfolio live rejection remains. |

## Validation evidence

- Final combined ADR-0002, ADR-0003, ADR-0004, canonical handoff, portfolio, replay, risk, and virtual-broker regression set: **108 passed**.
- Full repository: **1496 passed, 4 skipped, 8 failed**. The failures are the pre-existing SMC adapter expectation (1) and SVOS robustness/pipeline defect (7), matching the ADR-0003 baseline; no ADR-0004 test failed.
- Targeted Ruff: **PASS**.
- Targeted mypy with repository imports skipped: **PASS**. Repository-following mypy remains blocked by pre-existing pandas stub, dashboard typing, experiment typing, Telegram optional-session, and Google Cloud key-union errors.
- `git diff --check`: **PASS**.

## Known unrelated failures

1. `tests/core/test_smc_ob_fvg_session_adapter.py` expects a long signal but the existing adapter returns none.
2. Seven `tests/svos/test_pipeline.py` cases stop at the pre-existing robustness failure and therefore do not produce virtual-demo/package evidence.

These failures were not skipped, hidden, or modified because they are outside ADR-0004.

## Rollback

1. Stop the canonical runtime and verify that no demo adapter remains connected.
2. Preserve `runtime-state.json`, `runtime-events.jsonl`, `execution-events.jsonl`, replay reports, and the signed package.
3. Revert portfolio and replay command adoption to the ADR-0003 authority-owned callback.
4. Keep ADR-0002 package validation, ADR-0003 locking, and live rejection intact.
5. Use replay/virtual-only operation if pipeline integrity is uncertain; do not restore a risk-bypassing or environment-enabled write path.

## Next ADR recommendation

Proceed with ADR-0005: Trade Result + Recovery Feedback. It should consume canonical `execution-event/v1` results and define broker-truth closure, idempotent P&L/risk feedback, and recovery semantics without changing the ADR-0004 submission path.
