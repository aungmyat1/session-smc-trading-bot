# Database Cutover Readiness Report

Date: 2026-07-01
Scope: Phase 1 of the architecture-separation migration
Related: `database_inventory.md`, `database_target_architecture.md`, `postgres_cutover_plan.md`

## Verdict: **NOT READY** for live cutover execution (Steps 1–5 of `postgres_cutover_plan.md`)

Planning artifacts (inventory, target design, cutover plan — this Phase 1 deliverable) are
complete. Two pre-conditions from the cutover plan are outstanding; the copy itself is
low-risk once they're closed.

## Checklist

| Check | Result | Detail |
|---|---|---|
| PostgreSQL version match | **PASS** | Both hosts run 16.14 — dump/restore compatible, no version-upgrade step needed |
| VPS 1 disk space | **PASS** (tight) | 6.8 GB free / 38 GB, 83% used. Source dataset is 11 MB — trivial relative to free space. Matches `PREFLIGHT_STATUS.md`'s prior "90% utilized" finding, slightly improved |
| VPS 1 RAM | **PASS** | 3.8 GiB total, 446 MiB free, 1.4 GiB available, 2 GiB swap configured — sufficient for a `pg_dump` of an 11 MB database |
| VPS 2 disk space | **PASS** | 16 GB free / 29 GB, 44% used — comfortably clears the §6 capacity-gate floor for DB/schema work |
| VPS 2 RAM | **WATCH** | 955 MiB total, 355 MiB free, **no swap**. Sufficient for a `pg_restore` of an 11 MB dump (this is not a full research workload); still far below the 8 GB gate `DEPLOYMENT_TOPOLOGY.md` §6 requires before *running* replay/backtest/robustness workloads — that gate is unrelated to this copy and remains unmet |
| Docker status (VPS 2) | **PASS** | `quant-postgres` (postgres:16-alpine) healthy, up 5 days |
| Backup location | **PASS** | `/srv/svos/backups/postgres/` exists; already holds one checksum-verified backup from 2026-06-29. Same path is the target for the new pre-cutover dump |
| Backup/restore tooling | **PASS** | `scripts/control_plane_backup.py` exists, tested pattern (encrypted, SHA-256 manifest, CONFIRM-gated restore) — reuse, no new tooling needed |
| Network connectivity | **PASS** | Tailscale online both directions (`auto-trade-vps` ↔ `gcp-vm1`); SSH via `~/.ssh/google_compute_engine` confirmed working both ways; `rsync` present on both hosts |
| VPS 2 Postgres network exposure | **FAIL** | Published on `0.0.0.0:5432` and `[::]:5432`, `listen_addresses=*` — this is a known, already-flagged finding (`PREFLIGHT_STATUS.md` "Blocking" → "VPS 2 PostgreSQL currently publishes port 5432 on all host interfaces"), still uncorrected. Must be restricted to loopback/Tailscale **before** the `svos` database or any credential is loaded there, per `DEPLOYMENT_TOPOLOGY.md` §5 |
| Dedicated SVOS role/database (VPS 2) | **FAIL** | Only role present is `trading_user` (superuser/create-db/create-role/replication/bypass-RLS) — the container's sole account. No least-privilege `svos_app`-equivalent role exists yet. An existing `trading_research` database has 4 empty, non-matching schemas from an earlier bootstrap and should not be reused as-is (see `database_target_architecture.md`) |
| Target schema/data classification | **PASS** | Full 12-schema, 46-table inventory taken live from `vmassit`; none of it is live-broker order/position data (that's file-based, `logs/bot_state.json`, out of scope) |
| Production service impact | **PASS (none expected)** | `smc-demo-runner.service` and `live-dashboard.service` remain untouched by this plan; no restart, no config repoint performed in Phase 1 |

## Reasons for NOT READY

1. **VPS 2 Postgres is still exposed on all interfaces.** Loading a dedicated SVOS
   database/credentials onto a publicly-bound Postgres port would create the exact
   security exposure `DEPLOYMENT_TOPOLOGY.md` §5 and `PREFLIGHT_STATUS.md` already
   flag as blocking — this must close first, independent of this migration.
2. **No least-privilege role or dedicated database provisioned on VPS 2 yet.** Restoring
   into `trading_user`-owned space, or reusing the mismatched `trading_research` scaffold,
   would not meet the target architecture in `database_target_architecture.md`.

Neither blocker requires new infrastructure or a resize — both are configuration fixes
achievable on VPS 2 alone (bind address change + `CREATE ROLE`/`CREATE DATABASE`), and are
naturally the first two actions under Step 4 of `postgres_cutover_plan.md`. Once done, the
actual data copy (11 MB, version-matched, tooling already proven) is low-risk and can proceed
without further capacity work.

## Recommendation

1. Close the two FAIL items above (network exposure + role/DB provisioning) as a small,
   separately-approved VPS 2 configuration change — not a data migration, so it can happen
   before or independent of scheduling the copy itself.
2. Then execute `postgres_cutover_plan.md` Steps 1–5 (backup → verify → transfer → import →
   validate). No owner-approved capital/resize decision is required for this step.
3. Do **not** proceed to Step 6 (application repoint / `.env` change) without a separate,
   explicit CONFIRM — out of scope for this Phase 1 planning task.
4. The VPS 2 RAM/capacity gate (8 GB, §6) remains a distinct, later concern for *running*
   research workloads — it does not block this database-copy step and should not be conflated
   with it.
