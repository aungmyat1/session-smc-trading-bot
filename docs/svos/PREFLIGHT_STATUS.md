# Platform Implementation Preflight Status

Date: 2026-06-29  
Decision: **INFRASTRUCTURE PREPARATION IN PROGRESS**

## Completed

- Confirmed Python 3.12, Git, Docker, Compose, and PostgreSQL 16 tooling.
- Preserved tracked and untracked workspace changes outside the repository:
  - `/tmp/svos-worktree-20260629T070230Z.patch`
  - `/tmp/svos-untracked-20260629T070230Z.tar.gz`
- Created runtime and development requirement sources.
- Generated fully pinned SHA-256 runtime and development locks.
- Created an isolated `.venv` and installed the development lock with
  `--require-hashes`.
- Verified `pip check` reports no broken requirements.
- Verified all **1,170 tests pass** in the locked environment.
- Added repeatable Make targets for lock, install, test, quality, and preflight.
- Added initial Ruff and mypy configuration scoped to the new platform core.
- Completed `make preflight`: dependency check, Ruff, mypy, all 1,170 tests,
  and `git diff --check` pass.
- Confirmed and recorded the two-node boundary in
  `docs/svos/DEPLOYMENT_TOPOLOGY.md`.
- Confirmed VPS 2 (`gcp-vm1`) is online over Tailscale, with PostgreSQL 16
  healthy in Docker.
- Created the canonical `/srv/svos` data, artifact, backup, manifest, and
  runtime directories on VPS 2.
- Created a checksum-verified pre-layout logical PostgreSQL backup under
  `/srv/svos/backups/postgres` on VPS 2.
- Detected and contained live-configuration drift; the paired operating report
  is under
  `reports/svos/platform/incidents/INC-20260629-LIVE-CONFIG-DRIFT/`.
- Stopped the order-capable VPS 1 bot, retained spread capture, enforced
  `LIVE_TRADING=false` and `DEMO_ONLY=true` on both nodes, and removed broker
  credentials from the VPS 2 research environment.

Lock identities:

- `requirements.lock`:
  `3873e93a43dfd84ca0dd05a0a14a08e19239fbf218dbe97906b6ac02f00a0d43`
- `requirements-dev.lock`:
  `9bb67499b9c148cb626665724b2853b198f076e446a472513bb830d8df38716c`

## Blocking

### Host capacity

The VPS 1 root filesystem has approximately 3.9 GB free and is 90% utilized.
A resumable, non-destructive dataset copy to VPS 2 is in progress. Canonical
market data must not be deleted until checksum verification succeeds.

VPS 2 has approximately 24 GB free but only 955 MiB RAM and no swap. This is
sufficient for infrastructure preparation and constrained tests, not full
qualification runs. Paid VM/disk resizing is not authorized by this document.

### Worktree checkpoint

The external `/tmp` snapshot protects the current session but is not a durable
project checkpoint. Before schema or lifecycle implementation begins, create an
intentional commit/branch or copy the snapshot to durable external storage.
Do not discard the pre-existing dashboard changes.

### Database authority

The local PostgreSQL server responds, but the dedicated SVOS database, roles,
credentials, backup path, and restore test do not yet exist. Do not apply
migrations to an unidentified existing database.

VPS 2 PostgreSQL currently publishes port 5432 on all host interfaces. Correct
that exposure before loading SVOS credentials or canonical evidence. The
pre-change logical backup has already been created.

### Execution safety follow-up

The configuration drift is contained, but broker-side order/position history
for the affected interval still requires independent reconciliation. Do not
restart the order-capable bot during platform construction.

## Next safe actions

1. Complete and checksum-verify the VPS 2 dataset copy.
2. Create a durable worktree checkpoint without overwriting dashboard changes.
3. Restrict VPS 2 PostgreSQL exposure and prove backup restore.
4. Provision dedicated SVOS PostgreSQL roles and database.
5. Introduce the Alembic baseline and canonical report metadata schema.
