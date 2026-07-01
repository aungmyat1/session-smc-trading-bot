# Architecture Separation Migration Baseline

Date: 2026-07-01
Status: Observed
Version: 1.0
Owner: Platform Architecture
Authority: Level 7 — Migration Evidence
Related: ../svos/DEPLOYMENT_TOPOLOGY.md, ../SYSTEM_ARCHITECTURE.md, current_test_status.md, safety_state.md

## Scope and Method

This is the read-only Phase 0 baseline for separating the Production Trading
Engine from SVOS. It records the repository and the locally observable state of
`auto-trade-vps`. It does not change services, databases, trading logic, risk
parameters, or deployment configuration. Credentials and secret values are not
recorded.

The remote `gcp-vm1` host was not contacted during this snapshot. Its role below
comes from the authoritative deployment topology; its live service state remains
to be verified during a separately approved infrastructure audit.

## Repository Snapshot

| Field | Value |
|---|---|
| Baseline commit | `d162373b08ee9d43392c09704fd02428f0823f9c` |
| Starting branch | `main` |
| Migration branch | `architecture/separate-svos-production` |
| Starting worktree | Clean |
| Uncommitted files before Phase 0 | None |

## Corrected Deployment Topology

```yaml
production:
  node: auto-trade-vps
  role: downstream execution and live operations

svos:
  node: gcp-vm1
  role: research, validation, evidence, registry, and packaging
```

The connection between the zones is intended to be a versioned, validated
strategy artifact. Production must not perform research. SVOS must not submit
broker orders or possess broker credentials.

## Locally Observed Services: `auto-trade-vps`

Snapshot host:
`auto-trade-vps.asia-southeast1-b.c.auto-489108.internal`

### systemd

| Unit | State | Purpose |
|---|---|---|
| `smc-demo-runner.service` | active/running | Runs `SMCOrderBlockFVGSession` in demo mode every 60 seconds |
| `live-dashboard.service` | active/running | Uvicorn live-status dashboard on port 8090 |
| `postgresql@16-main.service` | active/running | Local PostgreSQL 16 cluster |
| `d2e3.service` | not installed | Deployment unit exists in the repository but not on this host |

The demo runner had `85` recorded systemd restarts at inspection time. Recent
logs showed normal tick cycles mixed with repeated MetaAPI subscription timeout
and reconnect errors. It was alive, but not healthy enough to call fully
operational.

### Processes

- Uvicorn: `dashboard.status_server:app`, port `8090`.
- Strategy runner: `scripts/run_strategy_demo.py --strategy
  SMCOrderBlockFVGSession --mode demo --interval 60`.
- No local SVOS pipeline, replay, optimizer, or research worker was observed.

### Containers, timers, cron, and workers

- Docker API was unavailable because the Docker daemon/socket was not present;
  no running containers could be observed on this host.
- No user crontab exists for `aungp`.
- No application-specific systemd timer was active. Only the operating-system
  package database backup timer matched the broad inventory scan.
- No Celery or equivalent background worker was observed.
- Repository deployment definitions under `deploy/gcp-vm1/` include PostgreSQL,
  D2E3, journal-sync, reconciliation, and dashboard units. Their directory name
  and contents conflict with the corrected node boundary and require Phase 1
  classification; they were not changed in Phase 0.

## Databases

### Production host database

- Engine: PostgreSQL `16.14`.
- Cluster: `16/main`, online on local port `5432`.
- Databases: `postgres`, `vmassit`.
- Application database: `vmassit`.
- Alembic repository head: `003`.
- `public.alembic_version` exists in `vmassit`.
- No database named `svos` or `trading_research` exists on this host.

Observed application schemas in `vmassit`:

- production-facing: `execution`, `operations`;
- research/SVOS-facing: `research`, `analytics`, `experiments`, `robustness`,
  `evidence`, `governance`, `strategy`, `market`, `config`;
- compatibility/default: `public`.

This confirms that database responsibilities are not yet physically separated:
research, governance, evidence, and execution schemas coexist in one database.

### SVOS database

The authoritative target places PostgreSQL and the research database on
`gcp-vm1`. Its current engine state, schemas, migration revision, and service
health were not directly verified in this local Phase 0 inspection.

### File-backed persistence

The repository also contains JSON/JSONL SVOS registry and approval artifacts,
SQLite trade journals, runtime JSON state, Parquet datasets, and report files.
These coexist with PostgreSQL and must be classified in Phase 1 before any
migration.

### Backup status

No PostgreSQL dump, checksum manifest, or restore-evidence artifact was found in
the locally searched repository, `/srv`, `/var/backups`, or user tree. Backup and
restore readiness is therefore **not verified**. This matches the documented
open P0-2 backup/restore gate.

## Deployment Method

- Production services are managed by systemd and shell wrappers.
- The working tree is under `/home/aungp/session-smc-trading-bot`; installed unit
  templates still reference `/opt/session-smc-trading-bot` in places.
- `deploy/gcp-vm1/docker-compose.yml` defines a PostgreSQL research stack but is
  not active on the inspected production host.
- No deployment action was performed.

## Dashboards and APIs

### Active live-status service

- `GET /` and `GET /dashboard/`: dashboard UI.
- `GET /api/status`: runtime status; responded successfully during baseline.
- `GET /api/control/state` and `/api/control/permission`: control state and
  execution permission.
- `GET /api/health/summary` and `/api/readiness/report`: health/readiness.
- `GET /metrics`: Prometheus-style metrics.
- `POST /api/emergency-stop` and `/api/emergency-stop/clear`: token-confirmed
  operator controls.

The service has no `/health` route; that probe returned HTTP 404. Its supported
health endpoint is `/api/health/summary`.

### Additional repository dashboard surfaces

The repository also contains a combined Flask dashboard with SVOS, EVF,
governance, reports, live operations, and strategy-control routes, plus a
separate legacy live Flask app. This is an observed mixed responsibility and a
Phase 1 boundary-analysis subject.

## Baseline Findings

1. The authoritative two-node intent is clear, but code, deployment definitions,
   dashboards, and the local database still mix production and SVOS concerns.
2. Production safety defaults are active, but the demo runner has recurring
   broker subscription errors and substantial restart history.
3. Catalog state and runtime state differ: no strategy is approved/current in
   the catalog, while a draft strategy demo runner is operationally active.
4. Backup/restore evidence and remote SVOS runtime health are not verified.
5. The baseline test and safety details are recorded in the companion files.

