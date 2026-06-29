# Stabilization Status

Date: 2026-06-29
Verdict: **NOT READY — feature freeze remains active**

This is the current implementation-status companion to the architecture review
roadmap. It does not replace gate evidence.

| Area | Status | Evidence / remaining gate |
|---|---|---|
| Governing scope | Implemented | Legacy scope and roadmap documents are explicitly superseded |
| Architecture decisions | Implemented | `ADR-0001-STABILIZATION-FOUNDATION.md` |
| Broker safety | Implemented | No current/approved strategy; direct promotion fails closed; Production Approval remains `NOT_RUN` |
| Lifecycle bypass closure | Implemented | Active runners cannot call legacy catalog mutators; architecture test has no bypass allow-list |
| Operator API security | Implemented baseline | Bearer token, immutable actor header, role checks, restricted CORS; OIDC remains deferred |
| Alembic baseline | Implemented | Empty and adopted-v2 paths share idempotent revision 001; duplicate v2 DDL removed from revision 002 |
| Control-plane schema | Implemented | Transition lineage, optimistic revision, evidence trust/invalidation, report records, import ledger, outbox |
| Transactional repository | Implemented | Decision, transition, stage revision, and outbox commit in one transaction with row lock |
| Immutable artifacts | Implemented | SHA-256 content-addressed filesystem adapter |
| Legacy import | Implemented baseline | Idempotent catalog import as DRAFT/non-qualifying evidence context |
| YAML cutover | Implemented baseline | Active lifecycle code does not write YAML; projection generator is explicit and read-only |
| PostgreSQL integration exercise | Pending environment gate | Run with disposable `SVOS_TEST_DATABASE_URL`; migration/concurrency test is present |
| Backup/restore tooling | Implemented baseline | Encrypted backup, integrity manifest, and confirm-gated restore; operational restore drill and RPO/RTO declaration remain pending |
| Full OIDC/four-eyes approval | Pending | Required before any broker-facing approval capability |

Feature work remains frozen until the pending Phase 2 operational exercises
pass and the architecture review verdict is formally updated.
