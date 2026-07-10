# MT5 Execution Node — Migration Plan

Date: 2026-07-07
Status: Plan only — no provisioning performed. Requires owner approval
(cloud provisioning access/cost) before Stage 1 begins.
Related: `docs/svos/ADR-0013-MT5-EXECUTION-ARCHITECTURE.md`,
`docs/svos/ADR-0011-MT5LINUX-BROKER-BRIDGE.md`, `docs/audit/wine-investigation-report.md`

## Infrastructure

### Node responsibilities

| | Node 1 — Trading System (`auto-trade-vps`, existing) | Node 2 — MT5 Execution (new) |
|---|---|---|
| Runs | Strategy engine, dashboard, PostgreSQL, research/analytics, monitoring | Wine, MT5 terminal, mt5linux RPyC server |
| Trading logic | Yes — unchanged | No |
| Broker credentials | No (post-migration) | Yes — `VANTAGE_MT5_DEMO_LOGIN/PASSWORD/SERVER` |
| Public/dashboard exposure | Yes (existing) | No — Tailscale-only |
| Migrates | Nothing — stays as-is | N/A — new node |

### Network design

- Node 2 joins the existing Tailscale mesh (already used by `auto-trade-vps`
  per `docs/vps/VPS_INVENTORY.md`) — no new VPN/tunnel technology.
- Node 1's `execution/mt5linux_connector.py` connects to Node 2 via
  `MT5LINUX_HOST=<node2-tailscale-ip>`, `MT5LINUX_PORT=18812` (already
  externalized in ADR-0011 — no code change needed).
- Node 2 should not expose the RPyC port beyond the Tailscale interface
  (bind to the Tailscale IP, not `0.0.0.0`) — the RPyC protocol itself has no
  built-in auth, so network-level isolation via Tailscale is the security
  boundary, same posture as this project's existing PostgreSQL binding
  (`127.0.0.1`-only, per `docs/vps/VPS_INVENTORY.md`).
- No public IP exposure required on Node 2 beyond what GCE assigns by default
  (firewall rules should restrict inbound to SSH + Tailscale only, mirroring
  Node 1's existing posture).

### Secrets

- `VANTAGE_MT5_DEMO_LOGIN`/`_PASSWORD`/`_SERVER` move to Node 2's `.env`
  (currently only needed by whichever host runs the MT5 terminal — after
  migration, that's Node 2, not Node 1).
- `METAAPI_TOKEN`/`VANTAGE_DEMO_METAAPI_ID` remain on Node 1 as the rollback
  path (ADR-0011) — do not remove until the mt5linux path is verified stable.
- No new secret-management system introduced — same `.env`-file convention
  as Node 1, per this project's existing pattern (CLAUDE.md §4: never commit
  secrets).

### Monitoring

- Node 2 needs its own basic health surface: Wine/MT5 terminal process alive,
  RPyC server responding, disk/memory headroom. A minimal version of
  `scripts/disk_report.py`'s pattern (or the script itself, since it's
  already generic) can run on Node 2 without modification.
- Node 1's existing `scripts/health_check.py`/`demo_health_check.py` already
  call through `MT5LinuxConnector`/`MT5Connector` — once pointed at Node 2,
  they transparently become the cross-node health check; no new health-check
  code is required.

### Backups

- Node 2 holds no unique data worth backing up on its own (Wine/MT5 terminal
  state is reconstructable from a fresh install + re-login) — no new backup
  target is created by this migration.
- Node 1's existing backup posture (`~/archives`, `~/db_backups`, per
  `docs/operations/backup-retention.md`) is unaffected.

## Deployment order

1. **Prepare new node** — provision a small GCE VM (Wine/MT5 doesn't need
   much CPU/RAM; a shared-core, 1-2G RAM instance is plausible per ADR-0012),
   join it to Tailscale, apply the same baseline hardening as Node 1
   (fail2ban, unattended-upgrades, chrony — matching `docs/vps/VPS_INVENTORY.md`'s
   existing baseline).
2. **Validate environment** — install Wine on the fresh node, run
   `wine cmd /c echo hello` as the first gate. If this fails identically to
   `auto-trade-vps`, the Wine investigation's root-cause question reopens
   (see `docs/audit/wine-investigation-report.md`'s recommendation that a
   clean base image "would not necessarily inherit whatever is causing this"
   — that assumption gets tested here, first, before anything else proceeds).
3. **Deploy MT5 gateway** — install the MT5 terminal, Wine-side Python, and
   the mt5linux server package on Node 2; log into the demo account; start
   the RPyC server bound to the Tailscale interface.
4. **Connect System2** — point Node 1's `MT5LinuxConnector` at Node 2 via
   `MT5LINUX_HOST`/`MT5LINUX_PORT`; run `scripts/health_check.py` /
   `scripts/demo_health_check.py` against the cross-node connection.
5. **Shadow testing** — per ADR-0011's original Phase 4 plan: run the
   mt5linux path read-only (prices, account info, positions) in parallel
   with the still-live MetaAPI path on Node 1, diff results, no order
   placement.
6. **Demo validation** — only after shadow parity holds, cut
   `run_st_a2_demo.py`'s live wiring over to the mt5linux/Node 2 path,
   keeping `DEMO_ONLY=true`/`LIVE_TRADING=false` unchanged throughout (per
   ADR-0011 — this migration changes connectivity only, never trading
   authorization).

## Rollback

- **Disable MT5 node**: stop the RPyC server / MT5 terminal on Node 2, or
  simply stop routing to it. Node 1's trading system, dashboard, and
  database are physically unaffected since none of them run on Node 2.
- **Return to previous execution mode**: revert `MT5LINUX_HOST`/`_PORT` (or
  the connector wiring in `run_st_a2_demo.py`) back to the MetaAPI path
  (`execution/mt5_connector.py`) — this is the same rollback ADR-0011 already
  defined, unchanged by the two-node topology.
- **Preserve data**: no trading data, risk state, or database content lives
  on Node 2 — a full rollback or Node 2 decommission has zero data-loss risk
  to Node 1's operational state.

## Gates before proceeding

Per the Phase 5 governance pattern (gate-and-stop, not gate-and-continue):
- **Step 2's Wine validation is itself a hard gate** — if a fresh node also
  fails `wine cmd /c echo hello`, do not proceed to Step 3; this would mean
  the Wine problem is not host-specific after all, and the whole premise of
  this migration plan needs re-examination before any further spend.
- Shadow parity (Step 5) is the gate before Step 6's cutover, unchanged from
  ADR-0011's original design.
