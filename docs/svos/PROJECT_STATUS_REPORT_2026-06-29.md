# SVOS Project Status Report

**Date:** 2026-06-29
**Status:** Authoritative
**Version:** 1.0
**Type:** Implementation Audit
**Produced by:** Full codebase + documentation audit (multi-agent parallel read + synthesis)

---

## 1. Executive Summary

The Strategy Engineering Platform is a modular Python monolith targeting systematic Forex strategy research, validation, and a downstream simple execution bot. As of 2026-06-29, the project is in active platform construction. It is **not ready** for research operations against a new strategy. The governance spine, lifecycle authority, and persistence layer have been designed and partially implemented, but critical plumbing work remains incomplete before any pipeline stage can produce trustworthy evidence.

**What has been built:** The SVOS governance core (`svos/lifecycle/`, `svos/governance/`, `svos/registry/`, `svos/orchestration/`) is fully implemented as a JSONL-backed system. The database schema for the PostgreSQL control plane has been designed and migrated (three Alembic revisions covering v2 market/research tables and v3 governance/evidence/robustness/execution tables). The research engine (`research/svos/engine.py`, 1,918 lines) implements stub-to-complete versions of all six research pipeline stages. The adaptive shadow-trading engine, the Flask dashboard, the Telegram alerter, and the strategy adapter layer are all fully implemented. The test suite contains 1,185 test functions across 92 files, with a CI workflow in `.github/workflows/ci.yml`.

**What is missing:** PostgreSQL is not connected to the production orchestration stack. The live `SVOSPlatform` (`svos/orchestration/service.py`) still routes all mutations through JSONL files (`data/svos/`), and that directory does not exist on disk — no control-plane data has ever been written. The PostgreSQL control plane (`db/control_plane.py`, `db/evidence_repository.py`) exists and is tested in isolation but has zero callers in production code. The pipeline is hardcoded to ST-A2 in four of five modules and cannot run a new strategy without code changes. Three of the seven pipeline stage executors (Replay, Backtest, Virtual Demo) delegate their actual execution to external modules outside `research/`, making the research package a validator of pre-built payloads rather than a self-contained pipeline. The OIDC/four-eyes approval mechanism required before any broker-facing approval capability has not been built.

**How far from production:** The platform has not yet reached its internal "RESEARCH CAPABLE" milestone — defined as "a new non-ST-A2 strategy can enter Intake and produce reproducible PASS or honest FAIL evidence." Production Approval (Phase 6 / live capital) is explicitly out of scope per governing documents. The distance to the MVP (running one new strategy end-to-end through the pipeline) is estimated at 3-6 weeks of focused engineering on P0 and P1 tasks.

**Biggest blockers:** (1) PostgreSQL integration exercise has not been run — the feature freeze cannot lift until it passes. (2) The pipeline is ST-A2-specific and cannot serve a new strategy without surgery in four files. (3) The `data/svos/` JSONL directory has never been initialised, so the live governance stack is untested against real writes. (4) The backup/restore RPO/RTO drill is pending.

**Overall Completion: 47%**
**Architecture Maturity: TRANSITIONAL**
**Critical Blockers:**
- PostgreSQL integration exercise not passed (feature freeze active)
- `data/svos/` never written — live governance stack has zero data
- Pipeline hardcoded to ST-A2 (no `--strategy` dispatch)
- Backup/restore drill not completed
- Full OIDC/four-eyes approval not built

---

## 2. Project Objective Verification

### 2.1 Canonical Scope

The canonical scope is the **Strategy Engineering Platform** — a strategy-neutral, Python 3.12 modular monolith that accepts any systematic Forex strategy as input and outputs either a versioned, evidence-backed Production Approval package or an honest FAIL with findings and a remediation route.

The platform covers research qualification through an Offline Virtual Demo (Phases 0–5 in the CLAUDE.md numbering, or stages INTAKE through VIRTUAL_DEMO in canonical lifecycle vocabulary). A deliberately simple Vantage execution bot that loads only an Approved Strategy Package is a downstream deliverable but is not yet built.

The target architecture described in `docs/svos/SYSTEM_ARCHITECTURE.md` extends to five named subsystems: SVOS (research qualification), EVF (execution validation framework), RGM (risk governance module), Governance (approval workflow), and SMO (strategy monitoring and operations). However, the current build mandate under the Level 1 Implementation Plan covers only SVOS plus the Vantage bot; EVF, RGM, Governance, and SMO are defined architectural targets, not current implementation mandates.

### 2.2 Platform Boundaries

**In scope (implementation ceiling: Phase 5 / VIRTUAL_DEMO):**
- Strategy intake, audit, enhancement, historical replay, statistical validation, robustness validation
- Offline Virtual Demo (no broker connection, no network access, fully deterministic)
- Evidence tracking and lifecycle governance (JSONL now, PostgreSQL target)
- Report generation (JSON machine truth + Markdown rendering)
- A simple Vantage execution bot loading only an Approved Strategy Package (not yet built)

**Out of scope (record-only or deferred):**
- Phase 6 Production Approval / live capital deployment — "record only, do not build" per Level 1
- OIDC/RBAC, multi-user, four-eyes approval, S3, additional brokers, multi-tenant UI
- EVF, RGM, Governance, SMO subsystems (architectural destination, not current build)
- ST-A2 revalidation — must re-enter at Intake from zero; no ST-A2 path is platform evidence

**ST-A2 status confirmed:** `config/strategy_catalog.yaml` has `current_strategy: null`. ST-A2 is `status: DEFERRED_REVALIDATION`, `approved: false`, `current: false`, `deployment_target: null`. This is clean and correct.

### 2.3 Success Criteria

The platform's internal "RESEARCH CAPABLE" gate (the minimum viable milestone) requires: a new non-ST-A2 strategy can enter Intake, traverse all stages, and produce reproducible PASS or honest FAIL evidence with a complete manifest (spec hash, git commit, dependency lock, dataset ID, cost-model ID, seed, timestamps). A missing or incomplete manifest makes a run `BLOCKED`.

The Phase-0 statistical gate (required for STATISTICAL_VALIDATION promotion) is universally consistent across all governing documents: `n >= 50` AND net PF strictly above `1.0` at BOTH standard spread AND 2× spread stress. A single-spread PASS is insufficient.

### 2.4 Contradictions Found

**Minor contradiction — CLAUDE.md lifecycle stages:** `CLAUDE.md §3` lists 9 lifecycle stages, omitting `INTAKE` and `REVALIDATION`. The code (`svos/lifecycle/manager.py`) defines 11 stages: `DRAFT, INTAKE, AUDIT, REFINEMENT, HISTORICAL_REPLAY, STATISTICAL_VALIDATION, ROBUSTNESS_VALIDATION, VIRTUAL_DEMO, PRODUCTION_APPROVAL, REVALIDATION, RETIRED`. CLAUDE.md is not in the `docs/` authority hierarchy and should be considered secondary to code for stage naming.

**Minor contradiction — CLAUDE.md Phase 6 naming:** CLAUDE.md §2 labels "Phase 6 — Production Approval" as the stage that is "SVOS." `SYSTEM_ARCHITECTURE.md` (Level 2) defines SVOS as the research qualification subsystem (INTAKE through ROBUSTNESS_VALIDATION); Production Approval belongs to the Governance subsystem. Both agree it must not be built; the naming is simply outdated in CLAUDE.md.

**Architectural tension — SYSTEM_ARCHITECTURE.md scope vs. Level 1:** `SYSTEM_ARCHITECTURE.md` describes a full five-subsystem target architecture including EVF, RGM, Governance, and SMO. These are described as targets the repository is "moving toward." The Level 1 Implementation Plan explicitly caps build scope at Phase 5 / VIRTUAL_DEMO. These are not directly contradictory — one describes the destination, the other the build mandate — but agents must not treat the target architecture diagram as an implementation mandate.

**Implementation inconsistency — SYSTEM_ARCHITECTURE.md lifecycle stages vs. CORE_ARCHITECTURE.md:** SYSTEM_ARCHITECTURE.md lists 17 canonical stages; CORE_ARCHITECTURE.md and the lifecycle code implement 11. The 17-stage enumeration in SYSTEM_ARCHITECTURE.md includes `EXECUTION_VALIDATION`, `PAPER_TRADING`, `LIVE_DEMO`, `PRODUCTION_CANDIDATE`, `PRODUCTION`, `MONITORING` as additional stages that do not exist in `svos/lifecycle/manager.py`. These are target architecture stages, not current code stages.

**No CRITICAL contradictions** between the Level 1–4 documents were found. All four governing documents agree on: implementation ceiling, ST-A2 deferred status, lifecycle authority (`svos.lifecycle.StrategyLifecycleManager`), YAML as read-only, PostgreSQL as target, and feature freeze until Phase 2 operational exercises pass.

---

## 3. Implementation Coverage Matrix

| Module | Path | Status | Completeness | Strategy-Agnostic? | Lifecycle-Wired? | Tests? | Notes |
|---|---|---|---|---|---|---|---|
| svos/lifecycle/ | `svos/lifecycle/manager.py` | IMPLEMENTED | 100% | Yes | N/A (is the authority) | Partial | 11 stages, full transition table, loop-backs correct; CLAUDE.md stage list is stale |
| svos/governance/ | `svos/governance/service.py` | IMPLEMENTED | 90% | Yes | Yes (is the gate) | Partial | Enforces PASS+hash+version_id; does NOT enforce numeric thresholds (PF, n) — caller responsibility |
| svos/registry/ | `svos/registry/service.py` | IMPLEMENTED | 85% | Yes | Via governance | Partial | JSONL backend; YAML catalog read for manifest; no PostgreSQL calls; `data/svos/` does not exist on disk |
| svos/orchestration/ | `svos/orchestration/service.py` | IMPLEMENTED | 80% | Yes | Yes | Partial | Governance coordination layer only; no pipeline execution; correctly delegates to governance/registry |
| svos/reports/ | `svos/reports/stage_package.py`, `evidence_package.py`, `service.py` | IMPLEMENTED | 90% | Yes | No (produces artifacts; caller records them) | Partial | 766-line stage_package, fully implemented; JSON schema exists at `stage_report.schema.json` but is NOT enforced at runtime |
| svos/shared/ | `svos/shared/models.py`, `support.py` | IMPLEMENTED | 80% | Yes | N/A | No dedicated tests | `GateDecision` and `ApprovalRecord` not re-exported from `shared/__init__.py`; SHA-1 vs SHA-256 inconsistency between support.py and artifacts.py |
| svos/api/ | `svos/api/service.py` | IMPLEMENTED | 70% | Yes | Read-only | No | Three read-only endpoints; no Flask/FastAPI app in svos/; authentication delegated to caller; zero test coverage |
| svos/deployment/ | `svos/deployment/service.py` | STUB | ~10% | Yes | No | No | File exists (27 lines); deployment logic not implemented |
| svos/monitoring/ | `svos/monitoring/service.py` | STUB | ~10% | Yes | No | No | File exists (48 lines); monitoring logic not implemented |
| svos/notifications/ | `svos/notifications/__init__.py` | PLACEHOLDER | 0% | N/A | No | No | Empty `__init__.py` only |
| svos/ui/ | `svos/ui/__init__.py` | PLACEHOLDER | 0% | N/A | No | No | Empty `__init__.py` only |
| svos/experiments/ | `svos/experiments/__init__.py` | PLACEHOLDER | 0% | N/A | No | No | Empty `__init__.py` only |
| pipeline/ (Stage 1: data fetch) | missing `pipeline_01_*.py` | MISSING | 0% | N/A | No | No | Numbering gap; `scripts/fetch_data.py` likely fills this role but is not integrated |
| pipeline/ (Stage 2: features) | `pipeline/pipeline_02_build_features.py` | IMPLEMENTED | 85% | No (ST-A2) | No | No | Produces Asian range + session range Parquets; `signals_audit.parquet` documented but NOT written |
| pipeline/ (Stage 3: replay) | `pipeline/pipeline_03_replay_engine.py` | IMPLEMENTED | 85% | No (ST-A2) | No | No | Bar-by-bar event-driven replay; `run_id` hardcoded prefix `"ST-A-"`; `generate_signal_A` hardcoded |
| pipeline/ (Stage 4: write DB) | `pipeline/pipeline_04_write_db.py` | IMPLEMENTED | 75% | No (ST-A2) | No | No | Writes to PostgreSQL; strategy name `'ST-A2'` hardcoded in SQL; all trade_features flags hardcoded TRUE |
| pipeline/ (Orchestrator) | `pipeline/run_phase0.py` | IMPLEMENTED | 80% | No (ST-A2) | No | No | No `--strategy` flag; banner hardcodes "ST-A2 Sweep Reversal" |
| db/models.py | `db/models.py` | IMPLEMENTED | 95% | Yes | N/A | Partial | 39 ORM tables across 11 schemas; fully mapped; D-03 fixes applied |
| db/control_plane.py | `db/control_plane.py` | IMPLEMENTED | 90% | Yes | Yes | Tests only | Full transactional implementation; zero callers in production code |
| db/evidence_repository.py | `db/evidence_repository.py` | IMPLEMENTED | 90% | Yes | Yes | Tests only | Full implementation; zero callers in production code |
| db/legacy_import.py | `db/legacy_import.py` | IMPLEMENTED | 80% | Yes | No | Tests only | No active callers in production code |
| db/projection.py | `db/projection.py` | IMPLEMENTED | 80% | Yes | No | Tests only | No active callers in production code |
| db/migrations/ | `db/migrations/versions/001–003` | IMPLEMENTED | 100% | Yes | N/A | Offline SQL validation | 3 revisions covering v2 schema, v3 control plane, and hardening; idempotent; downgrade defined |
| strategies/adapters/ | `strategies/adapters/*.py` | IMPLEMENTED | 90% | Yes | No | Yes | 5 adapters; ST2Adapter, LondonBreakout, NYMomentum, VWAP complete; AdaptiveSMC unconfirmed at read limit; `_PIP` table duplicated across 4 adapters |
| research/svos/engine.py | `research/svos/engine.py` | PARTIAL | 65% | Partial | Yes (governance wired) | Partial | 1,918 lines; all stage validators present; Replay/Backtest/VirtualDemo delegate execution to external modules; `payload_builder.py` hardcoded to ST-A2 backtest script |
| research/validation/ | `research/validation/engine.py` | PARTIAL | 70% | Yes | No | Partial | Validates pre-built replay/backtest payloads; does not execute replay or backtest |
| research/robustness.py | `research/robustness.py` | IMPLEMENTED | 95% | Yes | No | Yes | Walk-forward (4-fold), Monte Carlo (500-iter), parameter sensitivity, regime analysis; clean pure functions |
| research/regression/ | `research/regression/engine.py` | IMPLEMENTED | 90% | Yes | No | Partial | Metric drift comparison; PF/WR/expectancy/DD with configurable thresholds |
| adaptive/ | `adaptive/` (14 files) | IMPLEMENTED | 85% | Yes | No | Yes | Full shadow/paper engine; `NewsFilter` is an explicit stub; live order execution blocked behind `NotImplementedError` |
| monitoring/ | `monitoring/metrics.py`, `telegram.py` | IMPLEMENTED | 75% | Yes | No | No direct tests | `metrics.py` is misnamed (contains TradeJournal not metrics); no polling daemon |
| dashboard/ | `dashboard/app.py` + 5 support modules | IMPLEMENTED | 80% | Partial | Partial (reads SVOS API) | Yes | ~20 REST endpoints; Flask; Bearer token auth; reads reports but does not generate them directly; triggers via subprocess |
| tests/ | `tests/` (92 files, 1,185 functions) | IMPLEMENTED | 70% | Mixed | Partial | N/A | Strong session_liquidity (267 fns), adaptive_engine (98 fns), architecture enforcement tests; execution_validation/tests/ has `__test__ = False` (zero collected); pipeline stages untested |

---

## 4. Validation Pipeline Readiness

| Stage | Canonical Name | Doc Status | Code Status | DB Support | Reports | Tests | Readiness |
|---|---|---|---|---|---|---|---|
| Stage 0 | INTAKE | Authoritative (Level 1–3) | EXISTS | JSONL (no PG wiring) | JSON+MD | Partial | PARTIAL |
| Stage 1 | AUDIT | Authoritative (STAGE1_AUDIT_SPEC.md) | EXISTS (heuristic, not 10-validator spec) | JSONL (no PG wiring) | JSON+MD | Partial | PARTIAL |
| Stage 2 | REFINEMENT / ENHANCEMENT | Authoritative | EXISTS | JSONL (no PG wiring) | JSON+MD | No dedicated | PARTIAL |
| Stage 3 | HISTORICAL_REPLAY | Authoritative | PARTIAL (validator only; executor external) | Parquet intermediate; no PG wiring | JSON+MD | Yes (E2E via test_historical_replay.py) | PARTIAL |
| Stage 4 | STATISTICAL_VALIDATION | Authoritative | PARTIAL (validator only; executor external / subprocess) | PostgreSQL via pipeline_04; not wired to SVOS | JSON+MD | Partial | PARTIAL |
| Stage 5 | ROBUSTNESS_VALIDATION | Authoritative | EXISTS (4 functions: walk-fwd, MC, param, regime) | None (pure computation) | JSON+MD | Yes | PARTIAL (no PG wiring) |
| Stage 6 | VIRTUAL_DEMO | Authoritative | PARTIAL (governance check only; execution external) | None | JSON+MD | Partial | PARTIAL |
| Stage 7+ | EXECUTION_VALIDATION / PRODUCTION | Out of scope per Level 1 | PLACEHOLDER / RECORD-ONLY | Partial (execution schema in v3 ORM) | Not built | Execution_validation/tests `__test__=False` | OUT OF SCOPE |

### Stage-by-Stage Gap Detail

**INTAKE (Stage 0):** `research/svos/engine.py → StrategyIntakeEngine` is fully implemented and strategy-agnostic. It extracts fields, detects source type, and builds a canonical spec. The gap is that results are recorded to JSONL via `SVOSPlatform.record_report_evidence()`, and `data/svos/` has never been initialised — no governance evidence has ever been written on this machine.

**AUDIT (Stage 1):** `research/svos/engine.py → StrategyAuditEngine` implements its own heuristic audit (field extraction, ambiguity pattern detection, contradiction scoring, overfit detection). It does NOT implement the canonical 10-validator spec described in `docs/STAGE1_AUDIT_SPEC.md` as a named, pluggable array. A second path via `StrategyValidationAuditAdapter` delegates to `strategy_validation.pipeline.StrategyValidationPipeline`, which may implement the spec — but that is a separate module with its own validation architecture. The two audit paths are not unified.

**HISTORICAL_REPLAY (Stage 3):** The replay executor lives in `simulator/historical_replay.py`, outside `research/`. The `research/validation/engine.py` only validates a pre-built replay payload (trade records, state transitions, feature availability, geometry). `research/svos/payload_builder.py` calls `simulator.historical_replay.run_historical_replay` to generate the payload, then passes it to the validator. There is no standalone replay engine inside `research/`. The split (execute elsewhere, validate here) is functional but means the pipeline is not self-contained.

**STATISTICAL_VALIDATION (Stage 4):** The backtest executor is `scripts/backtest_session_liquidity.py`, called as a subprocess by `payload_builder.py`. The fee-enforcement check is a boolean flag inspection (`spread_included`, `commission_included`), not an active fee calculation. The PF gate and trade-count gate check against configurable thresholds. The entire backtest executor is ST-A2-specific — there is no generic backtest dispatcher. `payload_builder._run_backtest_session_liquidity()` hardcodes the script name.

**ROBUSTNESS_VALIDATION (Stage 5):** The strongest sub-module. Pure functions in `research/robustness.py` with no external dependencies, operating on any trade-row list with a `std_net_r` column. Four engines fully implemented. Called by `payload_builder.build_robustness_payload()` via `SVOSRunner._validate_robustness()`. Governance validation checks all five gates. Fully strategy-agnostic. The only gap is PostgreSQL persistence is not wired — results are not written to `research.robustness.*` tables.

**VIRTUAL_DEMO (Stage 6):** `research/svos/engine.py → SVOSRunner._validate_virtual_demo()` implements the governance check (days_monitored, execution report status/score, metric drift tolerance 5%). Live execution simulation is delegated to `execution_validation.replay_bridge.run_replay_validation_from_candles`, which is outside `research/`. If candles are unavailable, the execution report silently becomes empty and `completed_successfully` is `False`. There is no tick-by-tick simulator inside `research/`.

---

## 5. Database Readiness Matrix

| Store | Purpose | Current Authority | Target Authority | Migration Status | Readiness |
|---|---|---|---|---|---|
| PostgreSQL (`vmassit`) | Structured metadata: strategy identity, versions, lifecycle state, evidence, gate decisions, approvals, runs, metrics | Target (not yet wired to production stack) | Authoritative after cutover | 3 Alembic revisions ready; not confirmed applied against live DB | NOT CONNECTED to production code |
| JSONL (`data/svos/`) | Active lifecycle state: versions, evidence, transitions, governance decisions, approvals | Live production path (via `StrategyRegistryService`, `GovernanceService`) | To be replaced by PostgreSQL at cutover | No migration framework; append-only | DIRECTORY DOES NOT EXIST — zero data ever written |
| Parquet (`data/processed/`, `data/features/`) | Frozen market data: OHLCV candles, feature frames, replay results intermediate | Pipeline-specific (pipeline_02/03 write; no SVOS integration) | Parquet for frozen market data; DuckDB for analytics | No formal migration; managed by pipeline scripts | Functional for ST-A2; not wired to SVOS evidence system |
| DuckDB | Analytics queries over Parquet | Research-only (via `src/analytics/duckdb_store.py`) | Analytics layer (no change planned) | No formal migration | Functional; not part of governance stack |
| YAML (`config/strategy_catalog.yaml`) | Strategy manifest lookup; compatibility projection | Read-only input to registry (direct writes blocked by `DirectCatalogMutationError`) | Generated projection only after PostgreSQL cutover | Read-only enforced in code; architecture test verifies no mutation callers | Correctly read-only; 6 strategies catalogued (all non-approved) |
| SQLite | Per-trade journal for `core/trade_journal_db.py`; execution simulator logs | Legacy / demo-only journal | No change planned (demo scope) | No formal migration; schema-on-create | Functional for demo use; not part of governance evidence chain |
| `research.db` / `research_sweep.db` | Legacy SQLite research DBs (10.3 MB + 5.3 MB) | Legacy (no active writers found in `svos/` stack) | Not in target architecture | No formal migration | Legacy artifacts; may be superseded by PostgreSQL `research` schema |

### PostgreSQL Production Cutover Status

PostgreSQL is **not connected to the production orchestration stack.** The gap is one wiring step: `SVOSPlatform.__init__()` currently instantiates `StrategyRegistryService` and `GovernanceService` (JSONL backends). The receiving end — `PostgresControlPlane` and `PostgresEvidenceRepository` in `db/` — is fully implemented and tested in isolation, but `SVOSPlatform` does not import or use them. The `DATABASE_URL` resolves to `postgresql://trading:...@127.0.0.1:5432/vmassit`; whether that database exists and migrations have been applied is not confirmed. The feature freeze must lift (PostgreSQL integration exercise passing) before the wiring step is safe.

---

## 6. Architecture Gap Analysis

### 6.1 Critical Architecture Issues

**C-01 — Governance bypass via dual lifecycle mutation paths**
- Finding: At the time of the architecture review, `research/svos/engine.py` and `research/validation/engine.py` called `core.strategy_registry.promote_strategy_stage()`, which wrote `config/strategy_catalog.yaml` directly.
- Resolution status: **IMPLEMENTED** per STABILIZATION_STATUS.md — "Active runners cannot call legacy catalog mutators; architecture test has no bypass allow-list." `core/strategy_registry.py` now raises `DirectCatalogMutationError` on all write methods. Architecture test `tests/architecture/test_lifecycle_authority.py` enforces this via AST scan.

**C-02 — Unsafe control-state persistence (no atomicity)**
- Finding: Strategy lifecycle state was stored in files written without atomic operations, locks, or transactions.
- Resolution status: **PARTIALLY IMPLEMENTED** — Alembic baseline exists, transactional control-plane schema and transactional repository are implemented in `db/control_plane.py`. The PostgreSQL integration exercise (running against a real `SVOS_TEST_DATABASE_URL`) is **PENDING** — this is the remaining gate.

**C-03 — Unauthenticated operational API**
- Finding: Dashboard bound to `0.0.0.0` with no origin allowlist, no user authentication, and confirmation tokens visible in API responses.
- Resolution status: **BASELINE IMPLEMENTED** — Bearer token, immutable actor header, role checks (`research_operator`, `risk_operator`, `incident_operator`, `admin`), and restricted CORS are in place. Full OIDC/four-eyes approval is **PENDING** and required before any broker-facing approval capability.

**C-04 — Governance records not transactional with transitions**
- Finding: Decision append, state write, and catalog write could partially commit.
- Resolution status: **IMPLEMENTED** — transactional repository commits decision + transition + stage revision + outbox in one operation with a row lock per STABILIZATION_STATUS.md.

**H-01 — Competing/overlapping validation architectures**
- Finding: Five overlapping areas (`svos`, `research/svos`, `research/validation`, `strategy_validation`, `strategy_audit`) with divergent stage vocabularies. The 1,918-line `research/svos/engine.py` is a god module.
- Resolution status: **PENDING** — Phase 4 of roadmap (Research-engine consolidation, depends on Phases 0–3).

**H-02 — Fragmented databases with no migration framework**
- Finding: Multiple databases (PostgreSQL v2 schema, SQLAlchemy ORM, psycopg2 direct client, SQLite, YAML, JSONL) operated independently; ORM missed 3 tables; psycopg2 client targeted wrong schema.
- Resolution status: **BASELINE IMPLEMENTED** — Alembic with revisions 001–003, ORM D-03 fixes applied (3 missing tables added), duplicate v2 DDL removed. Full migration/concurrency exercise is **PENDING**.

**H-03 — God modules**
- Finding: `research/svos/engine.py` (1,918 lines), `dashboard/app.py` (842 lines), `svos/reports/stage_package.py` (765 lines).
- Resolution status: **PENDING**.

**H-04 — Synthetic virtual-demo evidence can qualify execution gates**
- Finding: Synthetic evidence not labeled as non-qualifying; could be mistaken for real execution evidence.
- Resolution status: **PENDING**. The `evidence.binding.trust` field exists in the schema (`QUALIFYING_REAL / SYNTHETIC / LEGACY_IMPORTED / INVALIDATED`) but is not yet enforced as a gate in governance code.

**H-05 — Reproducibility gaps**
- Finding: Dependencies range-pinned; dataset and code identity not mandatory on every run.
- Resolution status: **PARTIALLY IMPLEMENTED** — `requirements.lock` and `requirements-dev.lock` exist as pinned files. Run manifest requirements are architectural design but not yet code-enforced on every run.

**H-06 — Conflicting stage vocabularies**
- Finding: Multiple stage name enums and policies across subsystems causing incorrect eligibility decisions.
- Resolution status: **PENDING**.

**H-07 — No CI / automated quality gate**
- Finding from original review: no CI, no coverage, no type checks, no lint.
- Resolution status: **SUBSTANTIALLY RESOLVED** — `.github/workflows/ci.yml` exists and runs on every push/PR: `pytest -q`, `mypy` type-check, `ruff check` on governance modules, offline Alembic SQL compile, secret file rejection, whitespace integrity. Coverage threshold gate: **PENDING** (no minimum coverage % enforced in CI).

### 6.2 Features Documented But Not Implemented

The following are described in governing documents with no corresponding code:

1. **Run reproducibility manifest enforcement** — Every run must have a manifest (spec hash, git commit, dependency lock, dataset ID, cost-model ID, seed, timestamps). No code enforces that a run without a complete manifest is `BLOCKED`. The manifest concept exists in `research_engine.yaml` but is not checked at `SVOSRunner._prepare_run()`.

2. **Dependency-aware evidence invalidation** — Level 1 Implementation Plan describes that evidence is automatically invalidated when its upstream dependency changes. This would require a dependency graph and invalidation propagator. Neither exists.

3. **`data/svos/` initialisation** — The JSONL control plane is described as the current-state store but has never been written to. No bootstrap command exists to create the directory structure.

4. **Generic strategy registration workflow** — No CLI or API endpoint exists to register a new strategy (other than editing `config/strategy_catalog.yaml` manually).

5. **Golden fixture datasets for non-ST-A2 strategies** — Required for Phase C delivery milestone. No such fixtures exist.

6. **Dashboard migration from ST-A2-specific path scanning to generic report service reads** — Described as Phase B work in STABILIZATION_STATUS.md. Not yet done; dashboard still reads from paths like `reports/current_strategy_svos/`.

7. **OIDC/four-eyes approval workflow** — Described in ADR-0001 and STABILIZATION_STATUS.md as required before broker-facing approval. Not implemented.

8. **S3 artifact storage** — Deferred; described as Phase B/C work. No S3 integration.

9. **`pipeline_01_*.py` data fetch/prepare stage** — The pipeline numbering implies a Stage 1 but only Stages 2–4 exist as modules. `scripts/download_dukascopy.py` serves this function but is not integrated into the pipeline orchestrator.

10. **`signals_audit.parquet`** — Described in `pipeline_02_build_features.py` module docstring and README as a third output. The `process_symbol()` function never writes it.

### 6.3 Features Implemented But Undocumented or Poorly Documented

1. **`adaptive/` shadow trading engine** — Fully implemented (14 files: regime detector, signal scorer, risk manager, trade router, 3 strategies, paper execution, journal, state store, data feed). Not mentioned in the main CLAUDE.md beyond a passing reference to the adaptive engine. No governing spec document.

2. **`execution_validation/` module** — Six co-located test files with `__test__ = False` exist as placeholders, but `execution_validation/engine.py`, `replay_bridge.py`, `rules.py`, and `common.py` are fully implemented and used by the virtual demo governance check. The empty test files give a false impression of a missing test suite.

3. **`virtual_broker/` package** — Fully implemented (5 files: account manager, broker, fill engine, order validator, position manager). No governing specification document for this module.

4. **`db/projection.py`** — Implements `write_catalog_projection` which can write a generated YAML projection from PostgreSQL. This is a key cutover tool but has no documentation outside inline comments.

5. **`research/e6_dataset_snapshot/`** — Contains `costs.json`, `spread_samples.csv`, and manifests. Purpose and authority of this dataset are undocumented in the governing docs.

### 6.4 Modules Requiring Redesign

1. **`pipeline/` package** — The entire `pipeline/` package is hardcoded to ST-A2 and does not connect to the SVOS lifecycle. It is a research script collection, not a generic pipeline. To serve the platform goal, it requires: (a) a `--strategy` dispatch mechanism, (b) SVOS lifecycle wiring to record stage evidence, (c) removal of hardcoded strategy names from SQL, and (d) fix of the hardcoded-TRUE trade_features.

2. **`research/svos/payload_builder.py`** — `_run_backtest_session_liquidity()` hardcodes `scripts/backtest_session_liquidity.py` as the backtest executor. A generic backtest dispatch must replace this for the platform to serve non-ST-A2 strategies.

3. **`research/svos/engine.py`** — At 1,918 lines it violates the single-responsibility principle. It is simultaneously: an intake processor, an audit runner, an enhancement driver, a replay validator, a backtest validator, a robustness aggregator, a virtual demo validator, a production approval gate, a lifecycle governance coordinator, and a report writer. The architecture review (H-01) identifies this as requiring a split into per-stage handlers and a thin orchestrator.

4. **`svos/registry/service.py` → `SVOSPlatform`** — Currently wired to JSONL. Must be replaced with `PostgresControlPlane` and `PostgresEvidenceRepository` as the PostgreSQL cutover target. This is a wiring change, not a redesign, but it requires the PostgreSQL integration exercise to pass first.

### 6.5 Strategy-Agnostic Gaps

The following modules contain ST-A2-specific hardcoding that prevents the platform from serving a new strategy:

| Module | Hardcoding | Required change |
|---|---|---|
| `pipeline/pipeline_03_replay_engine.py` | `run_id` prefix `"ST-A-"`; import `generate_signal_A` from `session_smc.confirmation_entry` | Signal dispatch abstraction; configurable run_id prefix |
| `pipeline/pipeline_04_write_db.py` | SQL strings `'ST-A2'`, `'1.0'`, description; all `trade_features` hardcoded TRUE | Strategy identity from config/CLI; feature flags from Signal object |
| `pipeline/run_phase0.py` | Banner `"ST-A2 Sweep Reversal"`; no `--strategy` flag | `--strategy` CLI arg; banner from catalog |
| `pipeline/__init__.py` | Comment `"# pipeline — Phase-0 backtest pipeline for ST-A2"` | Update comment |
| `research/svos/payload_builder.py` | `_run_backtest_session_liquidity()` hardcodes `scripts/backtest_session_liquidity.py` | Generic backtest script registry keyed by strategy ID |
| `scripts/run_strategy_demo.py`, `scripts/run_d2_e3_demo.py` | Strategy-specific demo runners | Superseded by `run_current_strategy_svos.py` when catalog-aware |

The SVOS core (`svos/lifecycle/`, `svos/governance/`, `svos/registry/`, `svos/orchestration/`) is fully strategy-agnostic. The `strategies/adapters/` layer is strategy-agnostic by design. The `research/robustness.py` module is strategy-agnostic. The remaining hardcoding is isolated to the pipeline and payload builder modules.

---

## 7. Documentation Synchronization

| Document | Claimed Status | Actual Accuracy | Key Discrepancies |
|---|---|---|---|
| `docs/svos/STRATEGY_ENGINEERING_PLATFORM_IMPLEMENTATION_PLAN.md` | Authoritative (Level 1) | HIGH — accurately describes scope, ceiling, delivery sequence, and constraints | None found; this is the ground-truth implementation ceiling |
| `docs/svos/SYSTEM_ARCHITECTURE.md` | Authoritative (Level 2) | MEDIUM-HIGH — target architecture accurately described; implementation status annotations are optimistic | Claims "SVOS transitional v1.7" but does not state that PostgreSQL is not yet wired to production code; 17-stage lifecycle not matched in code (11 stages) |
| `docs/svos/CORE_ARCHITECTURE.md` | Authoritative (Level 3) | HIGH — storage description (JSONL) matches current implementation; PostgreSQL as target is acknowledged as transitional | `data/svos/` described as the storage location but directory does not exist on disk — a fact not noted in the document |
| `docs/svos/STABILIZATION_STATUS.md` | Current operational status | HIGH — accurately flags what is implemented vs pending; PostgreSQL exercise correctly marked PENDING | Accurate as of 2026-06-29; no significant drift found |
| `docs/svos/ADR-0001-STABILIZATION-FOUNDATION.md` | Authoritative — Accepted (Level 4) | HIGH — all 8 decisions match code behavior | Consistent with all other Level 1–3 documents |
| `CLAUDE.md` | Instruction (no DOC_AUTHORITY level) | MEDIUM — lifecycle stage list is stale (9 stages vs 11 in code); Phase 6 described as SVOS when it should be Governance | `INTAKE` and `REVALIDATION` missing from §3 stage list; "Phase 6 = SVOS" is outdated per SYSTEM_ARCHITECTURE.md five-subsystem model |
| `pipeline/README.md` | Authoritative (self-claimed) | MEDIUM — accurately describes the pipeline purpose but lists `signals_audit.parquet` as a Stage 2 output that is never actually written | `signals_audit.parquet` gap; broker named "VT Markets Standard" in comments but CLAUDE.md specifies Vantage (Vantage is the correct name for the standard account broker) |
| `db/README.md` | Not audited separately | Not assessed | See db/ findings in §5 |
| `docs/svos/DOC_AUTHORITY.md` | Authoritative (Level 0) | HIGH — correctly establishes hierarchy; canonical lifecycle vocabulary table matches code | No significant drift |

---

## 8. Roadmap Progress

| Milestone | Category | Status | Evidence | Blocker |
|---|---|---|---|---|
| DOC_AUTHORITY.md + documentation hierarchy | Documentation | COMPLETE | `docs/svos/DOC_AUTHORITY.md` exists; 8-level hierarchy enforced | None |
| ADR-0001 governance decisions recorded | Governance | COMPLETE | `docs/svos/ADR-0001-STABILIZATION-FOUNDATION.md` exists | None |
| Lifecycle authority (`svos/lifecycle/manager.py`) | Governance | COMPLETE | 11 stages, full transition table, loop-backs correct | None |
| Governance bypass closure | Governance | COMPLETE | `DirectCatalogMutationError`; architecture test enforces no bypass allow-list | None |
| Broker safety (no current/approved strategy) | Safety | COMPLETE | Catalog: `current_strategy: null`, all `approved: false` | None |
| Lifecycle bypass closure (YAML write blocked) | Governance | COMPLETE | All 3 write methods in `core/strategy_registry.py` raise `DirectCatalogMutationError` | None |
| Operator API security (baseline) | Security | COMPLETE | Bearer token, roles, CORS restricted per STABILIZATION_STATUS.md | None |
| Alembic baseline migration (001/002/003) | Persistence | COMPLETE | 3 revisions exist; offline SQL compile passes in CI | None |
| Control-plane schema (v3 tables) | Persistence | COMPLETE | 39 ORM tables across 11 schemas; `db/models.py` | None |
| Transactional repository | Persistence | COMPLETE | `db/control_plane.py` implements decision+transition+outbox atomically | None |
| Immutable SHA-256 artifact store | Persistence | COMPLETE | `svos/adapters/artifacts.py`; atomic write via `os.replace()` | None |
| Legacy import (idempotent YAML → PG) | Persistence | COMPLETE (baseline) | `db/legacy_import.py` exists; no active callers | No callers |
| YAML cutover (active lifecycle does not write YAML) | Persistence | COMPLETE (baseline) | `DirectCatalogMutationError` + architecture test | None |
| CI/CD pipeline | Operations | COMPLETE (baseline) | `.github/workflows/ci.yml`; pytest + mypy + ruff + offline Alembic | Coverage threshold not enforced |
| Backup/restore tooling | Operations | PARTIAL | `scripts/control_plane_backup.py` exists; restore drill PENDING | Restore drill not run |
| PostgreSQL integration exercise | Persistence | PENDING (BLOCKER) | `test_postgres_integration.py` exists but gated by `SVOS_TEST_DATABASE_URL` | Requires disposable test DB |
| `data/svos/` initialisation | Persistence | PENDING | Directory does not exist; no bootstrap command | Blocked by PG cutover decision |
| Full OIDC/four-eyes approval | Security | PENDING | Not built | Required before broker-facing approval |
| RPO/RTO declaration + restore drill | Operations | PENDING | Backup exists; drill not run | None |
| Strategy-agnostic pipeline | Architecture | PENDING | `pipeline/` hardcoded to ST-A2 | Requires ST-A2 hardcoding removal |
| PostgreSQL production cutover (wiring `SVOSPlatform` to PG) | Persistence | PENDING | `db/control_plane.py` built but not wired | Blocked by PG integration exercise |
| Generic research engine (non-ST-A2 strategy) | Research | PENDING | `payload_builder.py` hardcoded to ST-A2 backtest | Requires ST-A2 hardcoding removal |
| Strategy Audit engine (10-validator spec) | Research | PARTIAL | Heuristic audit exists; canonical 10-validator not implemented | Phase 4 |
| Historical Replay engine (self-contained) | Research | PARTIAL | Replay executor in `simulator/`; validator in `research/validation/` | Split architecture |
| Backtest engine (self-contained) | Research | PARTIAL | Executor in `scripts/`; validator in `research/validation/` | Split architecture; ST-A2-specific |
| Robustness engine | Research | COMPLETE | 4 functions in `research/robustness.py`; strategy-agnostic | None |
| Virtual Demo (offline, no broker) | Research | PARTIAL | Governance check exists; execution in `execution_validation/` | Tick engine not in `research/` |
| Report generation system | Reporting | COMPLETE (structure) | `svos/reports/stage_package.py` (766 lines); JSON schema defined | Schema not enforced at runtime |
| Test coverage >= 80% | Quality | PENDING | Current: ~45-55% estimated (1,185 tests but major modules untested) | Pipeline stages, svos/ services, telegram untested |
| Dashboard generic (non-ST-A2) | Operations | PARTIAL | Dashboard reads `reports/current_strategy_svos/`; ST-A2-specific paths | Phase B work |

**Overall Roadmap Completion: 45%**

---

## 9. Code Quality Assessment

### 9.1 Technical Debt Findings

**ST-A2 hardcoding (4 pipeline files):** The `pipeline/` package cannot run a new strategy. Hardcoded in: `pipeline_03_replay_engine.py` (signal function import, run_id prefix), `pipeline_04_write_db.py` (SQL strategy strings, all trade_features=TRUE), `run_phase0.py` (banner, no `--strategy` flag), `__init__.py` (comment). The hardcoding in `research/svos/payload_builder.py` (backtest script path) is a fifth location.

**Duplicate `_PIP` table:** The pip-size lookup table is duplicated across 4 strategy adapters: `london_breakout_adapter.py`, `ny_momentum_adapter.py`, `adaptive_smc_adapter.py`, `vwap_adapter.py`. Should be centralised in `core/` or `strategies/adapters/`.

**`monitoring/metrics.py` misnamed:** Contains `TradeJournal` class, not metrics. This creates confusion when reading the module structure.

**`execution_validation/tests/` placeholder files:** Six test files with `__test__ = False` at module level. pytest does not collect them. They are empty shells for deferred test authorship. They give a false impression of test coverage for a critical Phase 5 component.

**`signals_audit.parquet` promised but not produced:** `pipeline/pipeline_02_build_features.py` docstring and README both list this as an output. `process_symbol()` never writes it. Downstream code expecting this file will silently find nothing.

**`trade_features` flags all hardcoded TRUE:** `research.trade_features` rows in the PostgreSQL database are inserted with `bos_present=TRUE, choch_present=TRUE, fvg_present=TRUE, liquidity_sweep_present=TRUE` unconditionally for every trade regardless of whether the signal actually contained those features. Any query against trade_features for feature analysis will return meaningless data.

**SHA-1 vs SHA-256 inconsistency:** `svos/shared/support.py` uses SHA-1 for `stable_manifest_hash()` and `file_sha1()`. `svos/adapters/artifacts.py` uses SHA-256 for content-addressed artifact storage. No unified hash strategy across the shared layer.

**`GateDecision` and `ApprovalRecord` not exported from `shared/__init__.py`:** These two models are in `shared/models.py` but not re-exported by `shared/__init__.py`. Any code trying `from svos.shared import GateDecision` will fail with an `ImportError`.

**Dead code in `session_smc/`:** Contains an embedded repository at `session_smc/session-smc-trading-bot-replay/` and a deployment runbook at `session_smc/asian_session_deployment_runbook_v2/`. These are legacy artifacts that duplicate runtime code and inflate the package tree. Per the architecture review (A-04), these should be moved to archive or removed.

**`research.db` and `research_sweep.db`:** Two large legacy SQLite databases (10.3 MB and 5.3 MB respectively) are checked into the repository. These appear to be research artifacts from prior ST-A2 trials. They are not referenced by any active governance code and are not part of the target architecture.

### 9.2 Test Coverage Gaps

**Completely untested modules:**
- `svos/api/service.py` — SVOS Operational API (read-only facade, zero test coverage)
- `svos/deployment/service.py` — deployment service
- `svos/monitoring/service.py` — SVOS monitoring service
- `svos/notifications/` — notification dispatch
- `pipeline/pipeline_02_build_features.py` — feature computation stage
- `pipeline/pipeline_03_replay_engine.py` — replay engine
- `pipeline/pipeline_04_write_db.py` — database write stage
- `pipeline/run_phase0.py` — Phase-0 orchestrator
- `execution/mt5_connector.py`, `execution/mt5_executor.py` — MT5 connectors
- `execution/vantage_demo_executor.py` — Vantage demo executor
- `monitoring/telegram.py` — Telegram notifier (no direct unit tests; monkeypatched in one integration test)
- `db/evidence_repository.py` — partially covered via side effects only
- `db/runtime.py` — untested
- `virtual_broker/fill_engine.py`, `virtual_broker/position_manager.py`, `virtual_broker/broker.py` — no dedicated unit tests

**Execution validation/tests is a misleading directory:** The six files in `execution_validation/tests/` all have `__test__ = False` — they contain zero `def test_` functions and are never collected by pytest. The execution validation logic is exercised via top-level integration tests but not at unit level.

**Lifecycle state machine not exhaustively covered:** The tests for `svos/lifecycle/manager.py` check illegal transition skips and the failure loop, but do not exhaustively cover all 11 stages × all valid/invalid transitions.

**No property-based testing:** No Hypothesis-based tests exist anywhere. Arithmetic edge cases in position sizing, lot calculation, and ATR computation are covered by hand-crafted parametrics only.

**Estimated coverage:** Given the untested pipeline stages, svos/ sub-services, and execution modules, overall coverage is estimated at 45–55%. The session_liquidity and adaptive_engine suites are thorough; governance/persistence coverage is thinner than module count suggests.

### 9.3 CI/CD Status

**What exists:** `.github/workflows/ci.yml` runs on every push and PR:
- `pytest -q` — full test suite
- `mypy` type-check on governance-critical modules
- `ruff check` on canonical governance and data modules
- Offline Alembic migration SQL compile (`alembic upgrade head --sql`)
- Secret file rejection check
- Whitespace integrity check

**What is missing:**
- No coverage threshold enforcement (no `--cov` with `--cov-fail-under`)
- No dependency audit (no `pip-audit` or similar)
- No integration test run against a real PostgreSQL instance (the `test_postgres_integration.py` test is skipped in CI because `SVOS_TEST_DATABASE_URL` is not set)
- No security scanning (no Bandit, Semgrep, or equivalent)
- No container build/push step (Docker infrastructure exists: `Dockerfile` and `docker-compose.yml` but not in CI)

### 9.4 Dependency Risk

**Runtime dependencies are pinned:** `requirements.lock` (155,752 bytes) and `requirements-dev.lock` (178,805 bytes) are locked files with pinned versions. `requirements.in` is the source of truth. This satisfies the reproducibility baseline.

**Key runtime dependencies:**
- `metaapi-cloud-sdk>=29` — MetaAPI broker connection; version range-specified in `.in` (not pinned to an exact version in `.in`; the lock file pins the resolved version)
- `aiohttp>=3.9` — async HTTP; similarly range in `.in`
- `python-dotenv>=1.0` — environment loading

**Flask is NOT in `requirements.in` or `requirements.lock`:** The dashboard requires Flask, Flask-CORS, and PyYAML, which are installed separately via `make dashboard-install`. This means a fresh `pip install -r requirements.txt` does not produce a working dashboard. This is a deployment risk.

**`research.db` and `research_sweep.db` in repository:** Large binary files (15.6 MB total) are committed to git. This is not a security risk but a repository hygiene issue.

---

## 10. Live Project Timeline

The following timeline is reconstructed from git history (10 commits shown), code maturity levels, and doc timestamps.

| Phase | What Was Built | Approximate Period | Status |
|---|---|---|---|
| Foundation — initial strategy + data | `session_smc/` SMC signal modules (liquidity detector, structure detector, swing detector, session builder, entry engine), basic `data/forex_data.py`, initial `bot.py`, `Dockerfile` | Before Jun 19, 2026 | Complete (legacy) |
| Adaptive engine + core infrastructure | `adaptive/` shadow engine (all 14 modules), `core/` base classes (portfolio manager, signal router, registry, circuit breaker), `execution/` (MetaAPI client, order manager, risk manager, trade journal), `monitoring/` utilities | Before Jun 20, 2026 | Complete (legacy) |
| ST-A2 research pipeline | `pipeline/` (feature build → bar replay → DB write), `src/` research features, `research/robustness.py`, `research/svos/engine.py` initial version, DuckDB analytics, strategy validation modules, `scripts/backtest_*.py` | Jun 19–25, 2026 | Complete (ST-A2 specific) |
| SVOS architecture and lifecycle | `svos/` package full build (lifecycle, governance, registry, orchestration, reports), `db/models.py` ORM, initial Alembic migrations, `research/svos/engine.py` integration with governance, `strategies/adapters/` layer | Jun 25–27, 2026 (commits: d5f4a77, 7bc30c5, 3e567ce) | Complete (SVOS spine) |
| Industrial database architecture | `db/control_plane.py`, `db/evidence_repository.py`, migrations 002 and 003 (v3 control-plane schema with 7 new schemas, transactional repo, hardening), ORM D-03 fixes (3 missing tables added), `db/legacy_import.py`, `db/projection.py` | Jun 27–28, 2026 (commit: 496990c) | Complete (v3 schema) |
| Governance hardening + stabilisation | `svos/governance/service.py` GovernanceGateError + full policy enforcement, `DirectCatalogMutationError` bypass closure, architecture tests, ADR-0001, STABILIZATION_STATUS.md, `svos/api/service.py`, dashboard auth hardening | Jun 28, 2026 (commit: efb46a3) | Complete (stabilisation baseline) |
| Documentation governance | Archived 16+ superseded/legacy docs, created `DOC_AUTHORITY.md`, `GLOSSARY.md`, pipeline/db/strategies/svos-api READMEs, lifecycle Mermaid diagram, `STRATEGY_ENGINEERING_PLATFORM_IMPLEMENTATION_PLAN.md` v3 | Jun 29, 2026 (commit: cb761b2) | Complete |
| PostgreSQL production wiring | Not started | Future | PENDING |
| Strategy-agnostic pipeline | Not started | Future | PENDING |
| RESEARCH CAPABLE milestone | Not started | Future | PENDING |

---

## 11. Critical Path to Completion

### P0 — Must complete before any new development resumes

These tasks unblock the feature freeze. Nothing else should start until all P0 items are done.

**[P0-1] Run PostgreSQL integration exercise against a real test database**
- What: Provision a test PostgreSQL instance; set `SVOS_TEST_DATABASE_URL`; run `pytest tests/database/test_postgres_integration.py`; confirm all tests pass. Verify migration, concurrency, atomicity, and optimistic locking.
- Why: Closes the single remaining gate for the feature freeze (per STABILIZATION_STATUS.md: "Feature work remains frozen until the pending Phase 2 operational exercises pass").
- Effort: Small (2–4 hours)
- Dependency: PostgreSQL 16 available at localhost:5432 with correct credentials, or a Docker container via `docker-compose.yml`
- Verification: `pytest tests/database/test_postgres_integration.py` passes with zero skips; STABILIZATION_STATUS.md updated to mark PostgreSQL exercise COMPLETE

**[P0-2] Run backup/restore drill and declare RPO/RTO**
- What: Run `scripts/control_plane_backup.py` on a seeded test database; perform a restore; verify restored state matches original. Declare RPO (max data loss) and RTO (max recovery time) in writing.
- Why: STABILIZATION_STATUS.md explicitly lists this as a pending Phase 2 operational exercise.
- Effort: Small (2–4 hours)
- Dependency: P0-1 complete (need a live PostgreSQL instance with data)
- Verification: Restore drill documented; RPO/RTO declaration added to STABILIZATION_STATUS.md

**[P0-3] Initialise `data/svos/` and run `SVOSPlatform.bootstrap()` against the live catalog**
- What: Ensure the `data/svos/` directory tree is created; run `SVOSPlatform.bootstrap()` to initialise all 6 catalog strategies as JSONL records; verify state.json and versions.jsonl are written for each strategy.
- Why: The live governance stack has never written any data. No integration test can be considered passing until real writes have occurred.
- Effort: Small (1–2 hours)
- Dependency: P0-1 complete (to confirm the JSONL path works as expected; JSONL init does not require PG but PG exercise should come first)
- Verification: `data/svos/registry/<strategy>/state.json` exists for all 6 strategies; all show stage `DRAFT` or `INTAKE`

**[P0-4] Fix `GateDecision` and `ApprovalRecord` not exported from `svos/shared/__init__.py`**
- What: Add `GateDecision` and `ApprovalRecord` to the re-export list in `svos/shared/__init__.py`.
- Why: Any code using `from svos.shared import GateDecision` will currently fail with `ImportError`. This is a silent breakage in the public API surface.
- Effort: Trivial (5 minutes)
- Dependency: None
- Verification: `from svos.shared import GateDecision, ApprovalRecord` succeeds; existing tests still pass

### P1 — Required for MVP (running one new strategy end-to-end)

**[P1-1] Wire `SVOSPlatform` to PostgreSQL (replace JSONL backend)**
- What: Modify `svos/orchestration/service.py` to accept `PostgresControlPlane` and `PostgresEvidenceRepository` (from `db/`) as injectable backends, replacing the default `StrategyRegistryService` and `GovernanceService` (JSONL). Update the default constructor to use PG when `DATABASE_URL` is set.
- Why: PostgreSQL is the target authoritative store. The receiving end is fully built and tested. The wiring step is the last gap.
- Effort: Medium (1–2 days, including integration testing)
- Dependency: P0-1 (PG exercise must pass first)
- Verification: `SVOSRunner` records evidence to PostgreSQL; `tests/database/test_postgres_integration.py` covers the new path; JSONL files are no longer written by `SVOSPlatform`

**[P1-2] Remove ST-A2 hardcoding from `pipeline/` package**
- What: Add `--strategy` CLI arg to `pipeline/run_phase0.py`. Replace hardcoded `'ST-A2'` SQL strings in `pipeline_04_write_db.py` with values derived from the catalog. Replace `generate_signal_A` import with a signal dispatch registry keyed by strategy ID. Fix `trade_features` flags to be derived from `Signal` object fields rather than hardcoded TRUE.
- Why: The pipeline cannot serve any strategy other than ST-A2. This is the main barrier to the platform goal.
- Effort: Large (3–5 days)
- Dependency: `strategies/adapters/` must expose a dispatch registry; `core/strategy_registry.py` must provide strategy ID lookup
- Verification: `python -m pipeline.run_phase0 --strategy LONDON-BREAKOUT` runs without error (even if no data exists for that strategy); unit tests for pipeline_03 and pipeline_04 pass with a non-ST-A2 strategy name

**[P1-3] Fix `signals_audit.parquet` gap in `pipeline/pipeline_02_build_features.py`**
- What: Either implement the signals_audit.parquet output (signal annotations per bar) in `process_symbol()`, or remove it from the module docstring and README.
- Why: Code that expects this file will silently find nothing. Documentation should not describe outputs that do not exist.
- Effort: Small (hours)
- Dependency: None
- Verification: Either `data/features/{SYMBOL}/signals_audit.parquet` is written, or the docstring and README no longer mention it

**[P1-4] Replace `payload_builder._run_backtest_session_liquidity()` with a generic dispatch**
- What: Create a `BACKTEST_SCRIPTS` registry in `config/strategy.yaml` (or equivalent) mapping strategy ID to its backtest script. Replace the hardcoded path in `payload_builder.py` with a registry lookup.
- Why: `payload_builder.py` is the last ST-A2-specific hardcoding in the research engine. Without this, `SVOSRunner` cannot build a payload for any other strategy.
- Effort: Medium (1–2 days)
- Dependency: P1-2 (strategy dispatch registry pattern established in pipeline first)
- Verification: `build_svos_payload_bundle(strategy="LONDON-BREAKOUT", ...)` calls the correct script for that strategy

**[P1-5] Register a second test strategy in the catalog and run it end-to-end**
- What: Add a minimal second strategy (e.g., London Breakout adapter) to `config/strategy_catalog.yaml`. Run it through the full SVOS pipeline via `scripts/run_svos_pipeline.py`. Confirm a PASS or FAIL verdict with a complete manifest.
- Why: This is the literal definition of "RESEARCH CAPABLE." If this cannot be done, the platform goal has not been achieved.
- Effort: Large (depends on P1-1 through P1-4 being complete; then 1 week for data + pipeline work)
- Dependency: P1-1, P1-2, P1-3, P1-4 complete; market data available for the strategy's pairs
- Verification: Full SVOS run produces `reports/svos/<strategy>/` with JSON + Markdown; no `BLOCKED` manifest warnings; verdict is `PASS` or `FAIL` (not `ERROR`)

**[P1-6] Enforce coverage threshold in CI**
- What: Add `--cov=svos --cov=pipeline --cov=research --cov-fail-under=70` to the pytest step in `.github/workflows/ci.yml`.
- Why: Currently no minimum coverage is enforced. The pipeline stages are untested. A coverage gate will catch regressions and drive test authorship.
- Effort: Small (hours; primarily writing the missing tests to reach the threshold)
- Dependency: P1-2 (pipeline must be testable before tests can be written)
- Verification: CI passes with 70%+ coverage across the three most critical packages

### P2 — Required before production

**[P2-1] Implement OIDC/four-eyes approval workflow**
- What: Replace the current single-bearer-token API auth with an OIDC provider. Implement the four-eyes approval requirement for `LIVE_DEMO` and `PRODUCTION` entry gates.
- Why: Required per ADR-0001 and STABILIZATION_STATUS.md before any broker-facing approval capability.
- Effort: Large (week+)
- Dependency: P1-1 (PG must be the authoritative store before approval records are trustworthy)

**[P2-2] Implement strategy registration CLI/API**
- What: Build a CLI command (`python -m svos register --name "..." --spec-file strategy.md`) that creates a catalog entry, initialises SVOS state, and accepts the strategy through Intake.
- Why: Currently the only way to add a strategy is to manually edit YAML. A generic platform requires a proper intake flow.
- Effort: Medium (2–3 days)

**[P2-3] Implement the simple Vantage execution bot**
- What: A single-purpose bot that reads only an Approved Strategy Package from the platform and executes via MetaAPI. No research, no backtest, no approval logic.
- Why: The bot is a stated deliverable (Phase E of implementation plan) and the downstream target of the Virtual Demo.
- Effort: Large (week+; depends on full Phase D completion first)

**[P2-4] Build tick-resolution Virtual Demo executor**
- What: Move tick-by-tick simulation into `research/` (or create a proper virtual-demo sub-package) so the Virtual Demo stage is self-contained. Wire the output to `SVOSPlatform.record_report_evidence()`.
- Why: Current virtual demo governance check is a stub that calls `execution_validation.replay_bridge` externally and silently fails to empty if candles are unavailable.
- Effort: Large (week+)

**[P2-5] Centralise `_PIP` table and fix `GateDecision`/`ApprovalRecord` export**
- What: Extract the pip-size lookup table from 4 adapter files into `core/` or `strategies/adapters/__init__.py`. (P0-4 covers the shared model export.)
- Why: Duplicated constants are a maintenance risk.
- Effort: Small (hours)

### P3 — Future enhancements

- S3 artifact storage (replace local filesystem content-addressing)
- Multi-strategy dashboard (generic report browsing, not ST-A2-specific path scanning)
- Property-based tests (Hypothesis) for position sizing and ATR arithmetic
- Strategy comparison dashboard (compare two strategies' evidence packages)
- Dependent evidence invalidation graph (when spec changes, auto-invalidate downstream evidence)
- Coverage for `execution_validation/tests/` (convert `__test__ = False` stubs to real tests)
- MT5/Vantage executor unit tests
- Telegram alerter unit tests with mock HTTP
- News filter live feed integration (`adaptive/filters/news_filter.py`)
- Dedicated unit tests for `svos/api/service.py`, `svos/deployment/service.py`, `svos/monitoring/service.py`

---

## 12. Final Project Readiness Scorecard

| Dimension | Score | Evidence | Gap |
|---|---|---|---|
| Documentation | 78/100 | 7 authoritative governing docs; DOC_AUTHORITY.md hierarchy; 128 active docs; archive governance complete; GLOSSARY.md and READMEs written | CLAUDE.md stage list stale (9 vs 11); `pipeline/README.md` has `signals_audit.parquet` error; `data/svos/` existence not flagged in docs |
| Architecture | 62/100 | 5-subsystem target documented; CORE_ARCHITECTURE.md Level 3; lifecycle authority pattern enforced; ADR-0001 accepted | God module `research/svos/engine.py` (1,918 lines); competing validation architectures (5 overlapping areas); 17-stage vs 11-stage lifecycle mismatch; EVF/RGM/SMO only architectural targets |
| Database Layer | 55/100 | 39 ORM tables across 11 schemas; 3 Alembic revisions; transactional control plane; SHA-256 artifacts | PostgreSQL not wired to production code; `data/svos/` does not exist; dual storage backends (JSONL + PG) unresolved; legacy SQLite DBs in repo |
| Lifecycle Governance | 72/100 | 11 stages; full transition table; `DirectCatalogMutationError` bypass closure; architecture test enforces it; `GovernanceService` enforces PASS+hash+version_id | `GateDecision`/`ApprovalRecord` not exported from `shared/__init__.py`; numeric thresholds (PF, n) not enforced in governance gate; OIDC pending |
| Strategy Audit Engine | 45/100 | `StrategyAuditEngine` heuristic audit exists; `StrategyValidationAuditAdapter` for 10-validator path exists; full strategy-agnostic | 10-validator canonical spec (STAGE1_AUDIT_SPEC.md) not implemented as named pluggable array; two audit paths not unified |
| Historical Replay | 50/100 | Bar-by-bar event-driven replay in `simulator/historical_replay.py`; no-lookahead boundary respected; replay validator in `research/validation/engine.py` | Executor outside `research/`; pipeline hardcoded to ST-A2 (`generate_signal_A`); no generic signal dispatch |
| Backtest Engine | 45/100 | `scripts/backtest_session_liquidity.py` implements full fee-inclusive backtest; PF and trade-count gates enforced | Subprocess-based; hardcoded to ST-A2 script; fee enforcement is a flag check not active calculation; no generic dispatch |
| Robustness Engine | 88/100 | 4 fully implemented strategy-agnostic pure functions; walk-forward, Monte Carlo, parameter sensitivity, regime analysis; tested | Not wired to PostgreSQL `robustness` schema; no SVOS evidence recording for robustness results directly |
| Virtual Demo | 35/100 | Governance check in `SVOSRunner._validate_virtual_demo()`; execution bridge to `execution_validation/replay_bridge`; drift tolerance check | No tick-level simulator in `research/`; silently empty if candles unavailable; `execution_validation/tests/` all `__test__ = False` |
| Reporting | 70/100 | `write_stage_report_package()` 766 lines fully implemented; JSON schema `stage_report.schema.json` defined; 11 report types per run | JSON schema not enforced at runtime; reports depend on ST-A2-specific payload builder; no generic evidence package builder for new strategies |
| Testing | 58/100 | 1,185 test functions; 92 files; strong session_liquidity (267) and adaptive_engine (98) suites; architecture enforcement AST tests; CI enforces mypy + ruff | Pipeline stages untested; svos/api/deployment/monitoring untested; execution_validation/tests `__test__=False`; no coverage threshold; no PG integration in CI |
| Deployment/CI | 52/100 | `.github/workflows/ci.yml` exists; pytest + mypy + ruff + offline Alembic; `Dockerfile` + `docker-compose.yml` present | No coverage threshold; no security scan; no PG integration in CI; Flask dependencies not in requirements.lock; no container build step |
| **Overall** | **59/100** | | |

### Readiness Gates

| Gate | Status | What Is Missing |
|---|---|---|
| Research Ready (can audit a new strategy) | NO | `data/svos/` never initialised; pipeline hardcoded to ST-A2; PostgreSQL not wired; `--strategy` flag missing |
| Strategy Development Ready (can run full SVOS pipeline for a non-ST-A2 strategy) | NO | All P0 and P1 tasks outstanding; no generic signal dispatch; no generic backtest script registry |
| Historical Replay Ready | PARTIAL | Replay executor exists and is complete; not integrated with SVOS lifecycle; ST-A2-specific signal function hardcoded |
| Backtest Ready | PARTIAL | Backtest executor exists; hardcoded to ST-A2 script; not lifecycle-wired |
| Offline Virtual Demo Ready | NO | Tick executor not in `research/`; governance check partial; `execution_validation/tests/` all placeholder |
| Production Ready | NO | OIDC not built; Production Approval is record-only by design; live bot not built; Phase 6 explicitly out of scope |

### The Single Most Important Answer

**"If development resumes tomorrow, what are the exact next tasks, in what order, and why?"**

1. **Provision a PostgreSQL 16 instance and run `pytest tests/database/test_postgres_integration.py` with `SVOS_TEST_DATABASE_URL` set.** This single action lifts the feature freeze that blocks all other work. The test file exists, the schema exists, the migrations exist. This is a configuration task, not a coding task. (P0-1)

2. **Run `python -m svos bootstrap` (or equivalent) to initialise `data/svos/` and write the first JSONL records.** The live governance stack has never been exercised against real data. Without this, no integration scenario is possible. If no bootstrap command exists, add one to `scripts/` that calls `SVOSPlatform.bootstrap()`. (P0-3)

3. **Fix the `GateDecision`/`ApprovalRecord` export gap in `svos/shared/__init__.py`.** Five-minute fix that prevents a silent `ImportError` in the governance path. (P0-4)

4. **Wire `SVOSPlatform` to `PostgresControlPlane` and `PostgresEvidenceRepository`.** Replace the JSONL backend with the PostgreSQL backend that is already built and tested. This is the cutover step that makes the database layer authoritative. (P1-1)

5. **Add `--strategy` flag to `pipeline/run_phase0.py` and remove `'ST-A2'` hardcoding from `pipeline_04_write_db.py`.** These two changes in two files make the pipeline callable for a different strategy. The signal dispatch abstraction can come later; the SQL hardcoding removal is urgent. (P1-2)

6. **Replace `payload_builder._run_backtest_session_liquidity()` with a registry lookup.** Create a `BACKTEST_SCRIPTS` mapping in `config/research_engine.yaml` (or equivalent) so that `SVOSRunner` can call the correct backtest script for any strategy ID. (P1-4)

7. **Add a second strategy (e.g., London Breakout) to `config/strategy_catalog.yaml` and run `scripts/run_svos_pipeline.py --strategy LONDON-BREAKOUT`.** This is the acid test for "RESEARCH CAPABLE." If it produces a PASS or FAIL report with a complete manifest, the platform's core value proposition is demonstrated. (P1-5)

8. **Add `--cov-fail-under=70` to the CI pytest step and write the minimum tests needed to clear that threshold.** The first missing test suite to write is `pipeline/test_run_phase0.py` — the orchestrator with a non-ST-A2 strategy. (P1-6)

9. **Archive or remove `session_smc/session-smc-trading-bot-replay/` and `session_smc/asian_session_deployment_runbook_v2/`.** These embedded legacy artifacts inflate the package tree and duplicate runtime code. Moving them to `archive/` takes minutes and clarifies the active codebase boundary.

10. **Run the backup/restore drill and write the RPO/RTO declaration** as the final gate item for Phase 2 operational exercises. (P0-2)

---

*Report generated: 2026-06-29*
*Scope: Full codebase audit — docs, code, database, tests, architecture*
*Methodology: Multi-agent parallel read of all source files, governing documents, migration scripts, test files, and CI configuration*
*Authority level: This report is informational — it does not supersede `docs/svos/DOC_AUTHORITY.md` or any Level 0–4 governing document*
