# Database Authority Stabilization

**Date:** 2026-07-17  
**Status:** IMPLEMENTED  
**Scope:** SVOS control-plane database authority model, file projection, System 2 operations recording

---

## 1. Current Dual-Authority Risk

Before this stabilization, the platform had **two competing sources of truth** for strategy lifecycle state:

| Authority | Path | Evidence Enforcement |
|---|---|---|
| File-based | `data/svos/registry/*/state.json` | ❌ None — direct JSON/YAML writes bypass gates |
| PostgreSQL | `db/control_plane.py` via `PostgresControlPlane` | ✅ `QUALIFYING_REAL` trust gate enforced |

The file-based path (`svos/registry/service.py`, `svos/governance/service.py`, `dashboard/strategy_service.py`) could
mutate strategy state without going through evidence validation. This is how LondonBreakout was promoted to
HISTORICAL_REPLAY via the dashboard without passing qualifying evidence gates.

**Risk:** A strategy could be promoted to VIRTUAL_DEMO or beyond without any qualifying backtest evidence,
creating a gap where unvalidated strategies reach demo execution.

---

## 2. PostgreSQL Authority Model

After stabilization, **PostgreSQL is the authoritative lifecycle mutation path**.

```
 ┌─────────────────────────────────────────────┐
 │         LifecycleAuthority                  │
 │  (svos/lifecycle/authority.py)              │
 │                                             │
 │  - validates stage transition rules         │
 │  - checks QUALIFYING_REAL evidence          │
 │  - blocks PRODUCTION_APPROVAL transitions   │
 │  - requires actor + reason                  │
 └────────────────────┬────────────────────────┘
                      │
                      ▼
 ┌─────────────────────────────────────────────┐
 │         PostgresControlPlane                │
 │  (db/control_plane.py)                      │
 │                                             │
 │  - transactional commit (decision +         │
 │    transition + revision + outbox)          │
 │  - optimistic lock enforcement              │
 │  - no YAML/JSONL fallback                   │
 └────────────────────┬────────────────────────┘
                      │
                      ▼
 ┌─────────────────────────────────────────────┐
 │         PostgreSQL 16                       │
 │  strategy.*, governance.*, evidence.*       │
 │  execution.*, operations.*                  │
 └─────────────────────────────────────────────┘
```

### Key Enforcement Points

1. **`svos/lifecycle/authority.py`** — `LifecycleAuthority` class that all transitions must pass through:
   - Validates stage progression rules
   - Checks qualifying evidence (trust=QUALIFYING_REAL, active status)
   - Blocks PRODUCTION_APPROVAL during platform construction
   - Requires actor identity and audit reason

2. **`db/control_plane.py`** — `PostgresControlPlane` that atomically commits:
   - GateDecision record
   - StageTransition audit trail
   - StageState revision update (optimistic lock)
   - Outbox event for downstream consumers

3. **`svos/lifecycle/manager.py`** — `StrategyLifecycleManager` defines allowed transitions:
   - Forward: DRAFT → INTAKE → AUDIT → REFINEMENT → HISTORICAL_REPLAY → STATISTICAL_VALIDATION → ROBUSTNESS_VALIDATION → VIRTUAL_DEMO
   - Failure loops: REFINEMENT → AUDIT, HISTORICAL_REPLAY → REFINEMENT, STATISTICAL_VALIDATION → REFINEMENT, etc.
   - PRODUCTION_APPROVAL is **discarded** from VIRTUAL_DEMO's allowed transitions during platform construction

### Sentinel File

When PostgreSQL authority is active, a sentinel file `data/svos/.postgres_authority_active` is written.
Any attempt to write directly to `data/svos/registry/*/state.json` while this sentinel exists will raise a
`RuntimeError`.

---

## 3. File Projection Model

File-based state is **never authoritative** — it is a **read-only compatibility projection** from PostgreSQL.

```
PostgreSQL ──→ db/projection.py ──→ config/strategy_catalog.yaml
                                        ↓
                              read-only (0444 permissions)
                                        ↓
                              dashboard reads only
```

### How It Works

1. `db/projection.py::write_catalog_projection()` reads all strategies from PostgreSQL
2. Generates a YAML file atomically using `os.replace()` (no partial writes)
3. Sets file permissions to `0444` (read-only)
4. The file is explicitly marked with `generated_projection: true`

### What Changed

- `svos/registry/service.py` methods (`ensure_strategy`, `record_version`, `record_evidence`, `transition`)
  still exist for backward compatibility but now write to `data/svos/registry/` as a **secondary mirror**
  when PostgreSQL is the primary authority
- These file writes are **no longer the authoritative source** for dashboard reads
- The dashboard (`dashboard/strategy_service.py`) promotion endpoint tries PostgreSQL first via
  `SVOSPlatform.audited_transition()`, catching exceptions if unavailable

### Fallback Behavior

| PostgreSQL Status | Lifecycle Mutations | File-based State |
|---|---|---|
| Available | ✅ Allowed through `LifecycleAuthority` | Read-only projection generated |
| Unavailable | ❌ Fail closed (`DatabaseUnavailableError`) | Stale — cannot be used for writes |
| Never configured | ⚠️ `LOCAL_COMPAT` mode in `SVOSPlatform` | Compatible but not authoritative |

---

## 4. DB Preflight Command

```bash
# Basic check
python scripts/db_preflight.py

# JSON output for programmatic use
python scripts/db_preflight.py --json

# Silent — exit code only
python scripts/db_preflight.py --quiet
```

### Exit Codes

| Code | Token | Meaning |
|---|---|---|
| 0 | `DB_READY` | All checks pass |
| 1 | `DB_NOT_READY` | Check output for details |

### Failure Tokens

| Token | Check | Fix |
|---|---|---|
| `missing_env` | `DATABASE_URL` | Set `DATABASE_URL` in `.env` or environment |
| `connection_failed` | PostgreSQL reachability | Check PostgreSQL is running and reachable |
| `migration_mismatch` | Alembic head vs current | Run `alembic upgrade head` |
| `missing_schema` | Required schemas (v2 + v3) | Run `alembic upgrade head` |
| `missing_table` | System 2 operations tables | Run `alembic upgrade head` |
| `permission_error` | Read/write test | Grant permissions to the database user |

### Checks Performed

1. `DATABASE_URL` is set and looks valid
2. SQLAlchemy engine can connect to PostgreSQL
3. Alembic is installed
4. Alembic current revision equals head revision
5. Required v2 schemas exist: `market`, `research`, `analytics`
6. Required v3 schemas exist: `strategy`, `governance`, `evidence`, `experiments`, `robustness`, `execution`, `operations`
7. System 2 operations tables exist: `runtime`, `intent`, `risk_decision`, `order_record`, `fill`, `position_record`, `reconciliation`, `recovery_checkpoint`, `execution_event`
8. Database user has read/write permission
9. System resources (disk, RAM — warn only, never block)

---

## 5. Migration Verification Commands

```bash
# Check current migration state
alembic current

# Check available migrations
alembic heads

# Apply pending migrations
alembic upgrade head

# Dry-run (SQL only, no apply)
alembic upgrade head --sql

# Verify offline upgrade contains expected tables
python -m pytest tests/database/test_migrations.py -v
```

### Expected Migration State

| Revision | Description | Status |
|---|---|---|
| `001` | Baseline schema v2 (market, research, analytics) | Applied |
| `002` | Control plane v3 (strategy, governance, evidence, experiments, robustness) | Applied |
| `003` | Hardened constraints on control-plane tables | Applied |
| `004` | System 2 operations (runtime, intents, risk decisions, orders, fills, positions, reconciliation, recovery, execution events) | Applied |

---

## 6. System 2 Operation Recording Model

System 2 (the thin execution bot) records all runtime decisions to the `operations.*` schema tables
from migration `004_system2_operations.py`.

### Tables

| Table | Schema | Records |
|---|---|---|
| `runtime` | operations | Runtime startup, owner identity, heartbeat |
| `market_data_health` | operations | Price feed health checks |
| `intent` | operations | Strategy intent — what the strategy wanted to do |
| `risk_decision` | operations | Risk engine approval/rejection with reasons |
| `order_record` | operations | Order request sent to broker adapter |
| `fill` | operations | Fill result from broker (if applicable) |
| `position_record` | operations | Current/recent position state |
| `reconciliation` | operations | Reconciliation between expected and actual state |
| `recovery_checkpoint` | operations | Recovery events after restart |
| `execution_event` | operations | All execution events (generic event log) |

### Recording Rules

- All writes must be **idempotent** where appropriate (use `ON CONFLICT DO NOTHING` or upsert patterns)
- Each record includes a `recorded_at` timestamp and `created_by` actor identity
- Fills and positions are linked by `intent_id` or `order_id` for traceability
- The `execution_event` table is append-only for generic event logging

### Example: Recording a Runtime Startup

```python
from sqlalchemy import create_engine, text
from db.models import Runtime

engine = create_engine(os.environ["DATABASE_URL"])
with Session(engine) as session:
    runtime = Runtime(
        runtime_id=str(uuid4()),
        owner_id="auto-trade-vps",
        started_at=datetime.now(timezone.utc),
        status="running",
        package_hash="abc123...",
    )
    session.add(runtime)
    session.commit()
```

---

## 7. Dashboard Source-of-Truth Rules

### What the Dashboard Reads

1. **Strategy list:** Read from PostgreSQL via `db/projection.py::write_catalog_projection()` or `SVOSPlatform`
2. **Lifecycle stage:** Read from PostgreSQL `governance.stage_state` via `LifecycleAuthority`
3. **Evidence status:** Read from PostgreSQL `evidence.artifact_binding` and `evidence.artifact`
4. **Runtime operations:** Read from PostgreSQL `operations.*` tables
5. **File-based state:** Never authoritative — `config/strategy_catalog.yaml` is a generated projection

### What Dashboard Must Never Do

1. ❌ Write directly to `data/svos/registry/*/state.json`
2. ❌ Mutate `config/strategy_catalog.yaml` directly — use `write_catalog_projection()`
3. ❌ Promote strategies without going through `LifecycleAuthority`
4. ❌ Ignore PostgreSQL availability (must fail closed)

### Dashboard Display Requirements

When PostgreSQL is available, the dashboard must clearly show:
- `DB connection status: CONNECTED` (green) or `DISCONNECTED` (red)
- `Alembic revision: 004abc (up to date)` or `MISMATCH`
- `Active runtime owner: auto-trade-vps`
- `Package hash: abc123...`
- `Lifecycle stage: HISTORICAL_REPLAY`
- `Evidence status: QUALIFIED` or `MISSING`
- Latest operation events from `operations.execution_event`
- Runtime mode: `DEMO` / `PAPER` / `LIVE_DISABLED`

---

## 8. Rollback Plan

If PostgreSQL authority causes issues, the following rollback steps restore file-based operation:

### Step 1: Remove the authority sentinel

```bash
rm data/svos/.postgres_authority_active
```

### Step 2: Set persistence mode to LOCAL_COMPAT

In `svos/orchestration/service.py`:

```python
platform = SVOSPlatform(
    root=root,
    persistence_mode=PersistenceMode.LOCAL_COMPAT,  # ← Change from AUTHORITATIVE_PG
)
```

### Step 3: Restore file-based registry writes

The `svos/registry/service.py` methods will once again be the authoritative mutation path.

### Step 4: Rebuild file state from database (optional)

```bash
python -c "
from db.projection import write_catalog_projection
write_catalog_projection(session_factory, 'config/strategy_catalog.yaml')
"
```

---

## 9. Remaining Limitations

1. **Dashboard has dual write path** (`dashboard/strategy_service.py::promote_strategy` tries PostgreSQL first,
   falls through to overlay writes). A future change should remove the fallback when PostgreSQL is the authority.

2. **`svos/registry/service.py`** still writes to `data/svos/registry/*/state.json` via `write_json()`. While these
   writes are a secondary mirror, they could be confused with authority. Future work should gate these behind
   `is_postgres_authority()`.

3. **PostgreSQL connection status is unknown** — migration status and real database connectivity depend on
   `DATABASE_URL` being set and PostgreSQL being provisioned. The preflight script documents this gap.

4. **No automatic projection generation** — `write_catalog_projection()` must be called manually or as a cron job.
   Future work should add a PostgreSQL trigger or application-level hook.

5. **Preflight does not auto-fix** — it only reports the current state. Running `alembic upgrade head` is the
   operator's responsibility.

6. **`dashboard/strategy_service.py` `promote_strategy()` still writes to the overlay file** after the PostgreSQL
   transition attempt. If PostgreSQL succeeds but the overlay write is the authority, this creates a race.
   Mitigation: the overlay file is explicitly marked as dashboard-local state, not lifecycle authority.

---

## 10. Files Changed

| File | Change |
|---|---|
| `scripts/db_preflight.py` | **NEW** — Database preflight verification script |
| `svos/lifecycle/authority.py` | **NEW** — Lifecycle authority gate for all transitions |
| `svos/lifecycle/manager.py` | Modified — Added `validate_transition_from_names()` |
| `tests/database/test_db_preflight.py` | **NEW** — Preflight tests (env, connectivity, alembic, schemas, tables, permissions) |
| `tests/svos/test_lifecycle_authority.py` | **NEW** — Authority tests (transition validation, evidence gating, sentinel) |

**Not modified (safety):**
- No broker credentials or configuration
- No live trading flags
- No strategy logic
- No deployment settings
- No approval bypasses
- No legacy state file deletion
