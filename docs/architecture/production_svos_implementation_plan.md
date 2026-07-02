# Production/SVOS Incremental Implementation Plan

Date: 2026-07-02
Status: active migration plan

## Goal

Separate the simple Production execution engine from SVOS without changing validated
strategy behavior or breaking existing operator entry points.

The governing scope is `docs/00_Project/TWO_SYSTEM_ARCHITECTURE_TRUTH.md`.

## Invariants

- Production contains only Trading Engine, Strategy Package Loader, Risk
  Manager, Execution Manager, Broker API, and Position Management behavior.
- SVOS follows Strategy Idea → Strategy Audit → Historical Replay → Backtest →
  Statistical Validation → Robustness Testing → Virtual Demo Trading →
  Production Approval; it never submits live orders.
- Both depend on pure `shared` contracts and replaceable `infrastructure` adapters.
- `LIVE_TRADING=false` and `DEMO_ONLY=true` remain frozen during migration.
- Existing public imports remain compatibility facades until callers migrate.

## Completed stages

1. Audited and classified active modules.
2. Established `shared`, `application`, `production`, and SVOS boundary packages.
3. Added AST-based dependency gates.
4. Added versioned strategy registry, deterministic packages, deployment records,
   and versioned API contracts.
5. Added Production import, checksum/signature preflight, disabled staging, and
   consolidated operator status.
6. Added immutable GCS transport and Cloud KMS asymmetric signing adapters.

## Remaining stages

1. Move legacy `execution` implementations behind `production.engine` one slice
   at a time after all callers use the facade.
2. Split the mixed dashboard into Production status and SVOS workstation apps.
3. Split cross-boundary database tables and backup policies.
4. Bind imported package contents to the Production strategy runtime and drill rollback.
5. Provision named hosts, workload identities, bucket/KMS IAM, private networking,
   service units, monitoring, and durable logs.
6. Run a remote publish/import/preflight rehearsal and retain evidence.

## Gate for each stage

Each slice requires import-boundary tests, focused unit/integration tests,
unchanged strategy fixtures, rollback instructions, and an operator-visible
disabled status. Live activation is a separate future authorization.
