# Database Assessment

## Current status

The repository uses several persistence models:

| Store | Current role | Assessment |
|---|---|---|
| PostgreSQL `db/schema_v2.sql` | market, research, analytics, config | Useful prototype, not governed by migrations |
| SQLAlchemy `db/models.py` | partial ORM mapping | Does not mirror the SQL schema as claimed |
| `research_db/client.py` | direct psycopg2 writes | Duplicates ORM responsibility and degrades silently |
| DuckDB + Parquet | feature database and analytics | Appropriate for local reproducible research |
| SQLite trade journal | runtime signal/trade journal | Suitable locally; separate schema and identity model |
| SQLite execution log | virtual execution evidence | Missing declared foreign keys and migrations |
| YAML catalog | strategy/lifecycle authority | Unsafe as a concurrent system of record |
| JSON/JSONL/Markdown | reports, control state, evidence | Good artifact formats; unsafe as transactional metadata |

## Critical and high findings

| ID | Severity | Finding | Evidence/impact |
|---|---|---|---|
| D-01 | Critical | Control state is file-backed without atomic write or lock | Concurrent dashboard/runners can lose or corrupt state |
| D-02 | High | No migration framework or schema version table | Deployments cannot safely evolve or roll back |
| D-03 | High | SQL and ORM drift | SQL has candles, optimization_results, system_config; ORM omits them |
| D-04 | High | No canonical identifiers across stores | Strategy/run/trade/evidence joins rely on names and strings |
| D-05 | High | Split write stacks | SQLAlchemy, psycopg2, SQLite, YAML, and JSONL have different semantics |
| D-06 | High | Governance records are not transactional with transitions | Decision append, state write, and catalog write can partially commit |
| D-07 | Medium | PostgreSQL timestamps are mostly timezone-naive | Cross-market/session evidence can be ambiguous |
| D-08 | Medium | Financial precision is inconsistent | SQLite REAL and Python float coexist with PostgreSQL NUMERIC |
| D-09 | Medium | Retention, partitioning, backup, restore, and RPO/RTO are unspecified | Long-term scale and recovery are unproven |
| D-10 | Medium | Execution SQLite declares relationship columns without FK constraints | Orphan fills/positions are possible |

`db/models.py` says it mirrors `schema_v2.sql` exactly, but the SQL defines 16
tables while the ORM defines 13. There is also a likely responsibility error in
the direct client: daily equity writes target `analytics.daily_equity` while
the declared table is `research.daily_equity`.

## Recommended logical schema

### Control plane — PostgreSQL

- `strategy.strategy`: stable UUID, name, owner, status
- `strategy.version`: immutable spec hash, semantic version, parent version,
  source commit, created by/at
- `governance.stage_state`: current version and stage with optimistic lock
- `governance.gate_decision`: policy version, outcome, blockers, actor
- `governance.approval`: approver identity, role, scope, expiry/revocation
- `evidence.artifact`: URI, SHA-256, media type, size, schema version
- `evidence.binding`: strategy version, run, stage, artifact, status
- `research.run`: code commit, environment lock hash, dataset snapshot, seed,
  parameters, start/end, status
- `research.metric`: typed metric name/value/unit/window
- `operations.deployment` and `operations.incident`
- transactional outbox for lifecycle/evidence events

Use UUIDs/ULIDs, `TIMESTAMPTZ`, explicit enums/checks, foreign keys, unique
constraints, and optimistic version columns. Do not store large market data or
report bodies in these tables.

### Data plane

- Immutable vendor data and report artifacts in content-addressed object
  storage; filesystem storage may implement the same port locally.
- Partitioned Parquet for ticks/candles/features.
- DuckDB for local analysis and reproducible snapshots.
- PostgreSQL stores dataset manifests, partitions, hashes, and provenance.
- SQLite remains permitted only for isolated developer/virtual-broker runs and
  must export into canonical evidence contracts.

## Migration strategy

1. Introduce Alembic and baseline the existing PostgreSQL schema without
   destructive changes.
2. Add canonical control/evidence/run tables and schema-version metadata.
3. Import catalog strategies and derive stable IDs; preserve original YAML
   hashes as migration evidence.
4. Import SVOS JSONL versions/evidence/decisions/approvals idempotently.
5. Add repository interfaces and dual-read comparison; do not dual-write
   lifecycle state because it creates two authorities.
6. Cut lifecycle writes to PostgreSQL in one controlled release. Generate YAML
   as a read-only compatibility projection.
7. Reconcile replay/trade data using stable run IDs and documented precision.
8. Validate row counts, hashes, referential integrity, and a sampled semantic
   comparison; retain rollback snapshots.
9. Remove direct psycopg2/ORM duplication after callers use one repository.

## Success criteria

- Migration up/down tested from an empty DB and a production-like snapshot.
- Gate decision, evidence binding, transition, and outbox commit atomically.
- A strategy version/run can reproduce its code, parameters, dataset, and seed.
- No service uses YAML as lifecycle authority.
- Backup restoration meets declared RPO/RTO and is exercised.

