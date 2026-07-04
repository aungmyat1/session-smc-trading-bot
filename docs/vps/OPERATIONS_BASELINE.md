# VPS Operations Baseline

Date: 2026-07-04T16:43Z
Host: `auto-trade-vps` (GCP `asia-southeast1-b`, Ubuntu 24.04.4 LTS, kernel 6.17.0-1020-gcp)
Status: Snapshot — informational, no actions taken in this phase
Companion: `docs/vps/VPS_INVENTORY.md` (prior full inventory), `docs/vps/CLEANUP_REPORT.md` (Batch A-D actions already applied)

---

## 1. System

| Metric | Value |
|---|---|
| CPUs | 2 |
| Memory | 3.8 GiB total, 2.3 GiB used, 804 MiB free, 1.0 GiB buff/cache |
| Swap | 2.0 GiB total, 123 MiB used |
| Load average | 0.38, 0.24, 0.22 (1/5/15 min) — low relative to 2 vCPUs |
| Uptime | 46 minutes (recent reboot or restart) |
| Root filesystem | `/dev/root` ext4, 38G size, 31G used, 7.4G avail, **81%** used |
| `/boot` | 881M, 15% used |
| `/boot/efi` | 105M vfat, 6% used |

Disk usage reflects the state **after** `docs/vps/CLEANUP_REPORT.md` Batch A-D (84% → 81%, ~1.66 GiB reclaimed net across all batches so far).

## 2. Top resource consumers

**CPU** (top 5, excluding this baseline's own shell):
1. VS Code server extension host (node) — 4.2%
2. Claude Code CLI (this agent session) — 1.4%
3. VS Code remote server main — 0.3%
4. `tailscaled` — 0.3%
5. Pylance language server — 0.2%

**Memory** (top 5): same VS Code/agent-tooling processes dominate (878 MiB, 448 MiB, 311 MiB RSS respectively) — this is **developer/IDE tooling overhead, not production trading load**. The dashboard process (`uvicorn dashboard.status_server:app`, PID 596) uses 48 MiB RSS.

**Python processes:**
| PID | Command | Role |
|---|---|---|
| 596 | `.venv/bin/python -m uvicorn dashboard.status_server:app --port 8090` | Production — live dashboard backend |
| 553 | `fail2ban-server` | OS security service |
| 562 | `networkd-dispatcher` | OS networking |
| 677 | `unattended-upgrade-shutdown` | OS patching |
| 5650 | VS Code Python environment tool server | Dev tooling |

No `run_st_a2_demo.py` process is currently alive under a stable PID — it is crash-looping (see Phase 2 analysis) and each attempt exits in under 1 second.

**Node processes:** VS Code server (multiple), and two active MCP servers this coding session depends on: `mcp-server-circleci`, `pionex-trade-mcp` (both running from `~/.npm/_npx/*`) — **do not clear the npm cache while these are active** (already established in the prior cleanup pass).

**Docker:** `docker.service` and `containerd.service` are both `inactive`; no daemon socket present. Zero Docker resource usage — consistent with `docker ps -a` failing to connect.

## 3. Services — classification

Of ~150 systemd units on this host, the overwhelming majority are stock Ubuntu/cloud-init/GCE guest-agent services, unmodified and out of this project's scope (systemd internals, `snapd`, `apparmor`, `plymouth`, filesystem/udev helpers, etc.) — not itemized individually here to avoid noise; all report `active`/`exited` as expected for their type, and `systemctl --failed` confirms **zero failed units** platform-wide.

Project-relevant services:

| Service | Classification | Status | Restarts | Working dir | Startup | Importance |
|---|---|---|---:|---|---|---|
| `smc-demo-runner.service` | **Production — Broken** | `activating (auto-restart)` | **173** and climbing (~1 every 15s) | `session-smc-trading-bot` | systemd, enabled | Critical — this is the deployed demo trading runner; see Phase 2 analysis |
| `live-dashboard.service` | Production | `active (running)` | 0 | `session-smc-trading-bot` | systemd, enabled | High — operator's only live view |
| `postgresql@16-main.service` | Production | `active (running)` | 0 | n/a (pg_ctlcluster) | systemd, enabled | Critical — control-plane + operations.* schema (Sprint 2.3) |
| `agent-webhook-vps.service` | Unknown/legacy | `disabled` | n/a | `auto-trade-system/scripts/agent_bus` | disabled | Low — references a separate, unaudited `auto-trade-system` checkout outside this repo |
| `benchmark-bot.service` | **Broken (dangling)** | `disabled` | n/a | `/opt/benchmark-bot` | disabled | None — **working directory no longer exists**, deleted with approval in `CLEANUP_REPORT.md` Batch D; unit file itself is now a stale reference, safe cleanup candidate |
| `smc-bot.service` | **Broken (dangling)** | `disabled` | n/a | `~/simple-smc-ag-trading-bot` | disabled | None — **working directory/venv no longer exists**, same cause as above |
| `forex-bot.service` | Archived/legacy | `disabled` | n/a | `/opt/forex-bot` (260K, still present) | disabled | Low — tiny footprint, inert |
| `caddy.service` / `caddy-api.service` | Unused | `disabled` | n/a | n/a | disabled | None — no Caddyfile-driven routing confirmed in use; dashboard is served directly by uvicorn on :8090 |
| `d2e3.service`, `d2e3-journal-sync.*`, `reconcile-positions.*`, `agtrade-deployment-agent.*` | Deprecated (file-only) | `not-found` (not installed) | n/a | n/a | Present only as files in `deploy/gcp-vm1/systemd/`, never symlinked into `/etc/systemd/system/` | None currently — matches `SYSTEM2_MASTER_PLAN.md`'s existing note that these are a legacy/superseded path |

**New finding this phase:** `benchmark-bot.service` and `smc-bot.service` are now dangling references as a direct consequence of the prior cleanup session's approved deletions. Both were already disabled and inert before those deletions, so there is no operational impact — but the unit files themselves are dead weight. Flagged as a Phase 5 cleanup candidate (removing a disabled unit file pointing at a directory that no longer exists is unambiguously safe), not acted on in this phase.

## 4. Cron / timers

No project-specific cron jobs found under `aungp`'s crontab or `/etc/cron.d/` at the time of this snapshot beyond OS-standard `logrotate`/`man-db`/`apt` timers. No `pg_dump@`/`pg_basebackup@`/`pg_compresswal@` timers are active (their unit files exist under `/lib/systemd/system` per package defaults but are not enabled) — backups remain manual-only, consistent with `docs/database_authority_stabilization.md`'s "Remaining Limitations" §9.3.
