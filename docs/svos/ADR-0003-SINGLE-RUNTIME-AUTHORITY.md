# ADR-0003: Single Runtime Authority

Date: 2026-07-03
Status: Authoritative — Accepted
Version: 1.0
Updated: 2026-07-03
Owner: Lead Architect
Authority: Level 5 — Decision
Related: `ADR-0002-CANONICAL-STRATEGY-PACKAGE.md`, `../00_Project/TWO_SYSTEM_ARCHITECTURE_TRUTH.md`, `../../ARCHITECTURE_STABILIZATION_ROADMAP.md`

## Context

System 2 had multiple modules capable of owning a runtime loop and external connection lifecycle:

- `bot.py`
- `scripts/run_portfolio.py`
- `scripts/run_st_a2_demo.py`
- `scripts/run_d2_e3_demo.py`

Package checks, startup state, adapter selection, risk-service selection, event emission, and shutdown behavior were not governed by one owner. ADR-0002 established the package boundary but did not establish runtime ownership.

The roadmap originally reserved the ADR-0003 number for broker-truth risk feedback. Explicit owner instruction reassigns ADR-0003 to Single Runtime Authority. Broker-truth feedback remains unimplemented and requires a future, renumbered decision.

## Decision

`production.engine.RuntimeAuthority` is the only authoritative System 2 runtime lifecycle owner.

It owns:

1. acquisition and release of the single-runtime ownership lock;
2. validation of `strategy-package/v2` using the ADR-0002 public key;
3. expiry, signature, revocation, strategy identity, and execution-symbol checks;
4. selection of an approved broker adapter identifier;
5. selection of an approved risk-enforcer identifier;
6. lifecycle states and persistent state reporting;
7. append-only runtime lifecycle events;
8. invocation and safe shutdown of the selected runtime implementation adapter.

It does not implement strategy logic, risk calculations, broker calls, order behavior, package approval, or live authorization.

## Runtime lifecycle

```text
STOPPED
  -> ownership acquired
  -> VALIDATING_PACKAGE
  -> READY
  -> STARTING
  -> RUNNING
  -> STOPPING
  -> STOPPED

Validation failure -> REJECTED
Runtime failure    -> FAILED
```

State is persisted to `data/production/runtime/runtime-state.json`. Events are appended to `data/production/runtime/runtime-events.jsonl`. Runtime ownership is protected by the atomic `data/production/runtime/runtime-owner.lock` file.

A stale ownership lock fails closed and requires explicit operator investigation. A second authority may not overwrite the active owner's state or start a runtime.

## Package-first startup

No runtime implementation callback is invoked until:

- the package is a canonical v2 archive;
- the Ed25519 signature verifies;
- approval is current and not revoked;
- expected strategy identity matches;
- every package symbol is in `enabled_execution_symbols`;
- broker and risk component selections are recognized.

Missing, legacy-directory, malformed, unsigned, expired, revoked, mismatched, or research-only-symbol packages are rejected before broker connection.

## Component selection

Current accepted identifiers are deliberately narrow:

- broker adapter: `vantage-demo`
- risk enforcer: `demo-risk-firewall`

These identifiers select existing implementations without changing their behavior. No live broker adapter is registered. Adding another identifier requires a separate reviewed change.

## Legacy entrypoints

`bot.py`, `scripts/run_st_a2_demo.py`, and `scripts/run_d2_e3_demo.py` are compatibility implementations, not runtime owners. They expose `LEGACY_RUNTIME_ENTRYPOINT = True` and are inventoried by the canonical authority.

`scripts/run_portfolio.py` is the canonical command adapter and delegates lifecycle ownership to `RuntimeAuthority`. It requires a v2 archive for shadow and demo startup. Its existing strategy, broker, and risk behavior is unchanged after authority validation.

## Rejected alternatives

- **Process-local singleton only:** rejected because it does not prevent a second OS process.
- **PID file without atomic creation:** rejected because concurrent startup can race.
- **Keep validation in each script:** rejected because entrypoints can drift.
- **Accept ADR-0002 legacy directories at runtime:** rejected because canonical runtime must have one signed handoff format.
- **Move broker or risk behavior into the authority:** rejected as unrelated implementation and a violation of this ADR's orchestration-only scope.

## Rollback

Stop the canonical command, preserve runtime state/events and the package, and revert `scripts/run_portfolio.py` to its previous disabled/demo-only adapter. Do not remove ADR-0002 validation or restore legacy package startup. If authority integrity is uncertain, leave runtime stopped and fail closed.

## Consequences

- One runtime owner and one observable lifecycle now exist.
- Duplicate startup is rejected across processes sharing the runtime root.
- Legacy runtime implementations remain for rollback but are explicitly non-authoritative.
- Broker-truth feedback, retry semantics, risk changes, and later ADR work are not implemented here.
