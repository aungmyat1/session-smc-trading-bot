# PostgreSQL Database Inventory

Date: 2026-07-01
Status: Read-only inventory — no schema, data, or config changed
Scope: Phase 1 of the architecture-separation migration (`architecture/separate-svos-production`)
Related: `../audit/database_topology.md`, `../svos/DEPLOYMENT_TOPOLOGY.md`, `../svos/PREFLIGHT_STATUS.md`

## Method

Live queries only, run directly against both hosts:
- VPS 1 (`auto-trade-vps`, this host): `sudo -u postgres psql` (local peer auth, no app credentials used).
- VPS 2 (`gcp-vm1`): `ssh gcp-vm1` (Tailscale, key configured in local SSH config) → `docker exec quant-postgres psql`.

No DDL/DML executed. No rows inserted, updated, or deleted.

## VPS 1 (`auto-trade-vps`) — cluster `postgresql@16-main`, active

| Database | Owner | Size | Notes |
|---|---|---|---|
| `vmassit` | `trading` | 11 MB | The only application database in this cluster |
| `postgres`, `template0`, `template1` | `postgres` | — | Stock system databases, unmodified |

`listen_addresses = localhost` — not network-exposed. Role `trading` has no superuser/create-role attributes (plain login role). This matches `.env`'s `DATABASE_URL=postgresql+asyncpg://trading:***@127.0.0.1:5432/vmassit`.

### `vmassit` schema/table breakdown (12 non-system schemas, all owned by `trading`)

| Schema | Tables | Size | Row-bearing? | Content |
|---|---|---|---|---|
| `market` | `instruments`, `candles`, `asian_ranges`, `session_ranges`, `smc_events` | 248 kB | yes (instruments, smc_events) | Shared reference/market data |
| `research` | `strategies`, `run`, `replay_runs`, `trades`, `trade_features`, `daily_equity`, `metric`, `signals` | 384 kB | not checked individually | Research/backtest results |
| `governance` | `stage_state`, `gate_decision`, `approval`, `outbox`, `stage_transition` | 240 kB | `stage_state`=1 row | SVOS lifecycle state (`svos/lifecycle/manager.py` is sole writer) |
| `strategy` | `strategy`, `version` | 120 kB | `strategy`=2 rows | Strategy catalog entities |
| `analytics` | `daily_equity`, `experiment_log`, `monthly_metrics`, `optimization_results`, `phase0_gate`, `portfolio_equity`, `stage_gate`, `strategy_metrics`, `walk_forward_results` | 360 kB | not checked individually | Backtest/robustness analytics |
| `execution` | `virtual_order`, `virtual_fill`, `virtual_position`, `drift_observation` | 96 kB | `virtual_order`=0 rows | **Phase 5 offline virtual-demo simulator state — not live broker orders** |
| `experiments` | `experiment`, `parameter_set`, `result_binding` | 80 kB | not checked | Backtest optimization experiments |
| `robustness` | `monte_carlo_result`, `sensitivity_result`, `walk_forward_result` | 64 kB | not checked | Robustness-test outputs |
| `evidence` | `artifact`, `binding`, `report_record`, `legacy_import` | 112 kB | not checked | Evidence/report records for approval packages |
| `operations` | `deployment`, `incident` | 48 kB | `deployment`=0, `incident`=0 rows | Empty; ambiguous ops-metadata schema |
| `config` | `system_config` | 32 kB | not checked | Shared config table |
| `public` | `alembic_version` | 24 kB | 1 row | Alembic migration marker |

**Applications accessing `vmassit`:** `db/control_plane.py` and `db/models.py` (SQLAlchemy models for all 12 schemas above), read by `svos/lifecycle/manager.py`, `execution/governance_guard.py` (read-only), `dashboard/app.py`, and research/backtest scripts under `svos/`, `research/`. No separate production-only database or schema exists in this cluster.

**Live broker/trading state is NOT in Postgres.** Per `docs/migration/safety_state.md`, the demo runner's actual position/order state lives in `logs/bot_state.json` (file-based), not in any table above. `execution.virtual_order`/`virtual_fill`/`virtual_position` are Phase 5 **simulator** records (per repo `CLAUDE.md` §2 Phase 5 definition), not live trades.

## VPS 2 (`gcp-vm1`) — Docker container `quant-postgres` (postgres:16-alpine), healthy, up 5 days

| Database | Owner | Notes |
|---|---|---|
| `trading_research` | `trading_user` | Pre-existing, from earlier bootstrap (`PREFLIGHT_STATUS.md`, 2026-06-29) |
| `postgres`, `template0`, `template1` | `trading_user` | Stock; note `trading_user` owns even the system databases — it is the container's sole superuser role |

### `trading_research` current contents

4 schemas already exist but hold **zero tables**: `analytics`, `config`, `market`, `research` (all owned by `trading_user`). These are leftover scaffolding from the earlier preflight pass and do not match the full 12-schema set found on VPS 1 — they predate this inventory and should not be assumed authoritative.

`listen_addresses = *`, container publishes `0.0.0.0:5432->5432/tcp` and `[::]:5432->5432/tcp` — **confirms the network-exposure finding already flagged in `DEPLOYMENT_TOPOLOGY.md` §5 and `PREFLIGHT_STATUS.md` "Blocking"**: Postgres is reachable on all interfaces, not just loopback/Tailscale. Not yet corrected.

Only one role exists: `trading_user` (Superuser, Create role, Create DB, Replication, Bypass RLS). No dedicated least-privilege SVOS role has been provisioned yet — matches `PREFLIGHT_STATUS.md` "Next safe actions" item 4 (still outstanding).

A checksum-verified pre-layout logical backup already exists at `/srv/svos/backups/postgres/pre-platform-layout-20260629T071408Z.sql.gz` (+ `.sha256`).

## Tooling available for the migration

- `scripts/control_plane_backup.py` — existing encrypted (`gpg --symmetric AES256`) `pg_dump --format=custom` backup with SHA-256 manifest, and a `pg_restore` path gated behind `--confirm CONFIRM-RESTORE-CONTROL-PLANE`. This is the repo's established backup/restore mechanism and should be reused rather than inventing a new one.
- `rsync` present on both hosts.
- Both hosts run PostgreSQL **16.14** — dump/restore is version-matched, no upgrade step needed.
- SSH connectivity confirmed both directions over Tailscale (`auto-trade-vps` ↔ `gcp-vm1`, private overlay-network addresses) using the configured SSH key.

## Key finding

**There is no separate "production" database or schema to leave behind on VPS 1.** Every schema in `vmassit` is research/governance/analytics/evidence data or Phase-5 virtual-demo simulator state — none of it is live broker order/position data (that lives in `logs/bot_state.json`, outside Postgres entirely). This changes the target split from the assumed template (see `database_target_architecture.md`).
