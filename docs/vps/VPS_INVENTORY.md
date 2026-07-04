# VPS Inventory

Date: 2026-07-04
Status: Review
Snapshot: 2026-07-04T11:20:24Z
Host: `auto-trade-vps.asia-southeast1-b.c.auto-489108.internal`

## Scope and safety

Read-only inventory of the primary trading VPS. No service, package, configuration, trading state, or data was changed. Pseudo-filesystems were excluded from storage scans. Commands requiring root that were unavailable are called out.

## Hardware and storage

| Item | Observed state |
|---|---|
| Platform | Google Compute Engine VM (KVM), x86-64 |
| CPU | 2 vCPU, AMD EPYC 7B12; 1 core / 2 threads |
| RAM | 3.8 GiB total; 2.4 GiB used; 1.4 GiB available; 646 MiB free |
| Swap | 2.0 GiB `/swapfile`; 0 used |
| Root disk | Google Persistent Disk, 40 GB |
| Root filesystem | `/dev/sda1`, ext4, 38 GiB; 31 GiB used; 6.9 GiB available; **82% used** |
| Boot | `/dev/sda16`, ext4, 881 MiB; 15% used |
| EFI | `/dev/sda15`, vfat, 105 MiB; 6% used |
| Other mounts | tmpfs runtime mounts and one read-only snap mount; no separate data disk |

## Operating system

- Ubuntu 24.04.4 LTS (Noble), kernel `6.17.0-1020-gcp`.
- Uptime at snapshot: 10 minutes; load average `0.31 0.26 0.13`.
- 1,236 dpkg packages installed; 107 explicitly/manual packages.
- Important manual packages: Docker CE/CLI/Compose, containerd, PostgreSQL 16/client, Node.js, Python 3.12 tooling, Caddy, Tailscale, Fail2ban, Chrony, Google agents, Wine staging, SSH.
- `apt-get -s autoremove`: zero removable packages; 15 upgrades pending.
- Complete installed-package inventory is reproducible with `dpkg-query -W`; no package changes were made.

## Running system services

Twenty-seven services were running at capture: Avahi, Chrony, cron, D-Bus, Fail2ban, Google guest/OS Config agents, console gettys, `live-dashboard`, multipathd, network dispatcher, polkit, PostgreSQL 16, rsyslog, snapd, SSH, systemd host/journal/login/network/resolve/udev components, Tailscale, unattended upgrades, and two user managers.

`systemctl --failed` reported zero failed units at the instant sampled, but `smc-demo-runner.service` was in `activating/auto-restart` and therefore escaped that failed-unit view. See `RUNNING_SERVICES.md`.

## Docker

- Docker packages and binaries are installed.
- `docker.service` and `containerd.service` are disabled and inactive; `/var/run/docker.sock` does not exist.
- `/var/lib/docker` and `/var/lib/containerd` each use 4 KiB.
- Consequently there are no inspectable local images, containers, networks, volumes, or unused Docker resources.
- `/opt/benchmark-bot` has a disabled unit that would invoke Docker Compose, but it is not running.

## Python

- System Python: 3.12.3. No Conda, Mamba, or Micromamba executable found.
- Known project environments: primary repo `.venv` 1.4 GiB; `simple-smc-ag-trading-bot/.venv` (included in its 745 MiB project); `/opt/forex-validate/.venv` 416 MiB.
- Pip cache: 35 MiB, 84 HTTP files, no locally built wheels.
- Active production-facing dashboard uses the primary repository `.venv`; it is never a cleanup candidate without a controlled rebuild test.

## Node.js

- Node `v20.20.2`; npm `10.8.2`; pnpm and yarn not found.
- npm tree: 241 MiB, including active `_npx` MCP processes.
- Notable `node_modules`: dashboard 156 MiB; VS Code server generations and extensions about 670 MiB combined; global user modules 108 MiB; Antigravity server about 54 MiB.

## Databases

- PostgreSQL 16 cluster `main`: online, local-only `127.0.0.1:5432`, accepting connections. Databases: `vmassit` 11 MiB, `template1` 7.6 MiB, `postgres` 7.5 MiB, `template0` 7.3 MiB.
- Redis is not installed and no Redis unit exists.
- Protected project databases include `research_db/feature_database.duckdb` 283 MiB, `research.db` 10.8 MiB, `research_sweep.db` 5.5 MiB, `execution_validation.sqlite3` 876 KiB, and `data/trade_journal.db` 52 KiB.
- Tool/user databases include Codex `logs_2.sqlite` 382 MiB and various IDE state databases. None were deleted.

## Startup mechanisms

- Custom systemd units found: `live-dashboard`, `smc-demo-runner`, `smc-bot`, `forex-bot`, `benchmark-bot`, and `agent-webhook-vps` (plus unit files not currently loaded such as `agent-webhook-vps`).
- Enabled custom units: `live-dashboard` and `smc-demo-runner`. The other named custom units are disabled/inactive.
- 18 active timers were listed, all OS/cloud maintenance timers. No user crontab exists for `aungp`; no custom cron payload was found in standard cron directories.
- No evidence of a separate custom startup script outside systemd references was found.

## Network listeners

| Bind | Purpose |
|---|---|
| `0.0.0.0:22`, `[::]:22` | SSH |
| `0.0.0.0:8090` | Trading dashboard API |
| `127.0.0.1:5432` | PostgreSQL |
| `0.0.0.0:54112` | Developer Next.js process |
| loopback dynamic ports | VS Code/Pylance |
| Tailscale addresses/UDP 41641 | Tailscale |
| UDP 5353 | Avahi/mDNS |

Firewall status could not be read because `ufw status` requires root; package/unit presence alone does not prove policy enforcement.
