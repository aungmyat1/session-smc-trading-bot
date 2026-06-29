# Gap Analysis

## Workflow assessment

The intended workflow is represented in `research/svos/engine.py`:

```text
Intake -> Audit -> Enhancement -> Replay -> Backtest -> Robustness
       -> Verification Ready -> Virtual Demo -> Production Approval
```

This is functionally broader than the minimum requested pipeline. The ordering
is reasonable. Qualification authority is not: stage results, legacy catalog
promotion, the new lifecycle, dashboard projections, and execution eligibility
use different stage vocabularies and policies.

## Current versus target

| Capability | Current state | Target state | Priority | Complexity | Dependencies |
|---|---|---|---|---|---|
| Lifecycle governance | New gated core plus legacy direct promotion | One transactional authority | Critical | M | policy/version model |
| Strategy specification | Markdown/catalog paths and text parser | Immutable typed spec versions | High | M | registry DB, schema |
| Strategy audit | Two overlapping engines | One port and versioned findings | High | M | spec contract |
| Historical replay | Multiple capable implementations | One canonical event/run contract | High | H | dataset/run identity |
| Backtesting | Several scripts and `src` simulator | Registered engine adapter with common output | High | H | run/metric schemas |
| Robustness | Implemented checks and payloads | Reproducible WFA/Monte Carlo/regime evidence | High | H | experiment manager |
| Virtual demo | Simulator exists; synthetic payload default | Same execution code, deterministic cost/latency models | Critical | H | event contract, execution port |
| Production approval | Flags/catalog plus new approvals | Authenticated RBAC, attestation, revocation | Critical | M | identity, governance DB |
| Experiment management | Placeholder package and ad hoc reports | First-class hypotheses/runs/lineage | High | M | research DB |
| Evidence storage | Hashed files and indexes | Immutable artifact store + transactional metadata | Critical | M | storage port, DB |
| Monitoring/revalidation | Health/report aggregation | Drift policies and automatic revalidation cases | Medium | H | production telemetry |
| Deployment | Status view and scripts | Controlled deployment records/rollback | High | H | approval and runtime isolation |
| Notifications | Placeholder | Outbox-driven notifications | Low | M | event/outbox |
| API | Flask dashboard routes | Authenticated, versioned application API | Critical | M | identity and services |

Complexity: S/M/H describes implementation effort after dependencies exist.

## Missing systems

### Critical

- Transactional governance repository and exclusive mutation boundary.
- Authenticated operator identity, RBAC, and approval attestation.
- Immutable artifact metadata linked atomically to strategy/run/stage.
- Architecture/CI enforcement preventing bypass paths.

### High

- Versioned strategy specification schema and semantic validation.
- Canonical research run and dataset snapshot contracts.
- Database migrations and tested backup/restore.
- Experiment manager for parameters, seeds, folds, regimes, and comparisons.
- Unified quantitative metric definitions and units.
- Deployment/recovery state separate from strategy research status.

### Medium/Low

- Production drift rules and automated revalidation cases.
- Central event/outbox and notification adapters.
- Retention, archival, and legal/audit policy.
- Multi-user UI workflows after the service API is secured.

## Components to consolidate or defer

- Do not build more strategy engines until replay/backtest adapters share one
  contract.
- Do not expand placeholder `svos/ui`, `notifications`, or `experiments`
  packages merely to match the folder diagram.
- Consolidate audit behavior rather than choosing by file age.
- Archive the nested `session_smc` repository after behavioral parity tests.
- Keep DuckDB/Parquet; do not move bulk analytical data into the control DB.
- Keep live execution lightweight and downstream of governance.

## Recommended implementation order

1. Authority freeze and architecture decisions.
2. Governance integration and API security.
3. PostgreSQL control/evidence schema plus migrations.
4. Typed specification, evidence, run, and metric contracts.
5. Audit/replay/backtest/robustness adapter consolidation.
6. Virtual execution parity and recovery qualification.
7. Deployment, monitoring, drift, and revalidation.

