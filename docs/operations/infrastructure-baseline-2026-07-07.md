# Infrastructure Baseline Snapshot — 2026-07-07 (post-disk-expansion)

Date: 2026-07-07
Purpose: known-stable checkpoint for Phase 5B, taken after the disk expansion
(`docs/operations/disk-expansion-2026-07-07.md`) and before any MT5 execution
architecture decision is implemented.
Related: `docs/vps/OPERATIONS_BASELINE.md` (2026-07-04, pre-expansion baseline —
not superseded, this is a new checkpoint at a later point in time),
`docs/svos/ADR-0014-BROKER-CONNECTIVITY-TECHNOLOGY.md`

## Repository

| Item | Value |
|---|---|
| Branch | `codex/demo-smoke-test` |
| HEAD commit | `ce0396797701157541a3b272d16f2be7cbf8c2ce` — "refactor(system2): decouple execution from SVOS, add approved package contract" |
| Working tree | 79 modified/untracked paths (uncommitted — includes this session's docs plus other in-progress workstreams noted in prior sessions: Storage Audit, Risk Portfolio migrations, Dashboard work) |
| Uncommitted, unrelated to this session | `db/migrations/versions/005_risk_portfolio_state.py`, `006_validation_session.py`, dashboard components — pre-existing WIP from other sessions, not touched here |

## Host resources

| Resource | Value |
|---|---|
| Disk | 48G filesystem, 33G used, 15G free, **69% used** |
| Memory | 3.8Gi total, 1.9Gi used, 1.2Gi free, 1.9Gi available |
| Swap | 4.0Gi total, 1.3Gi used, 2.7Gi free |
| CPU | 2 vCPU |
| Load average | 0.24 / 0.20 / 0.14 (1/5/15 min) — low |
| Uptime | 2 days, 7:34 |

## Services

| Service | Status |
|---|---|
| `smc-demo-runner.service` | `active` |
| `live-dashboard.service` | `active` |
| `postgresql@16-main.service` | `active` |
| `tailscaled.service` | `active` |
| `ssh.service` | `active` |
| `fail2ban.service` | `active` |

## Ports / processes

| Port | Bind | Process |
|---|---|---|
| 22 | `0.0.0.0`, `[::]` | sshd |
| 5432 | `127.0.0.1` (loopback-only — correct, per prior audits) | PostgreSQL 16 |
| 8090 | `0.0.0.0` | dashboard (`uvicorn dashboard.status_server:app`, PID 302185) |

Trading process: `scripts/run_strategy_demo.py --strategy ST-A2 --mode demo
--interval 60`, PID 345510 — **same PID observed across every check since
the disk expansion**, confirming zero interruption to date.

## Application health

- PostgreSQL: `pg_isready` → accepting connections.
- Dashboard: `GET /api/status` → `200`.

## Known existing MT5/broker integration files (for reference, unchanged)

`execution/metaapi_client.py` (live), `execution/mt5_connector.py` (live,
MetaAPI-backed), `execution/mt5_executor.py` (superseded duplicate, not
in use), `execution/mt5linux_connector.py` (ADR-0011, built but not
provisioned — paused per ADR-0014).

## Checkpoint statement

This snapshot represents a stable, healthy state as of 2026-07-07, taken
specifically so that any future MT5 execution architecture change (whichever
option is eventually implemented) has a known-good reference point to
compare against or roll back to.
