# Database Topology Audit

Date: 2026-07-01
Status: Read-only audit finding
Scope: Phase 5 of the deployment-topology validation audit

## Inventory

| Database | Location | Size | Type | Owner module | Classification |
|---|---|---|---|---|---|
| `vmassit` | `postgresql+asyncpg://trading:...@127.0.0.1:5432/vmassit` (per `.env` `DATABASE_URL`) | remote/unknown row count | PostgreSQL 16 | `db/control_plane.py`, `db/models.py` | **Production + Research (co-located)** — see below |
| `research.db` | repo root, `/home/aungp/session-smc-trading-bot/research.db` | 11 MB | DuckDB | `research_db/client.py` (`ResearchDB`) | SVOS/Research |
| `research_sweep.db` | repo root | 5.3 MB | DuckDB | `src/analytics/sweep.py` | SVOS/Research |
| `research_db/feature_database.duckdb` | `research_db/` | 270 MB | DuckDB | `src/research_feature_database.py` | SVOS/Research |
| `research_db/feature_database.parquet` | `research_db/` | 64 MB | Parquet | mirror/cache of the above | SVOS/Research |
| `data/trade_journal.db` | `data/` | 24 KB | SQLite | unclear — no active writer found | Ambiguous/likely orphaned |
| `execution_validation/execution_validation.sqlite3` | `execution_validation/` | 588 KB | SQLite | `execution_simulator/database/execution_log.py` | Production-adjacent (offline validation audit log) |
| `data/svos/registry/*/state.json` (×8 strategies) | `data/svos/registry/` | ~4 KB each | JSON, not SQL | SVOS lifecycle registry | Shared/SVOS |

## `vmassit` (Postgres) schema breakdown

Per `db/models.py`, this single instance holds schemas for both concerns:

- **market**: `Instrument`, `Candle`, `AsianRange`, `SessionRange`, `SmcEvent`
- **research**: `Strategy`, `ReplayRun`, `Trade`, `TradeFeature`, `DailyEquity`
- **governance**: `StageState`, `GateDecision`, `Approval`, `Outbox`
- **strategy**: `StrategyEntity`, `StrategyVersion`
- **execution**: `VirtualOrder`, `VirtualFill`, `VirtualPosition`, `DriftObservation`
- **operations**: `Deployment`, `Incident`

This is the one database that does **not** cleanly map to the prompt's expected split
("Production DB: orders/positions/execution/portfolio/monitoring" vs. "SVOS DB:
research/validation/experiments/reports/strategies") — it holds both sets of tables in one
instance, and per `deployment_topology_validation.md` that instance currently runs on VPS 1
(loopback `127.0.0.1`), not on the VPS 2 research node the topology doc designates as the
Postgres owner. This is a live gap versus the target design, not a hard architectural flaw —
`docs/svos/DEPLOYMENT_TOPOLOGY.md` §5 already schedules the Postgres boundary/cutover work.

## Cross-access check

- Research code (`research_db/client.py`, `src/research_feature_database.py`) does not open the
  `vmassit` Postgres connection string or any production DB file — it writes only to the local
  DuckDB files above.
- Production/execution code (`execution/`, `dashboard/`) does not read or write `research.db`,
  `research_sweep.db`, or `feature_database.duckdb`.
- `execution_validation.sqlite3` is isolated — an audit log for offline signal/order replay
  comparison, not shared with either the Postgres instance or the DuckDB research files.
- `data/svos/registry/*/state.json` is read by both the SVOS lifecycle manager (write authority)
  and `execution/governance_guard.py` (read-only, per `module_boundary_analysis.md`) — this is
  the intended shared-state contract, not a violation.

**No cross-database read/write violations found.** The one structural finding is that the
Postgres instance mixes production and research schemas in a single database/host rather than
the two being physically separated — which is explicitly still in progress per
`docs/svos/PREFLIGHT_STATUS.md`'s "Next safe actions" (provision dedicated SVOS Postgres
roles/database, complete the VPS 2 cutover).

## `data/trade_journal.db` — orphan flag (informational only)

At 24 KB, unreferenced by any writer found during this pass, and pre-dating the current
`core/trade_journal_db.py` / Postgres `execution` schema, this file looks like a leftover from
before the Postgres migration. Flagged for future cleanup consideration — not touched by this
audit.
