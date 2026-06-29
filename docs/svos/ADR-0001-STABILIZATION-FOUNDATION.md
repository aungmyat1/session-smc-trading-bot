# ADR-0001: Stabilization Foundation Decisions

Date: 2026-06-29
Status: Accepted

## Context

Lifecycle state, evidence, reports, and execution controls currently span
PostgreSQL, YAML, JSONL, SQLite, and filesystem artifacts. The architecture
review found that this permits governance bypass and partial state changes.

## Decisions

1. `svos.lifecycle.StrategyLifecycleManager` defines the canonical stage
   vocabulary. `GovernanceService` is the only application service allowed to
   authorize a transition.
2. PostgreSQL 16 is the target authority for strategy versions, lifecycle
   state, decisions, approvals, evidence metadata, and the transactional
   outbox. A database failure blocks mutation.
3. Qualification artifacts use immutable SHA-256 content addressing. The
   database stores identity, lineage, trust, status, and location; it does not
   store large report bodies.
4. IDs are UUIDs in PostgreSQL. Strategy slugs and external run IDs are unique
   display/integration identifiers, never relational identity substitutes.
5. All control-plane timestamps are timezone-aware UTC. Financial values use
   explicit `NUMERIC` precision; binary floating point is not canonical
   financial evidence.
6. Research, governance, reporting, and broker execution remain modular-monolith
   boundaries. Broker credentials are unavailable to research and reporting.
7. YAML is a generated compatibility projection after cutover. It is never a
   mutation fallback.
8. Production Approval remains record-only under the current implementation
   ceiling. Live trading stays disabled and requires an owner confirmation
   outside this implementation.

## Acceptance consequences

- Legacy direct mutation callers must be removed, not allow-listed forever.
- Empty and production-like migration paths, rollback, restore, optimistic
  concurrency, and atomic decision/state/outbox behavior require tests.
- Feature work remains frozen until stabilization Phases 0-2 pass.
