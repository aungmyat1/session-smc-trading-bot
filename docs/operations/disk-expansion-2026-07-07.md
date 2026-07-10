# Infrastructure Change Report — Boot Disk Expansion

Date: 2026-07-07
Host: `auto-trade-vps` (GCE, `asia-southeast1-b`)
Change type: Live persistent disk resize (no downtime)
Executed by: PM agent, with explicit owner confirmation before the billable action
Related: `docs/audit/capacity-plan.md`, `docs/operations/storage-governance.md`,
`config/storage_policy.yaml`

## Summary

Boot disk (`auto-trade-vps`, GCE pd-ssd) resized from **40GB → 50GB** (+10GB),
live, with the partition and filesystem grown online. Zero service
interruption. Free space improved from 5.1G (87% used) to 15G (69% used) —
comfortably past the 15%-free acceptance target (31% achieved).

## Pre-change verification

- Partition table inspected (`parted`): `/dev/sda1` already extended to the
  full current disk size — confirmed no unpartitioned space existed to grow
  into locally; a real GCE-level disk resize was required, not just a local
  operation.
- `gcloud` CLI confirmed available and authenticated (project `auto-489108`,
  zone `asia-southeast1-b`).
- Confirmed with owner before executing, since this is a real, recurring
  GCP billing increase (pd-ssd, billed per GB-month) applied to the live
  production host's boot disk.

## Before / After

| Metric | Before | After |
|---|---|---|
| GCE disk size | 40GB (pd-ssd) | 50GB (pd-ssd) |
| Root filesystem size (`df -h`) | 38G | 48G |
| Used | 33G | 33G (unchanged — no data added/removed) |
| Free | 5.1G | 15G |
| Used % | 87% | 69% |
| Inodes used | 381,666 / 5,111,808 (8%) | 381,668 / 6,422,528 (6%) |
| Docker storage | 4.0K (`/var/lib/docker`), inactive | 4.0K, unchanged |
| PostgreSQL data dir | 66M | 66M, unchanged |
| Application logs (`logs/`) | 18M | 18M, unchanged |

Inode total grew proportionally with the filesystem resize (ext4 allocates
inode tables at format time based on size, and `resize2fs` extended this
correctly) — inode usage percentage dropped from 8% to 6% even though the
used-inode count is effectively unchanged (381,666 → 381,668), confirming no
data was modified, only capacity added.

## Steps executed

1. `gcloud compute disks resize auto-trade-vps --zone=asia-southeast1-b --size=50GB` — GCE-level resize, live, disk stayed `READY` throughout.
2. Block device rescan check (`lsblk` already reflected 50G without needing an explicit SCSI rescan write).
3. `sudo growpart /dev/sda 1` — extended partition 1 from 39G to 49G.
4. `sudo resize2fs /dev/sda1` — grew the ext4 filesystem online (no unmount, no reboot) to fill the new partition size.

## Verification performed

- `df -h` (before/after) — confirmed above.
- Inode usage (`df -i /`) — confirmed no anomalies.
- Docker storage — confirmed unchanged (still inactive, 4.0K).
- PostgreSQL data directory size — confirmed unchanged (66M), `pg_isready` confirmed accepting connections post-resize.
- Application logs — confirmed unchanged (18M).
- **Service continuity**: `smc-demo-runner.service`, `live-dashboard.service`, `postgresql@16-main.service`, `tailscaled.service`, `ssh.service`, `fail2ban.service` all verified `active` after the change. Dashboard HTTP endpoint returned `200`. **The demo runner process (PID 345510) was the same PID before and after** — it was never restarted, confirming true zero-interruption of the live trading process throughout the entire resize.

## Data integrity

No data was deleted, moved, or modified at any point in this change. This
was a pure capacity-addition operation.

## Acceptance criteria — status

| Criterion | Status |
|---|---|
| Root filesystem increased successfully | ✅ 38G → 48G |
| Free space > 15% | ✅ 31% free (69% used) |
| No services interrupted | ✅ all 6 services active throughout; demo runner PID unchanged |
| Before/after disk report created | ✅ this document |

## Cost note

This is a recurring cost increase (pd-ssd billed per GB-month for the
additional 10GB) — small in absolute terms but ongoing, not one-time. Flagged
here for the record since it was the basis for requiring explicit
confirmation before execution.

## Relationship to open infrastructure questions

This resize addresses the **capacity** blocker independently of the
**MT5/Wine hosting** decision (`docs/svos/ADR-0013-MT5-EXECUTION-ARCHITECTURE.md`).
It does not change the recommendation in that ADR — Wine's reliability
problem on this host is unrelated to disk space and remains unresolved. This
change does, however, meaningfully de-risk Node 1's near-term capacity
posture (research dataset growth, log growth, general operating headroom)
regardless of which MT5 hosting path is ultimately chosen.
