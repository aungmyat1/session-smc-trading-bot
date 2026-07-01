# Target Database Topology

Date: 2026-07-01
Status: Proposed — awaiting owner review before cutover
Scope: Phase 1 of the architecture-separation migration
Related: `database_inventory.md`, `../svos/DEPLOYMENT_TOPOLOGY.md` §5, `postgres_cutover_plan.md`

## Deviation from the assumed template — read this first

The requested split was:

```
Production DB (auto-trade-vps): orders, positions, execution, portfolio, monitoring
SVOS DB (gcp-vm1): research, validation, experiments, reports, strategies
```

Live inventory (`database_inventory.md`) shows this template doesn't map onto what actually
exists. `vmassit`'s 12 schemas are **all** research/governance/analytics/evidence data or
Phase 5 offline virtual-demo simulator state — there is no live-broker orders/positions/
portfolio/monitoring schema in Postgres to keep on VPS 1. Real trading runtime state lives in
`logs/bot_state.json` on VPS 1, outside Postgres, and is out of scope for this database
migration entirely.

**Recommended target: migrate the entire `vmassit` database to VPS 2, unsplit.** VPS 1 keeps
no application database in its local Postgres cluster after cutover.

## Target topology

```yaml
VPS 1 (auto-trade-vps):
  postgresql@16-main: no application database (system databases only)
  application state: logs/bot_state.json (file-based), unchanged, untouched by this migration

VPS 2 (gcp-vm1):
  docker quant-postgres:
    database: svos            # new, dedicated — do NOT reuse trading_research as-is (see below)
    schemas: market, research, governance, strategy, analytics, execution,
             experiments, robustness, evidence, operations, config, public
    role: svos_app             # new least-privilege role — do NOT use trading_user (superuser) for app traffic
    network: loopback + Tailscale only (0.0.0.0 exposure must be closed first)
```

### Why not reuse `trading_research`

It already exists with 4 empty schemas (`analytics`, `config`, `market`, `research`) that don't
match the 12-schema source set and predate this inventory. Reusing it risks a silent partial
overwrite or a confusing mixed-origin schema. Since it holds zero tables, there is no data-loss
risk in either dropping and recreating it as `svos`, or renaming it — that decision belongs to
whoever executes cutover, not this planning pass. Recommendation: create a fresh `svos` database
and formally retire `trading_research` once confirmed unused elsewhere.

### Why a new role instead of `trading_user`

`trading_user` is the container's only role and holds full superuser/create-role/create-db/
replication/bypass-RLS privileges — the same account Docker's own bootstrap and any admin task
uses. Per `DEPLOYMENT_TOPOLOGY.md` §5 ("dedicated SVOS database and least-privilege roles"),
application code should connect as a scoped role (`CONNECT` on `svos` + schema-level
grants only), not the container superuser. This is still an open item from
`PREFLIGHT_STATUS.md`'s "Next safe actions" — unaffected by, and a prerequisite alongside, this
migration.

## What does NOT move

- `logs/bot_state.json` and any other file-based execution/runtime state on VPS 1 — untouched.
- `execution_validation/execution_validation.sqlite3` — isolated offline audit log
  (`database_topology.md`), not part of this Postgres cutover.
- Local DuckDB research files (`research.db`, `research_sweep.db`,
  `research_db/feature_database.duckdb`) — a separate, already-isolated data path; out of scope
  for this Postgres-only migration.
- `data/trade_journal.db` — flagged as a likely orphan in the prior audit; no action here.

## Post-cutover application changes (not performed by this planning pass)

`DATABASE_URL` in `.env` on VPS 1 must point at VPS 2's Tailscale address instead of
`127.0.0.1` once cutover completes. This is an application-config change, not a database
change, and requires its own CONFIRM step per repo `CLAUDE.md` — not authorized by this
document.

## Capacity check against target

Per `DEPLOYMENT_TOPOLOGY.md` §6, the capacity gate for this move (schema/DB work only, not full
research workloads) only requires VPS 2 to hold the dataset + backups without OOM. At 11 MB of
data, this is far under any constrained-profile risk; the 8 GB RAM gate remains reserved for
full replay/backtest/robustness *execution*, which is a separate, later concern (`postgres_cutover_plan.md`
does not unblock that).
