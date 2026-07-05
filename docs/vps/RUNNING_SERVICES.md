# Running Services Audit

Date: 2026-07-04
Status: Review
Snapshot window: 2026-07-04T11:20–11:21Z

## Critical finding

`smc-demo-runner.service` is enabled but not operational. It restarts every 15 seconds because `run_st_a2_demo.py` rejects configured strategy `SMCOrderBlockFVGSession`; restart count rose from 41 to 44 during observation. This is a production-readiness incident and log-amplification risk. No change was made because this engagement is audit-only.

## Application and data services

| Service/process | Owner | CPU/RAM snapshot | Port / cwd | Startup | Class / importance |
|---|---|---|---|---|---|
| Live dashboard, Python/uvicorn PID 611 | `aungp` | 0.3%; 144 MiB RSS (unit 170 MiB) | `0.0.0.0:8090`; primary repo | enabled `live-dashboard.service`, restart always | Production-facing demo status; critical |
| SMC demo runner | `aungp` | transient | primary repo | enabled systemd, restart always | Intended production demo; **broken/restart loop** |
| PostgreSQL 16 | `postgres` | low; master 31 MiB RSS plus workers | `127.0.0.1:5432`; `/var/lib/postgresql/16/main` | enabled systemd | Production data/control plane; critical, healthy |
| VS Code extension host PID 1734 | `aungp` | 8.4%; 754 MiB RSS | loopback; `/home/aungp` | SSH user session | Development; temporary/high memory |
| Pylance PID 3087 | `aungp` | 6.2%; 596 MiB RSS | loopback | VS Code child | Development; temporary/high memory |
| Next.js PID 1937 | `aungp` | 0.9%; 211 MiB RSS | `0.0.0.0:54112`; dashboard extension cwd | VS Code child | Development/temporary; externally bound |
| Codex app server PID 1790 | `aungp` | 2.0%; 166 MiB RSS | no public port | VS Code extension | Development; active audit session |
| CircleCI MCP instances | `aungp` | ~4 MiB? parents plus 2×78 MiB RSS nodes | primary repo | npm children of Codex | Development; duplicate-looking but active; do not kill during session |

## Core OS/network services

SSH, Tailscale, Fail2ban, Chrony, Google guest/OS Config agents, journald/rsyslog, cron, unattended upgrades, networkd/resolved, D-Bus, polkit, udev, logind, snapd, multipathd, Avahi, and console/user managers were running. These are platform or access services; none is an orphan based on this snapshot.

Potential review item: Avahi exposes mDNS UDP 5353 and is usually unnecessary on a cloud trading VPS. Disable only after confirming no discovery dependency. Multipath/open-iscsi packages/units likewise deserve a dependency review, not immediate removal.

## Inactive custom services

| Unit | Working directory | State | Assessment |
|---|---|---|---|
| `smc-bot.service` | `simple-smc-ag-trading-bot` | disabled/inactive | Legacy; preserves repo/env reference |
| `forex-bot.service` | `/opt/forex-bot` | disabled/inactive | Legacy demo; protects `.env` and logs |
| `benchmark-bot.service` | `/opt/benchmark-bot` | disabled/inactive | Experimental Docker Compose stack |
| `agent-webhook-vps.service` | `auto-trade-system/scripts/agent_bus` | disabled/inactive | Unit references a path not present in top-level inventory; investigate before removal |

## Health and exposure

- PostgreSQL readiness passed and is loopback-only.
- Dashboard process and listener are alive; `/health` returned HTTP 404, so no valid health endpoint was established.
- Docker and containerd are inactive; no Docker health check applies.
- Redis is absent.
- `systemctl --failed` returned none, but does not represent the demo runner’s auto-restart failure state.
- Public/wildcard listeners needing firewall review: SSH 22, dashboard 8090, developer Next.js 54112, Avahi 5353. UFW policy could not be inspected without root.
