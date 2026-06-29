# db — Database Layer

Date: 2026-06-29
Status: Authoritative
Version: 1.0
Updated: 2026-06-29
Owner: Platform Architecture
Authority: Level 6 — Module Documentation
Related: docs/svos/ADR-0001-STABILIZATION-FOUNDATION.md,
         docs/HISTORICAL_DATA_ARCHITECTURE.md,
         docs/svos/CORE_ARCHITECTURE.md

---

## Purpose

This package provides the transactional PostgreSQL persistence layer for
SVOS lifecycle state, evidence records, and governance decisions.

It owns the canonical lifecycle record for every strategy that passes through
the SVOS pipeline. The authoritative schema is defined across `schema_v2.sql`
(research and market data) and `schema_v3.sql` (control-plane governance
tables). ORM models in `models.py` cover both versions.

---

## Architecture

The package is organized into three functional layers:

**Connection layer** (`connection.py`, `runtime.py`): Engine and session
factory built on SQLAlchemy + QueuePool. The `DATABASE_URL` environment
variable overrides the resolved default, making this usable in CI and Docker
without code changes. When `DATABASE_URL` is absent the engine resolves to
`None` — callers must check before use.

**ORM layer** (`models.py`): Single authoritative Python declaration of all
tables across both schema versions. The v2 schema covers market data, research
runs, analytics, and configuration. The v3 additions introduce UUID-keyed
control-plane tables: `StrategyEntity`, `StrategyVersion`, `StageState`,
`GateDecision`, `Approval`, `Outbox`, `Artifact`, and `ArtifactBinding`, plus
tables for experiments, robustness results, virtual execution, and operations.

**Repository layer** (`control_plane.py`, `evidence_repository.py`): The
repositories own all state mutations. Application code must not write ORM
objects directly outside these repositories. `PostgresControlPlane` handles
lifecycle transitions. `evidence_repository.py` handles immutable report
metadata.

**Supporting modules** (`projection.py`, `legacy_import.py`): Read-only YAML
compatibility projection from PostgreSQL state, and idempotent import of
legacy YAML catalog records as non-qualifying state.

---

## Module Inventory

| Module | Purpose |
|---|---|
| `control_plane.py` | Fail-closed transactional lifecycle repository (`PostgresControlPlane`) |
| `models.py` | SQLAlchemy ORM models — v2 + v3 unified schema definition |
| `connection.py` | Database connection factory (engine, `SessionLocal`, `get_db`) |
| `runtime.py` | Database runtime helpers: `resolve_database_url`, `.env` loading |
| `evidence_repository.py` | Transactional PostgreSQL metadata repository for immutable reports |
| `legacy_import.py` | Idempotent import of legacy YAML catalog records as non-qualifying state |
| `projection.py` | Generated read-only YAML compatibility projection from PostgreSQL |
| `schema_v2.sql` | Original DDL — market + research schema |
| `schema_v3.sql` | Extended DDL — control-plane governance tables |
| `migrations/` | Alembic migration scripts |

---

## control_plane.py — PostgresControlPlane

### Purpose

The `PostgresControlPlane` is the **fail-closed transactional lifecycle
repository**. It owns the indivisible commit of a permitted decision,
transition, stage revision, and outbox event.

Policy evaluation belongs to the SVOS application layer. This module does not
evaluate whether a transition should be permitted — that is the caller's
responsibility. Once the caller has made that determination and constructs a
`TransitionCommand`, `PostgresControlPlane` commits the full atomic record or
raises an error. It never falls back to YAML or JSONL on error.

### Key Invariants

- Never falls back to YAML or JSONL on error (fail-closed).
- A `TransitionCommand` is rejected if `actor`, `reason`, or `policy_version`
  is empty or whitespace.
- Optimistic concurrency via `expected_revision` prevents races: the commit
  will raise `ControlPlaneConflict` if the row's `opt_lock` counter does not
  match `expected_revision`, or if the current stage does not match
  `from_stage`.
- A version mismatch between the command's `version_id` and the live
  `StageState.current_version_id` also raises `ControlPlaneConflict`.
- Evidence is required for all transitions except those originating from
  `DRAFT`, `REFINEMENT`, or `REVALIDATION` stages.
- Evidence must be `status="active"`, `trust="QUALIFYING_REAL"`,
  `invalidated_at=None`, and bound to the exact strategy ID, version ID, and
  source stage. Any evidence ID that does not satisfy all five conditions
  raises `ControlPlaneEvidenceError`.

### Error Classes

| Class | Base | When raised |
|---|---|---|
| `ControlPlaneError` | `RuntimeError` | Base error for any rejected commit; also raised for missing fields, unknown strategy, or missing stage state |
| `ControlPlaneConflict` | `ControlPlaneError` | Stale `expected_revision`, stage mismatch, or version ID mismatch — indicates a concurrent mutation |
| `ControlPlaneEvidenceError` | `ControlPlaneError` | Evidence absent, not found, stale, invalidated, non-qualifying trust, or bound to wrong strategy/version/stage |

### Data Classes

**`TransitionCommand`** (frozen dataclass): The caller-constructed command
carrying all inputs for a single transition. Fields: `strategy_slug`,
`version_id` (UUID), `from_stage`, `to_stage`, `expected_revision` (int),
`actor`, `reason`, `policy_version`, and an optional `evidence_ids` tuple of
UUIDs.

**`CommittedTransition`** (frozen dataclass): The return value on success.
Fields: `decision_id`, `transition_id`, `strategy_id` (all UUID), plus
`from_revision` and `to_revision` (int).

### Core Method: commit_transition

`commit_transition(command: TransitionCommand) -> CommittedTransition`

Executes the following steps inside a single database transaction with
`SELECT ... FOR UPDATE` row locking on the `StageState` row:

1. Validates that `actor`, `reason`, and `policy_version` are non-empty.
2. Normalizes `from_stage` and `to_stage` via
   `StrategyLifecycleManager.normalize_stage` and validates the transition is
   legal via `validate_transition`.
3. Fetches the `StrategyEntity` by slug; raises `ControlPlaneError` if absent.
4. Fetches and locks the `StageState` row; raises `ControlPlaneError` if
   absent.
5. Asserts `opt_lock == expected_revision` and `current_stage == from_stage`
   (raises `ControlPlaneConflict` on mismatch).
6. Asserts `current_version_id == command.version_id` (raises
   `ControlPlaneConflict` on mismatch).
7. Validates evidence via `_validate_evidence` (raises
   `ControlPlaneEvidenceError` on failure).
8. Inserts a `GateDecision` row (`allowed=True`).
9. Computes `next_revision = opt_lock + 1`.
10. Inserts a `StageTransition` row linked to the `GateDecision`.
11. Updates `StageState.current_stage`, `StageState.opt_lock`, and
    `StageState.updated_by` in place.
12. Inserts an `Outbox` row with `event_type="stage_transition"` and a payload
    containing `decision_id`, `from_stage`, `to_stage`, `from_revision`,
    `to_revision`, and `actor`.
13. Flushes all objects and returns a `CommittedTransition`.

All steps are atomic — if any step raises, the transaction rolls back and no
rows are written.

---

## Persistence Authority

| Store | Current Authority | Target |
|---|---|---|
| JSONL (`data/svos/`) | Current canonical control records | Migrated to PostgreSQL |
| PostgreSQL | Target canonical — evidence + approvals | Full authority after cutover |
| YAML (`config/`) | Read-only projection only | Permanent read-only |

YAML writes are forbidden for lifecycle state. See ADR-0001.

---

## Migrations

Located in `db/migrations/versions/`:

| File | Description |
|---|---|
| `001_baseline_schema_v2.py` | Baseline schema — market and research tables |
| `002_add_control_plane_v3.py` | Control-plane tables — governance, evidence, experiments, robustness, execution, operations |
| `003_harden_control_plane.py` | Hardened constraints on control-plane tables |

Migrations are managed via Alembic. The environment configuration is in
`db/migrations/env.py`.

---

## Limitations

- When `DATABASE_URL` is not set, `engine` and `SessionLocal` in
  `connection.py` are `None`. Callers must guard against this; there is no
  automatic fallback data store.
- `PostgresControlPlane` delegates transition legality checks to
  `StrategyLifecycleManager`. It does not independently enforce which stage
  transitions are valid — it trusts the manager's `validate_transition` result.
- The `Outbox` table enables downstream event consumers but no outbox relay
  worker is included in this package. Events accumulate until consumed
  externally.
- Evidence validation requires `trust="QUALIFYING_REAL"`. Imported legacy
  records (via `legacy_import.py`) are marked non-qualifying and cannot satisfy
  this gate, by design.
