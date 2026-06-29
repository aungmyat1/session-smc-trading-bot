# SVOS Two-Node Deployment Topology

Date: 2026-06-29  
Status: Infrastructure preparation in progress  
Safety mode: `LIVE_TRADING=false`, `DEMO_ONLY=true`

## 1. Deployment Decision

Use the two VPS instances as separate security and workload zones:

| Node | Role | Permitted workloads | Prohibited workloads |
|---|---|---|---|
| VPS 1 (`auto-trade-vps`) | Control, development, and downstream execution | source development, dashboard/API during migration, package verification, Vantage demo worker, execution monitoring | bulk research builds, authoritative research database, qualification from local YAML |
| VPS 2 (`gcp-vm1`) | Strategy engineering research plane | PostgreSQL, market data, replay, backtest, robustness, Virtual Demo, evidence/report generation | broker credentials, Vantage order submission, live-trading enablement |

The nodes communicate over Tailscale or an SSH tunnel. PostgreSQL and internal
services must not be exposed on a public interface. VPS 1 may retrieve approved
packages and read reports; VPS 2 cannot call the broker.

## 2. Current Inventory

### VPS 1

- Machine class: GCP `e2-medium`, 2 vCPU, approximately 3.8 GiB RAM.
- Root disk: 40 GB, approximately 3.9 GB free before data offload.
- Existing market data: approximately 7.4 GB under `data/`.
- Existing DuckDB/research artifacts: approximately 437 MB.
- PostgreSQL 16 is active locally.
- The existing bot and spread-capture processes are active and must not be
  interrupted during platform construction.

### VPS 2

- Machine class: GCP `e2-micro`, 2 shared vCPU, approximately 955 MiB RAM.
- Root disk: 30 GB, approximately 24 GB free before data import.
- Docker is installed; `quant-postgres` (PostgreSQL 16) is healthy.
- PostgreSQL currently occupies a small Docker volume.
- No swap is configured.
- The checked-out application tree under `/opt/session-smc-trading-bot` is a
  deployment copy rather than a Git working tree.

The current VPS 2 is sufficient for database/schema work, report development,
small fixtures, and a preserved copy of the existing dataset. It is not
approved for memory-intensive full research runs until a constrained profile
passes without OOM, or the VM is resized.

## 3. Canonical VPS 2 Filesystem

```text
/srv/svos/
  data/market/          immutable/frozen market inputs and snapshots
  artifacts/            content-addressed evidence, reports, and packages
  backups/postgres/     logical database backups and checksums
  manifests/            dataset, transfer, and infrastructure manifests
  runtime/              queues, locks, temporary run state

/opt/svos-platform/
  releases/<release-id>/ immutable application releases
  current -> releases/<release-id>

/etc/svos/               root-owned environment/configuration, never in Git
```

Preparation creates `/srv/svos` first and leaves the legacy `/opt` application
tree and PostgreSQL volume intact. A later release cutover may introduce
`/opt/svos-platform`; it must not replace the current deployment until its
health and rollback checks pass.

## 4. Data Transfer and Cutover Rules

1. Confirm source data is quiescent or take a named snapshot.
2. Create a logical PostgreSQL backup and SHA-256 checksum on VPS 2.
3. Copy with resumable `rsync`; never delete the VPS 1 source during transfer.
4. Run a checksum-based dry comparison and store the result as a transfer
   manifest.
5. Verify file count, byte count, dataset readability, and available capacity.
6. Declare `/srv/svos/data/market` canonical only for research workers on VPS 2.
7. Keep execution-required data on VPS 1; do not make broker safety depend on a
   cross-region filesystem mount.
8. Remove source research copies only in a later, explicit cleanup after
   backup and recovery checks.

## 5. PostgreSQL Boundary

- PostgreSQL remains on VPS 2 and receives the dedicated SVOS database and
  least-privilege roles defined in the requirements.
- Bind the database to loopback and use SSH/Tailscale forwarding, or bind only
  to a protected Tailscale address after firewall verification.
- The current all-interface Docker port publication is a security finding and
  must be corrected before SVOS credentials or canonical evidence are loaded.
- Take and verify a logical backup before Compose, role, schema, or port changes.
- Alembic owns new SVOS schemas; the existing `schema_v2.sql` is baseline input,
  not migration authority.

## 6. Capacity Gate

The infrastructure preparation gate passes when:

- VPS 1 has at least 15 GB free after a verified data offload or has a separate
  persistent volume;
- VPS 2 retains at least 12 GB free after the initial dataset and backup copy;
- PostgreSQL backups have verified checksums and a restore rehearsal;
- a constrained test profile proves the current VPS 2 does not OOM; and
- full replay/backtest/robustness runs remain disabled until VPS 2 has at least
  8 GB RAM, with 16 GB recommended.

Increasing the VM size or disk is a paid infrastructure change and requires an
explicit owner decision. The platform must report insufficient capacity as
`BLOCKED`, not silently reduce qualification work.

## 7. Rollback

- VPS 1 continues to use its current paths and processes during preparation.
- VPS 2 retains its legacy `/opt/session-smc-trading-bot` tree and Docker volume.
- Restore PostgreSQL from the latest checksum-verified logical backup if a
  schema/bootstrap test fails.
- Delete no source dataset until the remote checksum comparison and a sample
  read both pass.
