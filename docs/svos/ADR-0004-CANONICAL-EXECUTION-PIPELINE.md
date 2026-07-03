# ADR-0004: Canonical Execution Pipeline

Date: 2026-07-03
Status: Authoritative — Accepted
Version: 1.0
Owner: Lead Architect
Authority: Level 5 — Decision
Related: `ADR-0002-CANONICAL-STRATEGY-PACKAGE.md`, `ADR-0003-SINGLE-RUNTIME-AUTHORITY.md`, `../../ARCHITECTURE_STABILIZATION_ROADMAP.md`

## Context

Replay, virtual-demo, and demo execution previously had different orchestration and event shapes. Replay emitted `ReplayEvent`, portfolio demo performed its risk check and `TradeManager` call inline, and virtual broker callers could submit directly. A result from one mode therefore did not prove that the same validation, risk, and execution ordering would occur in another mode.

ADR-0002 made the signed package the only executable handoff. ADR-0003 made `RuntimeAuthority` the only lifecycle owner. Neither decision established one post-validation execution path.

The stabilization roadmap originally proposed a default-deny broker-write decision under ADR-0004 and runtime-equivalent replay under ADR-0005. Explicit owner instruction assigns ADR-0004 to the Canonical Execution Pipeline. Broker-write capability hardening and full deterministic replay qualification remain future, separately numbered work.

## Decision

`production.engine.CanonicalExecutionPipeline` is the only authoritative System 2 path from an execution intent to an execution result.

The fixed order is:

1. receive a normalized `ExecutionIntent`;
2. invoke the configured risk gate;
3. emit the normalized risk decision;
4. stop when risk is denied;
5. invoke exactly one mode adapter when risk is approved;
6. emit a normalized execution result.

Strategy generation, signal selection, and risk-policy calculation are inputs to this boundary and are not changed by it. Broker mechanics remain adapter responsibilities.

## Authority and startup

`RuntimeAuthority.run_pipeline()` validates `strategy-package/v2`, identity, expiry, revocation, symbols, and component selections before it constructs the pipeline. A pipeline cannot start without the resulting `RuntimeContext`. Canonical replay and portfolio entrypoints delegate to `RuntimeAuthority.run_pipeline()`.

Pipeline construction or adapter construction before package validation is forbidden for canonical entrypoints.

## Modes and adapters

The only available execution modes are:

- `replay` — uses `ReplayExecutionAdapter`, which has no broker dependency and only returns a simulated result;
- `virtual_demo` — uses `VirtualDemoExecutionAdapter` around a virtual or non-writing implementation;
- `demo` — uses `DemoExecutionAdapter` around the existing demo `TradeManager`.

The pipeline business logic is identical in all three modes. Only the adapter differs. `live`, `shadow`, and unknown modes are invalid pipeline modes. The portfolio command maps its legacy `shadow` vocabulary to `virtual_demo` at the boundary.

There is no live adapter, live mode enum member, live capability, or real broker order implementation in this decision. Future live support requires a separate owner-approved ADR and implementation.

## Risk gate

Every intent passes through a `RiskGate` before adapter invocation. A rejected decision produces a normalized rejection and the adapter is not called. Demo uses the existing `execution.demo_risk_manager.check_limits`; this ADR does not change its limits or calculations. Replay uses an explicit approving gate only after package/runtime validation because it cannot write to a broker.

## Normalized events

All modes emit `execution-event/v1` with the same fields:

- event and UTC timestamp;
- runtime owner and package identity;
- mode;
- intent, strategy, symbol, side, and quantity;
- approval, reason, status, and adapter reference;
- mode-specific details in a bounded details object.

Lifecycle event types are `pipeline_started`, `intent_received`, `risk_decision`, `execution_result`, and `pipeline_stopped`. Portfolio and replay commands append these records to JSONL evidence.

## Legacy paths

Direct `ReplayEngine` use remains a comparison/strategy-generation API; it is not an authoritative execution run. A replay claiming execution evidence must use `historical_replay.replay_cli`, a signed package, `RuntimeAuthority`, and the replay adapter.

The portfolio tick retains a compatibility seam for existing isolated unit fixtures. Canonical `run()` refuses startup without a pipeline, and the command always supplies one. Lower-level broker and virtual-broker APIs remain adapter implementations, not runtime authorities.

## Rejected alternatives

- **One pipeline class per mode:** rejected because orchestration and risk ordering could drift.
- **Risk checks inside adapters:** rejected because a demo adapter could bypass the gate.
- **A broker mock attached to replay:** rejected because replay must be structurally incapable of broker access.
- **Environment-selected live adapter:** rejected because environment variables are not authorization and live remains unavailable.
- **Move strategy or risk policy into the pipeline:** rejected as an unrelated behavior change.

## Consequences

- Package validation precedes pipeline construction.
- Replay, virtual demo, and demo share one intent/risk/adapter/event path.
- Replay cannot call a broker through its adapter.
- Demo cannot invoke its adapter after risk denial.
- Mode-specific payloads no longer change the evidence envelope.
- Full market-data replay parity, trade-result recovery feedback, durable evidence storage, and live authorization are deferred.

## Rollback

Stop the runtime and preserve runtime, pipeline, and execution event files. Revert command adoption to the ADR-0003 authority-owned callback while leaving ADR-0002 package validation, ADR-0003 locking, and the live-mode deny in place. The safe fallback is replay/virtual-only; rollback must not restore an environment-enabled live path or bypass risk checks.
