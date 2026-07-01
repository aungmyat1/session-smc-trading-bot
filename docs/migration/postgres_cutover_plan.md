# PostgreSQL Cutover Plan — `vmassit` (VPS 1) → `svos` (VPS 2)

Date: 2026-07-01
Status: Proposed — planning only, no step in this document has been executed
Related: `database_inventory.md`, `database_target_architecture.md`, `database_cutover_readiness.md`

This plan follows the transfer rules already codified in `../svos/DEPLOYMENT_TOPOLOGY.md` §4/§7
and reuses the repo's existing encrypted backup tool (`scripts/control_plane_backup.py`) rather
than introducing a new mechanism.

## Pre-conditions (must all be true before Step 1 runs)

1. Owner has reviewed and approved `database_target_architecture.md`.
2. VPS 2 Postgres port exposure is corrected (currently `0.0.0.0:5432` — see readiness report).
3. Dedicated `svos` database + least-privilege `svos_app` role are provisioned on VPS 2.
4. No other process is actively writing to `vmassit` during the export window (verify
   `smc-demo-runner.service` and dashboard are not mid-write; they are read-mostly against this
   DB today per `database_topology.md`, but confirm live at cutover time, not from this doc).

## Step 1 — Backup (VPS 1, source)

Use the existing tool, not a new script:

```
python scripts/control_plane_backup.py backup /srv-equivalent/backups/vmassit-<UTC-timestamp>.sql.gpg
```

This produces:
- an AES-256-encrypted `pg_dump --format=custom --no-owner --no-acl` artifact
- a `.manifest.json` with a SHA-256 digest
- the artifact chmod'd `0400`

Additionally take a second, unencrypted `pg_dump --format=custom` for the dry-run restore
rehearsal in Step 3 (encrypted copy is the durable backup; plaintext copy is discarded after
verification).

## Step 2 — Checksum verification

`control_plane_backup.py`'s manifest already carries a SHA-256 of the encrypted artifact.
Additionally:
- `sha256sum` the plaintext dump before encryption and record it locally (not committed).
- After `rsync` to VPS 2 (Step 3), re-run `sha256sum` on the transferred plaintext dump and diff
  against the source value. Do not proceed to import on a mismatch.

## Step 3 — Export/transfer method

```
rsync -av --checksum <plaintext-dump> aungp@gcp-vm1:/srv/svos/backups/postgres/
```

Use `--checksum` (content-hash compare) not just size/mtime, given the dataset is small (11 MB)
and correctness matters more than transfer speed. Do not delete the VPS 1 source dump after
transfer — retain until Step 6 passes.

## Step 4 — Import method (VPS 2, target)

1. Create target database and role first (idempotent, run once):
   ```
   CREATE ROLE svos_app LOGIN PASSWORD '<from secret store, not this doc>';
   CREATE DATABASE svos OWNER svos_app;
   ```
2. Restore into the new, empty `svos` database:
   ```
   pg_restore --no-owner --no-acl --role=svos_app -d svos <plaintext-dump>
   ```
3. Grant schema-scoped privileges to `svos_app` per `database_target_architecture.md` (least
   privilege — no superuser).

## Step 5 — Post-import validation

- `\dn` on `svos` → all 12 source schemas present.
- Per-schema table count matches `database_inventory.md`'s table list exactly (12 schemas, 46
  tables total across the two research/analytics-heavy schemas + governance/strategy/etc.).
- Row counts on the non-empty tables (`market.instruments`, `market.smc_events`,
  `governance.stage_state`=1, `strategy.strategy`=2, `public.alembic_version`=1) match source.
- `alembic_version` value on target equals source — confirms migration head is preserved, not
  reset.

## Step 6 — Cutover decision point (STOP — requires CONFIRM)

Do not repoint `.env`'s `DATABASE_URL` or restart any service as part of this plan. Repointing
production/research code at the new database is an application-config change requiring its own
explicit CONFIRM per repo `CLAUDE.md`, and is intentionally excluded from this database-only
cutover plan (see `database_target_architecture.md` "Post-cutover application changes").

## Downtime requirements

**None required for the database copy itself** — `vmassit` stays live and untouched throughout
Steps 1–5; this is a copy, not a cutover of live traffic. `pg_dump --format=custom` is
non-blocking (MVCC snapshot). Downtime, if any, is only incurred later when `.env` is
repointed and the reading services restart — that step is out of scope here and would need its
own maintenance-window plan when proposed.

## Rollback plan

- Source `vmassit` on VPS 1 is never modified or dropped by this plan — it remains the live
  database for as long as `.env` still points at it. Rollback is simply "do nothing further":
  no application ever pointed at `svos` on VPS 2, so there is nothing to revert on the app side.
- If import validation (Step 5) fails: drop the partially-restored `svos` database on VPS 2 and
  re-run Step 4 from the verified dump. The VPS-2-side pre-existing `pre-platform-layout-*`
  backup and the empty `trading_research` scaffold are unaffected either way.
- If the encrypted backup's checksum ever fails to verify: do not restore from it; regenerate
  from `vmassit` (still live on VPS 1) and repeat from Step 1.

## Explicit restrictions carried over from the task scope

Do not, under this plan: drop any database, delete any schema, change any existing credential,
migrate any table into a location that replaces a still-in-use source, or restart
`smc-demo-runner.service` / `live-dashboard.service` / `postgresql@16-main.service`. Execution of
Steps 1–5 requires owner approval of this plan; Step 6 (app repoint) requires a separate,
later CONFIRM regardless.
