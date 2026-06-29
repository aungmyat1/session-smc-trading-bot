# SVOS Architecture Summary

Date: 2026-06-29
Status: Authoritative
Version: 1.0
Load once per agent session. Replaces reading SYSTEM_ARCHITECTURE + CORE_ARCHITECTURE.

---

## 1. Platform Goal

Accept any systematic Forex strategy → produce a versioned, evidence-backed Production
Approval package OR an honest FAIL with findings and a remediation route.

Implementation ceiling: **Phase 5 / VIRTUAL_DEMO**. Production Approval is record-only.
Live trading bot is a future downstream deliverable.

---

## 2. Module Map

```
svos/                    ← main SVOS governance namespace
  lifecycle/             COMPLETE — 11 stages, transition table, loop-backs
  governance/            COMPLETE — policy gate, PASS+hash+version_id enforced
  registry/              COMPLETE — JSONL backend (data/svos/ NEVER WRITTEN)
  orchestration/         COMPLETE — coordination; delegates to governance
  reports/               COMPLETE — stage_package.py 766 lines; JSON schema defined
  shared/                PARTIAL  — GateDecision/ApprovalRecord NOT exported from __init__
  api/                   PARTIAL  — 3 read-only endpoints; no Flask app; zero tests
  deployment/            STUB     — 27 lines; no logic
  monitoring/            STUB     — 48 lines; no logic
  notifications/         PLACEHOLDER
  ui/                    PLACEHOLDER
  experiments/           PLACEHOLDER

db/                      ← PostgreSQL persistence layer (NOT YET WIRED to production)
  control_plane.py       COMPLETE — transactional, fail-closed, optimistic locking
  evidence_repository.py COMPLETE — evidence CRUD with trust/currency checks
  models.py              COMPLETE — 39 ORM tables across 11 schemas
  migrations/            COMPLETE — 3 Alembic revisions (001/002/003)
  projection.py          COMPLETE — writes YAML from PG; no active callers

pipeline/                ← Phase-0 backtest pipeline (ALL ST-A2 HARDCODED)
  pipeline_02_build_features.py  PARTIAL — signals_audit.parquet never written
  pipeline_03_replay_engine.py   PARTIAL — generate_signal_A hardcoded
  pipeline_04_write_db.py        PARTIAL — 'ST-A2' SQL hardcoded
  run_phase0.py                  PARTIAL — no --strategy flag
  config.py                      COMPLETE — spread costs, sessions; strategy-agnostic

research/                ← validation engines
  svos/engine.py         PARTIAL  — 1918 lines; 6 stage validators; god module
  svos/payload_builder.py PARTIAL — _run_backtest_session_liquidity() ST-A2 hardcoded
  validation/engine.py   PARTIAL  — validates pre-built payloads only
  robustness.py          COMPLETE — 4 functions, strategy-agnostic

strategies/adapters/     COMPLETE — 5 adapters; architecture agnostic; _PIP duplicated x4
adaptive/                COMPLETE — 14 modules; shadow engine; NewsFilter stub
monitoring/              PARTIAL  — TradeJournal (misnamed metrics.py); no daemon
dashboard/               PARTIAL  — ~20 endpoints; ST-A2-specific paths; Flask not in lock
tests/                   PARTIAL  — 1185 functions; ~50% coverage; pipeline untested
```

---

## 3. Lifecycle Stages (canonical — svos/lifecycle/manager.py)

```
DRAFT → INTAKE → AUDIT → REFINEMENT → HISTORICAL_REPLAY
→ STATISTICAL_VALIDATION → ROBUSTNESS_VALIDATION
→ VIRTUAL_DEMO → PRODUCTION_APPROVAL → REVALIDATION → RETIRED
```

Failure loops: any stage failure → REFINEMENT → re-enter failed stage.

VIRTUAL_DEMO is OFFLINE ONLY. No broker. No network. Fully deterministic.

---

## 4. Persistence Authority

| Store            | Current role               | Target role          | Status                        |
|---|---|---|---|
| JSONL (data/svos/) | Live production store    | Replaced by PG       | DIRECTORY DOES NOT EXIST      |
| PostgreSQL       | Target authoritative store | Sole authority       | Built; NOT WIRED to production|
| YAML (config/)   | Read-only catalog projection | Read-only permanent | Correctly read-only           |
| Parquet          | Frozen market + feature data | Permanent           | Functional                    |
| DuckDB           | Analytics over Parquet     | Permanent analytics  | Functional                    |
| SQLite           | Demo journal only          | No change            | Legacy; not governance        |

Key gap: `SVOSPlatform.__init__()` uses JSONL backends.
`PostgresControlPlane` and `PostgresEvidenceRepository` are built but have zero callers
in production code. Wire in P1-1.

---

## 5. Dependency Rules

```
Domain code (svos/domain/) ─────┐
Application code (svos/application/) ← domain only
Ports (svos/ports/)              ← application, domain
Adapters (db/, filesystem)       ← ports only
Interfaces (CLI, API, workers)   ← application, ports
```

**Never import Flask, SQLAlchemy, broker SDKs, or concrete filesystem paths from domain code.**

---

## 6. Governance Flow

```
Client → svos/orchestration/service.py (SVOSPlatform)
  → svos/governance/service.py (GovernanceService)
      → svos/lifecycle/manager.py (StrategyLifecycleManager)  # validates legality
      → svos/registry/service.py (StrategyRegistryService)    # persists state
          → data/svos/ JSONL  [current]
          → db/control_plane.py PostgresControlPlane  [target]
```

The governance service enforces: PASS result, evidence hash, version_id, policy_version.
It does NOT enforce numeric thresholds (PF > 1.0, n ≥ 50) — those are caller responsibility.

---

## 7. Strategy-Agnostic Gaps

These 5 locations MUST be fixed before the platform can serve a new strategy:

| File | Hardcoding |
|---|---|
| `pipeline/pipeline_03_replay_engine.py` | `generate_signal_A` import; `"ST-A-"` run_id prefix |
| `pipeline/pipeline_04_write_db.py` | SQL `'ST-A2'`, `'1.0'`; all trade_features=TRUE |
| `pipeline/run_phase0.py` | No `--strategy` flag; ST-A2 banner |
| `research/svos/payload_builder.py` | `_run_backtest_session_liquidity()` hardcoded script path |
| `pipeline/__init__.py` | Comment only (trivial) |

---

## 8. Key Technical Debt

1. `GateDecision`, `ApprovalRecord` not exported from `svos/shared/__init__.py` → `ImportError`
2. `signals_audit.parquet` documented but never written by `pipeline_02`
3. SHA-1 in `svos/shared/support.py` vs SHA-256 in `svos/adapters/artifacts.py`
4. `_PIP` table duplicated across 4 adapters
5. `research.db` + `research_sweep.db` (15.6 MB) committed to git
6. `execution_validation/tests/` has 6 files all `__test__ = False` (zero collected)
7. Dashboard Flask not in `requirements.lock` (separate `make dashboard-install`)
8. `monitoring/metrics.py` misnamed — contains TradeJournal, not metrics

---

*Detailed evidence: docs/svos/PROJECT_STATUS_REPORT_2026-06-29.md*
