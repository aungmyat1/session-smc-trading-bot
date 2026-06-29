# Strategy Engineering Platform — Implementation Requirements

Date: 2026-06-29  
Purpose: Entry requirements for Phases A and B  
Related plan: `docs/svos/STRATEGY_ENGINEERING_PLATFORM_IMPLEMENTATION_PLAN.md`

## 1. Readiness Decision

The repository contains enough reusable development to begin the platform
foundation, but the environment is **NOT YET READY** for database migration or
large research runs.

Current readiness:

| Area | Status | Decision |
|---|---|---|
| Python/Git tooling | READY | Python 3.12.3 and Git are available |
| Container tooling | READY | Docker and Compose are available |
| PostgreSQL tooling | PARTIAL | PostgreSQL 16 client/server responds; SVOS database and credentials are not verified |
| Research storage | PARTIAL | Real datasets exist; canonical snapshots and hashes are incomplete |
| Python dependencies | READY | Locked development environment now includes Alembic, Polars, Ruff, mypy, and pytest-cov |
| Dependency reproducibility | READY | Separate fully pinned runtime and development locks exist |
| Host capacity | IN PROGRESS | VPS 2 is available for data/DB offload; its 955 MiB RAM still blocks full research runs |
| Working tree | PARTIAL | External snapshot exists; a durable intentional checkpoint is still required |
| Test baseline | READY | 1,170 tests pass in the locked environment |
| Broker safety | READY FOR CONSTRUCTION | Live execution remains disabled; broker access is not required for Phases A-B |

The approved topology is recorded in `docs/svos/DEPLOYMENT_TOPOLOGY.md`. A
resumable copy to VPS 2 is permitted, but do not delete the VPS 1 source or run
full data builds until transfer verification and the capacity gate pass.

## 2. Required Engineering Capabilities

These are work capabilities, not independent services. One engineer or agent
may hold several capabilities, but every change must receive the relevant
review.

### 2.1 Platform architecture and governance

Required knowledge:

- modular monolith boundaries and dependency inversion;
- lifecycle state machines and fail-closed policy evaluation;
- immutable strategy versioning and evidence lineage;
- optimistic concurrency and transactional workflows;
- backward-compatible migration of legacy callers.

Primary responsibilities:

- own the canonical lifecycle vocabulary and mutation authority;
- prevent direct YAML/catalog mutation;
- keep research, governance, reporting, and execution responsibilities separate;
- review every public contract or lifecycle change.

### 2.2 Database and migration engineering

Required knowledge:

- PostgreSQL 16, SQLAlchemy 2, psycopg2, and Alembic;
- normalized control-plane schemas, constraints, indexes, and transactions;
- idempotent import, optimistic locking, backup, restore, and rollback;
- JSONB usage without turning relational state into unvalidated blobs.

Primary responsibilities:

- create and test migrations;
- reconcile the existing 16 SQL tables with the 13 ORM mappings;
- import YAML/JSONL state with original hashes and non-qualifying trust;
- prove concurrent transitions cannot both succeed.

### 2.3 Quantitative research and data engineering

Required knowledge:

- chronological replay and prevention of lookahead bias;
- Forex sessions, timezones, spread, commission, slippage, and R-multiples;
- Parquet, DuckDB, PyArrow, Polars, dataset snapshots, and streaming hashes;
- backtest statistics, walk-forward analysis, Monte Carlo, parameter stability,
  and regime analysis.

Primary responsibilities:

- define reproducible dataset and run manifests;
- validate net-of-fees metrics and honest FAIL outcomes;
- ensure parameter changes create new trials;
- keep strategy algorithms independent from Vantage execution code.

### 2.4 Report and evidence engineering

Required knowledge:

- JSON Schema, deterministic Markdown rendering, and content addressing;
- stage-gate reports, evidence bindings, remediation, and version comparison;
- immutable artifacts, invalidation without deletion, and queryable report
  metadata.

Primary responsibilities:

- upgrade the existing report schema to the full strategy-neutral lifecycle;
- consolidate the two report indexes and compatibility paths;
- prove reports never mutate lifecycle state or contact a broker;
- produce the Approved Strategy Package only from qualifying real evidence.

### 2.5 Execution-safety engineering

Required knowledge:

- order, fill, position, risk, idempotency, reconnect, and recovery semantics;
- virtual clocks, latency/slippage models, and broker adapter isolation;
- credential boundaries and startup/order authorization checks.

Primary responsibilities:

- reuse the same execution contracts in Virtual Demo and the future Vantage bot;
- keep broker credentials outside research/report workers;
- maintain independent fail-closed submission guards.

### 2.6 Quality and security engineering

Required knowledge:

- pytest, property/failure-injection testing, architecture tests, and migration
  tests;
- Ruff, type checking, coverage, dependency auditing, and secret scanning;
- safe configuration, least privilege, and incident/recovery testing.

Primary responsibilities:

- preserve the 1,170-test baseline;
- add CI release gates;
- verify that missing state, evidence, DB connectivity, or authorization blocks
  rather than degrades into permissive behavior.

### Agent-skill policy

- No external agent skill is required to begin Phases A-B; the work is grounded
  in repository contracts and local tooling.
- Agents must read the governing implementation plan, this requirements file,
  `CLAUDE.md`, the architecture review, and the relevant module tests before
  editing.
- Database migrations, lifecycle changes, quantitative formulas, and execution
  safety changes require a second review pass even when one agent performs the
  implementation.
- Do not delegate authority decisions to generated code or AI recommendations.
- AI may create draft strategy specifications but cannot activate, qualify,
  approve, deploy, or enable live trading.

## 3. Required Runtime and Development Environment

### 3.1 Supported baseline

| Component | Required | Current |
|---|---|---|
| Python | 3.12.x | 3.12.3 |
| PostgreSQL | 16.x | Client/server 16.14 responds locally |
| Docker Engine | Current supported release | 29.6.0 |
| Docker Compose | v2+ | v5.1.4 |
| Git | 2.4x+ | 2.43.0 |
| Time standard | UTC | Repository convention exists |

Use a project virtual environment. Do not install or upgrade dependencies into
an uncontrolled global environment during implementation.

### 3.2 Python dependency groups

Runtime core:

- SQLAlchemy 2.x;
- psycopg2-binary 2.9.x;
- Alembic;
- Pydantic 2.x;
- PyYAML;
- python-dotenv.

Research:

- DuckDB 1.5.x;
- PyArrow;
- Polars;
- Pandas only where current reusable modules still require it.

Interfaces:

- Flask and Flask-CORS during compatibility migration;
- MetaAPI SDK only in the isolated future execution worker.

Development and quality:

- pytest and pytest-asyncio;
- pytest-cov;
- Ruff;
- mypy or Pyright, with one selected as the canonical checker;
- pip-tools for a fully pinned `requirements.lock` with hashes;
- jsonschema for report-contract tests;
- dependency and secret scanners in CI.

Currently missing from the active environment:

- Alembic;
- Polars, despite being declared in `requirements.txt`;
- pip-tools;
- Ruff;
- mypy/Pyright configuration;
- pytest-cov.

### 3.3 Capacity requirements

Current host:

- root filesystem: 38 GB total, 4.8 GB free, 88% used;
- RAM: 3.8 GB total, about 1.1 GB available;
- swap: 2 GB;
- repository data: 7.4 GB;
- research database artifacts: 437 MB;
- logs: 215 MB.

Minimum before PostgreSQL migration or full data builds:

- 15 GB free disk after cleanup;
- 8 GB RAM or a constrained test profile with verified no-OOM behavior;
- separate persistent PostgreSQL volume with backup capacity;
- no copied multi-gigabyte datasets inside test fixtures or container build
  contexts.

Recommended development/research host:

- 4 CPU cores;
- 16 GB RAM;
- 100 GB SSD/NVMe free for data, database, artifacts, and two backup generations.

Current two-node allocation:

- VPS 1 (`auto-trade-vps`): control/development and downstream Vantage demo
  execution; do not interrupt the active bot or spread collector.
- VPS 2 (`gcp-vm1`): PostgreSQL, datasets, research engines, Virtual Demo, and
  reports; no broker credentials or order submission.
- VPS 2 currently has a 30 GB root disk with about 24 GB free and 955 MiB RAM.
  It may host preparation and constrained tests, but full qualification runs
  remain blocked until an 8 GB minimum RAM profile is available or no-OOM
  behavior is demonstrated.

## 4. Database Requirements

### 4.1 Database roles

Use separate credentials:

- `svos_migrator`: schema changes only;
- `svos_app`: transactional application reads/writes;
- `svos_reader`: dashboard/report read access;
- `svos_importer`: time-limited legacy import access;
- execution worker role: package/deployment reads and execution-event writes
  only.

Research and report workers receive no broker credentials.

### 4.2 Required schemas

- `strategy`: strategies and immutable versions;
- `governance`: stage state, transitions, gate decisions, and later approvals;
- `research`: run manifests, experiments, dataset snapshots, and metrics;
- `evidence`: artifacts, reports, bindings, invalidations, and certificates;
- `operations`: deployment, execution events, incidents, and monitoring state.

Every table uses stable IDs, `TIMESTAMPTZ`, explicit constraints, created actor,
and schema/policy version where relevant.

### 4.3 Migration requirements

- Baseline the existing schema without pretending ORM/SQL parity exists.
- Add an Alembic version table and reversible migrations.
- Test upgrade from empty and current-like databases.
- Import catalog and JSONL records idempotently through an import ledger.
- Store source path, SHA-256, source timestamp, and `LEGACY_IMPORTED` trust.
- Commit decision, transition, state revision, evidence binding, and audit event
  atomically.
- PostgreSQL failure blocks mutation; YAML is not a fallback.
- Generate YAML only as a read-only compatibility projection.

### 4.4 Backup and recovery requirements

Before the database becomes authoritative:

- define development and production RPO/RTO;
- implement encrypted logical backup and restore scripts;
- test restore into a clean database;
- verify row counts, hashes, constraints, and current-stage state;
- retain the pre-migration catalog and JSONL hashes as migration evidence.

## 5. Required Data and External Resources

### 5.1 Available local resources

- normalized tick dataset manifest for EURUSD, GBPUSD, and XAUUSD;
- processed M1/M5/M15/H1/H4/D1 Parquet datasets;
- a 437 MB DuckDB feature database with candles, structure, sweeps, FVGs, and
  order blocks;
- historical Forex CSV inputs used by existing replay/backtest tools;
- E6 dataset and cost-model snapshots;
- approximately 73 MB of spread-capture logs;
- deterministic sample SVOS payloads;
- existing strategy specifications and audit artifacts.

### 5.2 Data gaps and qualification restrictions

- The normalized manifest records paths, rows, dates, and sizes but not a
  cryptographic hash for every data partition.
- The active Vantage cost profile is still a placeholder; measured costs are
  incomplete and cannot create qualifying evidence.
- Existing ST-A2 and sample reports are legacy/synthetic, not platform
  qualification evidence.
- Dataset ownership, license/usage constraints, retention, and archival rules
  need explicit records.

### 5.3 External resources required later

- Vantage/MetaAPI demo account and API credentials, isolated to the execution
  worker;
- measured Vantage spread/commission/slippage data by instrument and session;
- authoritative UTC clock/NTP and timezone database;
- S3-compatible object storage when local content-addressed storage is retired;
- OIDC identity provider when multi-user or broker-connected operation begins;
- CI runner with PostgreSQL service support.

No external broker, OIDC, or S3 resource is needed for Phases A-B.

## 6. Reusable Current Development

| Existing component | Reuse decision | Required change |
|---|---|---|
| `svos/lifecycle/manager.py` | REUSE | Make its vocabulary canonical and place all mutation behind authority |
| `svos/governance/service.py` | CONSOLIDATE | Retain policy checks; remove independent persistence/transition authority |
| `svos/registry/service.py` | ADAPT | Replace YAML/JSONL authority with repository ports and PostgreSQL |
| `svos/reports/stage_package.py` | REUSE/REFACTOR | Preserve stage packages and renderers; upgrade lifecycle/schema and remove direct file identity |
| `svos/reports/evidence_package.py` | REUSE | Bind outputs to canonical evidence and report records |
| `strategy_validation/` | REUSE/FIX | Keep modular validators; correct structural parsing and false positives |
| `research/validation/engine.py` | REUSE AS ADAPTER | Remove lifecycle promotion and emit typed evidence only |
| `src/data`, `src/features`, `src/analytics` | REUSE | Add dataset/run manifests and strategy-neutral ports |
| `src/backtest/simulator.py` | EVALUATE/PARITY | Retain after golden comparison with other backtest paths |
| `execution_simulator/` | REUSE | Make it the foundation of offline Virtual Demo through shared contracts |
| `execution_validation/` | REUSE | Bind EVF checks to versioned execution evidence |
| `execution/` MetaAPI/Vantage clients | DEFER/ISOLATE | Use later behind the approved-package bot boundary |
| `dashboard/report_service.py` | MIGRATE | Replace filesystem scanning/path IDs with canonical report queries |
| `scripts/generate_reports.py` | COMPATIBILITY ONLY | Remove ST-A2 paths and emit JSON plus deterministic Markdown |
| `db/schema_v2.sql` and ORM | BASELINE ONLY | Reconcile drift through Alembic; do not treat as final design |
| 1,170 existing tests | PRESERVE | Add architecture, migration, evidence, report, and fail-closed tests |

Do not rebuild working quantitative algorithms merely to fit a new folder
layout. Wrap them, establish parity, then retire duplicates deliberately.

## 7. Report-System Prerequisites

Before report implementation begins:

- approve one report schema version covering the full lifecycle;
- define stable report, artifact, evidence, run, strategy, and version IDs;
- define trust and validity enums;
- define deterministic JSON serialization and Markdown rendering rules;
- define content-addressed local artifact paths;
- create PostgreSQL report/evidence metadata tables;
- select one report index service;
- map current six-stage and nine-stage compatibility outputs to the new stages;
- define retention and invalidation behavior;
- ensure report workers have no broker credentials and no lifecycle mutation
  capability.

Required report acceptance fixtures:

- complete PASS pipeline;
- audit FAIL with refinement route;
- missing replay causing downstream BLOCKED reports;
- statistical FAIL with real metrics;
- invalidated prior-version evidence;
- synthetic sample pipeline;
- successful Production Approval package;
- tampered artifact/package rejection.

## 8. Configuration and Safety Requirements

Required environment variables for Phases A-B:

- `DATABASE_URL` for the application role;
- separate migration URL or credentials;
- `DB_BACKEND=postgres`;
- `LIVE_TRADING=false`;
- `DEMO_ONLY=true`;
- content-addressed artifact root;
- qualification-policy path/version;
- UTC timezone.

Rules:

- secrets live outside Git and logs;
- configuration is validated at startup;
- unknown/missing safety values fail closed;
- broker modules are not imported by research/report workers;
- dashboard binds to loopback during construction;
- no process may infer approval from an environment flag.

## 9. Preflight Gate

All items below must pass before Phase A implementation is declared started:

- [ ] Preserve the current working tree in an intentional checkpoint without
      discarding user changes.
- [ ] Copy and checksum-verify canonical research data on VPS 2, then free at
      least 15 GB on VPS 1 or provision a separate development volume.
- [ ] Create a Python 3.12 virtual environment.
- [ ] Split direct dependencies into source requirement groups.
- [ ] Generate and verify a fully pinned, hashed dependency lock.
- [ ] Install Alembic, Polars, quality tools, and all locked dependencies.
- [ ] Run all 1,170 tests from the locked environment.
- [ ] Provision a dedicated development PostgreSQL database and roles.
- [ ] Verify migration and application connections without default passwords.
- [ ] Snapshot and hash current catalog, JSONL history, and report indexes.
- [ ] Confirm `LIVE_TRADING=false`, `DEMO_ONLY=true`, loopback dashboard, and no
      broker credentials in research/report environments.
- [ ] Approve canonical lifecycle, ID, trust, report-status, and Phase-0 policy
      definitions.
- [ ] Record ST-A2 as deferred/preserved; do not delete or revalidate it.

## 10. Immediate Preparation Backlog

Execute in this order:

1. **Workspace checkpoint:** inventory and preserve the existing 15 changes.
2. **Capacity:** archive or move generated data/logs without deleting canonical
   inputs; reach the 15 GB free-space gate.
3. **Environment:** create the virtual environment, requirement groups, and
   hashed lock; install missing tools.
4. **Baseline:** run tests, schema checks, and data-manifest verification from
   the locked environment.
5. **Database:** provision roles/database, introduce Alembic baseline, and test
   backup/restore before importing state.
6. **Contracts:** approve lifecycle, IDs, trust/status enums, evidence/report
   schemas, and mutation-authority API.
7. **Safety snapshot:** prove broker execution is unavailable to all Phase A-B
   workers.

Only after these preparation items pass should implementation begin on the
mutation authority, transactional registry, and canonical report system.
