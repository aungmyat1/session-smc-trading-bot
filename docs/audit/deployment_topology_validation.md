# Deployment Topology Validation

Date: 2026-07-01
Status: Read-only audit finding
Scope: Phase 2 of the deployment-topology validation audit

## Prompt's assumed topology (input to this audit)

```
gcp-vm1 → SVOS (research/backtest/optimization/validation/registry/reports/research DB)
auto-trade-vps → Production (live trading engine/broker/execution/risk/dashboard/monitoring)
```

**Verdict: partially correct, and already documented — but not fully realized yet.** The
two-node split exists and is the *intended, authoritative* design, but it is mid-migration:
this host still carries research-adjacent state it isn't supposed to under the target design.

## What is actually running, verified directly on this host

```
$ hostname
auto-trade-vps.asia-southeast1-b.c.auto-489108.internal

$ systemctl list-units --type=service --all | grep -iE "smc|d2e3|demo|dashboard|reconcile"
  live-dashboard.service    loaded  active  running  Live trading dashboard service
  smc-demo-runner.service   loaded  active  running  SMC OB+FVG strategy demo runner

$ systemctl is-enabled d2e3.service reconcile-positions.timer d2e3-journal-sync.timer
not-found
not-found
not-found
```

- `live-dashboard.service` and `smc-demo-runner.service` are the only two units from
  `deploy/gcp-vm1/systemd/` actually installed and running on this box.
- `d2e3.service`, `d2e3-journal-sync.service/.timer`, and `reconcile-positions.service/.timer`
  exist as **files in the repo** under `deploy/gcp-vm1/systemd/` but are **not installed** as
  systemd units on this host (`not-found`, not merely inactive). Anything that assumes they run
  (e.g. the reconciliation job described in `docs/AUDIT_IMPLEMENTATION_PLAN_2026-07-01.md`
  P1.2) is not yet deployed here.
- No crontab entries exist for this user — nothing scheduled outside systemd.
- `smc-demo-runner.service` polls the Vantage MT5 **demo** account via MetaAPI every 60s
  (`LIVE_TRADING=false`, `DEMO_ONLY=true` enforced via the unit's env file); orders are paper
  money only.

## Directory name vs. host identity — confirmed mismatch, but it's a known/authoritative one

The deploy directory on **this** host (`auto-trade-vps`) is named `deploy/gcp-vm1/`. Taken at
face value this looks like a misconfiguration (production configs living under a name that
belongs to the other node). However, `docs/svos/DEPLOYMENT_TOPOLOGY.md` (dated 2026-06-29,
status: Authoritative) defines the intended roles explicitly:

| Node | Role | Permitted | Prohibited |
|---|---|---|---|
| VPS 1 (`auto-trade-vps`) — **this host** | Control, development, downstream execution | source dev, dashboard/API during migration, package verification, Vantage demo worker, execution monitoring | bulk research builds, authoritative research database, qualification from local YAML |
| VPS 2 (`gcp-vm1`) | Strategy engineering research plane | PostgreSQL, market data, replay, backtest, robustness, Virtual Demo, evidence/report generation | broker credentials, Vantage order submission, live-trading enablement |

So `gcp-vm1` is the *name of the other, separate machine* — this repo's `deploy/gcp-vm1/`
directory name is misleading only in that it collides with that other node's name while
actually containing **this** host's (VPS 1's) execution unit files. This is a naming footgun,
not evidence that production and research are undeployed/unseparated. No independent
"auto-trade-vps"-named deploy directory exists in the repo; VPS 1's units simply live under the
confusingly-named `deploy/gcp-vm1/` path.

## SVOS / research side (per `docs/svos/DEPLOYMENT_TOPOLOGY.md` and `PREFLIGHT_STATUS.md`, both 2026-06-29)

- VPS 2 (the actual `gcp-vm1` machine) is online over Tailscale; Docker + PostgreSQL 16
  (`quant-postgres`) are healthy there.
- `/srv/svos/{data,artifacts,backups,manifests,runtime}` canonical layout has been created on
  VPS 2.
- **Not yet done:** dedicated SVOS Postgres roles/database on VPS 2, restricted Postgres
  network exposure (currently published on all interfaces — flagged as a security finding in
  the topology doc itself), and the checksummed dataset cutover from VPS 1 to VPS 2.
- SVOS services are **not deployed as systemd units anywhere** — they run ad hoc via scripts
  (`run_pipeline.py`, backtest/replay scripts), consistent with Phase 1's finding that
  `svos/`, `research/`, etc. have no corresponding entries in `deploy/gcp-vm1/systemd/`.

## Production database still lives on VPS 1, contrary to the target topology

`.env`'s `DATABASE_URL` points to `postgresql+asyncpg://trading:...@127.0.0.1:5432/vmassit` —
a **loopback** address. `db/control_plane.py` (the Postgres control plane used by both
execution governance and research writes, per `database_topology.md`) is therefore currently
connecting to a **local** Postgres instance on VPS 1, not VPS 2. `DEPLOYMENT_TOPOLOGY.md`
explicitly prohibits "authoritative research database" on VPS 1 and confirms in its §2
inventory that "PostgreSQL 16 is active locally" on VPS 1 today. `PREFLIGHT_STATUS.md`'s "Next
safe actions" (provision dedicated SVOS Postgres roles/DB on VPS 2, complete the checksummed
data copy) confirm this cutover has not happened yet. **This is the single largest live gap
between the target topology and current reality** — see `architecture_gap_report.md`.

## Confirm/reject table

| Component | Expected | Actual | Status | Evidence |
|---|---|---|---|---|
| Live trading demo execution | `auto-trade-vps` | `auto-trade-vps` (this host) | PASS | `smc-demo-runner.service` active, `hostname` output |
| Live dashboard | `auto-trade-vps` | `auto-trade-vps` (this host) | PASS | `live-dashboard.service` active |
| Replay / backtest / optimization engine | `gcp-vm1` | ad hoc, invoked manually — infra staged on VPS 2 but no scheduled/systemd execution anywhere | PARTIAL | No `svos`/`research` systemd units on either host; `PREFLIGHT_STATUS.md` |
| Research/strategy registry (Postgres) | `gcp-vm1` | **VPS 1, loopback** (`127.0.0.1:5432/vmassit`) | FAIL (in-progress migration) | `.env` DATABASE_URL, `DEPLOYMENT_TOPOLOGY.md` §2 |
| Production DB / execution state | `auto-trade-vps` | Same Postgres instance as above, on VPS 1 | PASS (co-located, not yet split) | same |
| Broker credentials confined to VPS 1 | Prohibited on VPS 2 | Explicitly removed from VPS 2 per `PREFLIGHT_STATUS.md` (INC-20260629-LIVE-CONFIG-DRIFT) | PASS | `PREFLIGHT_STATUS.md` "Completed" section |
| Reconciliation job (`reconcile-positions`) | Running per audit plan P1.2 | Unit files present, **not installed** | FAIL | `systemctl is-enabled` → not-found |
| D2E3 alternate strategy service | Optional | Unit files present, **not installed** | N/A (intentionally disabled) | `systemctl is-enabled` → not-found |

## Summary

- **Production runs on `auto-trade-vps`** (this host), demo-only, as designed.
- **SVOS is designed to run on `gcp-vm1`** (a separate, verified-online machine) per an
  authoritative 2026-06-29 topology doc — this is real infrastructure, not aspirational, but
  the migration onto it is incomplete.
- **The one substantive violation of the target topology today:** the authoritative Postgres
  database (shared by execution governance and research) still runs locally on VPS 1 instead
  of on VPS 2, and full replay/backtest/robustness runs are documented as blocked on VPS 2
  until it has enough RAM (currently 955 MiB, 8 GB minimum required per the capacity gate in
  `DEPLOYMENT_TOPOLOGY.md` §6).
- The `deploy/gcp-vm1/` directory name is confusing (it holds VPS 1's own unit files) but is
  not itself evidence of a topology defect.
