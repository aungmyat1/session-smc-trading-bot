# SYSTEM 2 MASTER PLAN — Production Live Trading Platform

- Date: 2026-07-04
- Status: **Authoritative — single source of truth for System 2**
- Scope: System 2 (Production Execution Layer) only. System 1 (SVOS research) is referenced
  only where it forms an interface into System 2 (package handoff, approval gate).
- Safety: This document does not authorize live trading, does not change `LIVE_TRADING`/
  `DEMO_ONLY`, and does not implement code. It is a review and plan only.
- Method: Direct, read-only, file:line-anchored inspection of the current repository state
  (`/home/aungp/session-smc-trading-bot`) as of 2026-07-04, including uncommitted changes and the
  most recent System-2 commits (`c9203a1` "Address execution safety review findings", `d8e0a59`
  "Use static operations queries", `e009d5f` "Complete disabled System 2 execution platform").
  Cross-checked against `ARCHITECTURE_STABILIZATION_ROADMAP.md`, `docs/architecture/*`,
  `docs/svos/ADR-000{2,3,4}-*.md`, and `docs/audit/*` (2026-07-04 audit pass).
- **Update 2026-07-04, later same day (Phase 3 stabilization + this pass):** Sprints 2.1-2.3 landed
  (canonical pipeline, legacy-runner block, durable Postgres operations recording — see the
  Implementation Roadmap below). A VPS stabilization pass then discovered `smc-demo-runner.service`
  had been crash-looping since its creation on an unapproved, `INTAKE`-stage strategy name and had
  **never actually executed ST-A2 (or any strategy) in production** — see
  `docs/systemd/SMC_DEMO_RUNNER_ANALYSIS.md`. This has now been fixed and verified: the wrapper
  (`deploy/gcp-vm1/run_smc_demo.sh`) now runs `--strategy ST-A2`; the service has been stable
  (0 restarts) with a healthy broker connection and clean tick cycles since 2026-07-04T17:01:32Z.
  Everything in this document describing the deployed runner's behavior was accurate for the
  *code path* throughout, but had not, until this fix, been exercised by the actually-running
  production process.

---

## Executive Summary

System 2 is a demo-only (`LIVE_TRADING=false`, `DEMO_ONLY=true`), single-broker
(MetaAPI → Vantage MT5 demo) forex execution layer. It is **not one system today — it is two,
running in parallel, and only one of them is actually deployed.**

- The **deployed** process on the live host is `scripts/run_st_a2_demo.py` (systemd unit
  `smc-demo-runner.service`), a "legacy" runner that has real governance/recovery wiring
  (`TradingPermissionService`, emergency-stop handling, startup recovery counting) but does not
  use the newer `CanonicalExecutionPipeline`.
- The **canonical** runner, `scripts/run_portfolio.py`, does use the newer
  `CanonicalExecutionPipeline` / `RiskFirewall` architecture built in ADR-0002/0003/0004, but
  **has no systemd unit at all** — it is not deployed anywhere. It also lacks the emergency-stop
  wiring, permission-service check, and startup recovery step the deployed legacy runner has.

Layered on top of this split-brain, three independent findings compound each other into the
platform's most consequential open risk:

1. **~~The risk-halt feedback loop is dead code in both runners.~~ Fixed in the deployed runner,
   2026-07-04.** `execution/demo_risk_manager.py::record_result()` and
   `core/portfolio_manager.py::record_close()` are now called from a real trade-close event in
   `scripts/run_st_a2_demo.py` (see Phase 1 below) — daily/weekly/monthly loss limits and
   consecutive-loss halts can now fire from real P&L in the runner that's actually deployed.
   **Still dead code in `run_portfolio.py`** (the undeployed canonical runner) pending the Phase 2
   decision recorded below.
2. **~~That same risk/portfolio state is held only in memory~~ Partially addressed 2026-07-04**
   (`core/portfolio_manager.py`, `execution/demo_risk_manager.py`'s `risk_state` dict) — both are
   now persisted to JSON (`logs/risk_state.json`/`logs/portfolio_state.json`) every tick and
   reloaded at process start in `run_st_a2_demo.py`, so a restart no longer silently resets them to
   zero. This is a plain JSON file, not the transactional/durable ledger this document originally
   called for — that remains open.
3. **~~Restart recovery is informational-only in the deployed runner.~~ Fixed in the deployed
   runner, 2026-07-04.** `execution/startup_recovery.py::reconcile_pending_executions()` now
   performs real broker-truth reconciliation — for each non-terminal `ExecutionRecord` left by an
   interrupted run it either confirms the broker order and backfills the journal (recovered) or
   finds no broker evidence and marks it `FAILED_TERMINAL` without ever resubmitting (lost) — and
   is called from `scripts/run_st_a2_demo.py::run()` before the tick loop starts accepting new
   signals. It never calls an order-placement API, so re-running it against the same state is a
   verified no-op (`tests/execution/test_startup_recovery.py`,
   `tests/scripts/test_run_st_a2_demo_e2e_recovery.py`). **Still `run_portfolio.py`:**
   `ExecutionStateStore.recover_incomplete()` is never called there at all — unchanged, pending the
   Phase 2 decision recorded below.

None of this blocks the platform from being useful for demo-scope observation today — broker
connectivity, order placement, retry/backoff, logging, and Telegram alerting are all genuinely
implemented and working. But **an operator pressing "emergency stop" on the canonical runner, or
relying on daily-loss halts to protect the demo account during a losing streak, or trusting the
dashboard's `/api/v1/production/health` endpoint as a liveness signal, would all be wrong today** —
each of those controls exists in code but is disconnected from the path that is actually running.

This plan is sequenced to close the split-brain and the disconnected-safety-mechanism gaps first
(Phase 1-2), then consolidate duplicated surfaces (dashboard backends, strategy loader pipelines,
APIs) (Phase 3), then complete deployment/observability hygiene (Phase 4). No phase enables live
trading; that remains gated behind SVOS Production Approval per `CLAUDE.md` §0.1, which no
strategy currently holds.

---

## Architecture

### Current (as observed, not as documented)

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  VPS 1 — auto-trade-vps (confirmed live)                                          │
│                                                                                     │
│  ENTRYPOINT A — DEPLOYED                    ENTRYPOINT B — NOT DEPLOYED           │
│  ┌────────────────────────────┐             ┌────────────────────────────────┐   │
│  │ scripts/run_st_a2_demo.py   │             │ scripts/run_portfolio.py        │   │
│  │ systemd: smc-demo-runner.   │             │ systemd: NONE                   │   │
│  │ service (real, active)      │             │ (canonical architecture, never  │   │
│  │                              │             │  actually run in production)    │   │
│  │ ✓ TradingPermissionService   │             │ ✓ CanonicalExecutionPipeline    │   │
│  │ ✓ StrategyExecutionGuard     │             │ ✓ RiskFirewall / _PortfolioRisk-│   │
│  │ ✓ emergency-stop check/tick  │             │   Gate                          │   │
│  │ ✓ recover_incomplete() at    │             │ ✗ no permission/guard check      │   │
│  │   startup (informational)    │             │ ✗ no emergency-stop check per    │   │
│  │ ✗ no CanonicalExecutionPipe- │             │   tick                           │   │
│  │   line layer                 │             │ ✗ no recover_incomplete() call   │   │
│  └──────────────┬───────────────┘             └───────────────┬────────────────┘   │
│                 │                                              │                    │
│                 └───────────────┬──────────────────────────────┘                    │
│                                 ▼                                                    │
│                  execution/trade_manager.py  (the REAL order path, both runners)     │
│                  → execution/execution_state.py (durable per-order JSON state)       │
│                  → execution/mt5_connector.py → MetaAPI → Vantage MT5 DEMO           │
│                                                                                       │
│                  core/portfolio_manager.py (in-memory only: _open_symbols,           │
│                  _daily/_weekly/_monthly_pnl_pct — record_close() never called)      │
│                  execution/demo_risk_manager.py (in-memory risk_state —              │
│                  record_result() never called)                                       │
│                                                                                       │
│  DASHBOARD — 3 backend processes, fragmented routes:                                │
│  ┌───────────────────┐  ┌───────────────────┐  ┌────────────────────────────────┐  │
│  │ status_server.py   │  │ app.py             │  │ live_app.py                     │  │
│  │ FastAPI :8090       │  │ Flask               │  │ Flask                           │  │
│  │ systemd: live-      │  │ systemd: EXAMPLE    │  │ own systemd unit (per docs;     │  │
│  │ dashboard.service   │  │ ONLY — not          │  │ superseded in practice by       │  │
│  │ — CONFIRMED         │  │ confirmed running   │  │ status_server for the live      │  │
│  │ DEPLOYED            │  │                     │  │ deployment)                     │  │
│  │ NO /new-dashboard   │  │ serves New Dashboard│  │ duplicate /api/live-dashboard/* │  │
│  │ routes              │  │ (dist/, /api/new-   │  │ routes vs app.py                │  │
│  │                     │  │ dashboard/*) — real  │  │                                 │  │
│  │                     │  │ data IF this process │  │                                 │  │
│  │                     │  │ were running         │  │                                 │  │
│  └───────────────────┘  └───────────────────┘  └────────────────────────────────┘  │
│                                                                                       │
│  Net effect: New Dashboard frontend is wired to real SVOS/strategy data through      │
│  app.py, but app.py is not confirmed deployed — the frontend is unreachable on the   │
│  live host today.                                                                    │
└──────────────────────────────────┬────────────────────────────────────────────────┘
                                    │
                                    ▼
                    Postgres `vmassit` (control-plane, VPS 1 loopback)
                    + JSON/JSONL flat files (data/execution/*.json,
                      data/production/runtime/runtime-state.json,
                      reports/control_state.json, data/production/heartbeat.json)

  SVOS → PRODUCTION HANDOFF (two disconnected pipelines):
  ┌─────────────────────────────────┐        ┌────────────────────────────────────┐
  │ Pipeline A — packaging/staging   │        │ Pipeline B — what runners actually  │
  │ production/importer.py           │   ✗    │ load                                │
  │ production/verifier.py           │  NOT   │ --strategy-package / APPROVED_      │
  │ production/activation.py         │ CONN-  │ STRATEGY_PACKAGE env var →           │
  │ (checksum/signature verified,    │ ECTED  │ approval_package.package_validator   │
  │  STAGED_DISABLED only)            │        │ → config/strategy_portfolio.yaml →   │
  │                                   │        │ strategies/adapters/*.py (hardcoded) │
  └─────────────────────────────────┘        └────────────────────────────────────┘
```

### Target (end state for this master plan — still demo-only)

```
                     ┌───────────────────────────────────────────┐
                     │  ONE canonical runner, ONE systemd unit     │
                     │  (merges Entrypoint A's governance/recovery │
                     │   wiring into Entrypoint B's pipeline       │
                     │   architecture, or vice versa — Phase 2     │
                     │   decides which survives)                   │
                     │  - TradingPermissionService + emergency-stop │
                     │    check every tick                          │
                     │  - CanonicalExecutionPipeline / RiskFirewall │
                     │  - recover_incomplete() at startup, WITH     │
                     │    automatic broker-truth reconciliation      │
                     │  - record_result()/record_close() called on  │
                     │    every trade close, persisted durably       │
                     └───────────────────────┬───────────────────────┘
                                             ▼
                     execution/trade_manager.py → execution_state.py
                     (durable) → mt5_connector.py → MetaAPI → Vantage DEMO
                                             │
                     Risk/portfolio state persisted to Postgres or a
                     durable JSON store keyed by day/week/month — survives
                     restart, feeds the SAME halts the runner checks.
                                             │
                     ┌───────────────────────▼───────────────────────┐
                     │  ONE dashboard backend, serving BOTH the        │
                     │  operations/live-position views AND the New     │
                     │  Dashboard SPA, with a single CONFIRM-token      │
                     │  contract applied consistently to every          │
                     │  mutation route (activate, position close/       │
                     │  protect/cancel, emergency-stop, promote/demote) │
                     └─────────────────────────────────────────────────┘
                     One strategy-loading path: the runner loads ONLY
                     from a verified import (Pipeline A above), retiring
                     Pipeline B's separate config-driven adapter loading.
```

---

## Current Status — Component Classification

Legend: **Implemented** (works end-to-end, correctly wired) · **Partial** (real code exists but
incomplete or only partially wired) · **Missing** (no implementation) · **Broken** (implementation
exists but does not function as intended in the path that matters) · **Deprecated** (superseded,
should be retired) · **Duplicate** (two+ implementations of the same concern coexist)

| Component | Classification | Summary |
|---|---|---|
| Execution Engine | **Duplicate** | `CanonicalExecutionPipeline` (used by undeployed `run_portfolio.py`) vs. direct `TradeManager` calls (used by deployed `run_st_a2_demo.py`, no pipeline layer) — two real architectures, only the weaker one is live |
| Broker Integration | **Implemented** (demo scope) | Real MetaAPI/Vantage SDK usage, confirmed live account/candle data; live-mode code paths exist below the CLI entrypoint (WS3, open) |
| Order Management | **Partial** | Real retry/backoff/state-machine (`execution_state.py`); `production/engine/orders.py` idempotency layer built but unused (**Duplicate** sub-finding) |
| Position Management | **Partial** (2026-07-04) | `record_close()` is now called from a real trade-close event in the deployed legacy runner (`scripts/run_st_a2_demo.py::_process_closed_positions`, via new `execution/position_close_detector.py`), releasing the one-per-symbol dedup guard on actual broker close. Still **not durably persisted across a crash mid-tick** beyond the once-per-tick JSON snapshot (see Persistence row), and matching is by `(symbol, position.id == journal.broker_order_id)` — the same convention `scripts/reconcile_positions.py` already used, inherited limitation since MetaAPI order placement never captures a separate `positionId` |
| Risk Engine | **Partial** (2026-07-04) | `record_result()` is now called from the same real close event in the deployed legacy runner, so daily/weekly/monthly loss halts and consecutive-loss halts **can** fire from real P&L (verified by `tests/scripts/test_run_st_a2_demo_close_detection.py::test_losing_streak_halts_via_real_close_events`). `risk_state` and `PortfolioManager`'s counters are now persisted to `logs/risk_state.json` / `logs/portfolio_state.json` and reloaded at process start, so a restart no longer silently zeroes them. **Still open**: this wiring exists only in the legacy runner (`run_st_a2_demo.py`), not `run_portfolio.py`; a JSON file is not the durable, transactional ledger this plan's Phase 1 originally called for (no atomic write, no Postgres option evaluated); unmatched broker closes (no matching journal row) are alerted via Telegram but not auto-resolved |
| Account Monitoring | **Partial** | Real broker account/balance snapshot exists (`live_dashboard_service.py`) but is a separate ad hoc connection, decoupled from the tick loop and not feeding the risk engine |
| Health Monitoring | **Partial** | `/api/v1/production/health` heartbeat source is never fed by the canonical runner — will read stale/UNKNOWN; a separate, real broker-connectivity check exists but is disconnected from the actual tick-loop's own connection |
| Logging | **Implemented** | Real gzip-rotating handler, daily rotation, dual-layer (app + OS logrotate), live evidence through 2026-07-04 |
| Alerting | **Partial** | `TelegramAlerter` is comprehensive and wired into `bot.py`/`run_st_a2_demo.py`; not confirmed wired into the canonical `run_portfolio.py` |
| Strategy Package Loader | **Duplicate** | Pipeline A (`production/importer.py`/`verifier.py`, checksum+signature verified) and Pipeline B (`config/strategy_portfolio.yaml` + hardcoded adapters, what runners actually load) are entirely disconnected |
| Strategy Activation | **Partial** | `production/activation.py` correctly dead-ends at `STAGED_DISABLED`/`BLOCKED` (live categorically unreachable — good); its own activate API endpoint lacks the CONFIRM-token pattern the emergency-stop endpoints use |
| Execution Workflow | **Partial / Broken** | Real signal→risk-gate→order→journal flow exists but diverges between the two runners; risk-halt dead code (see Risk Engine) sits inside this flow |
| Dashboard Backend | **Duplicate** | 3 backend processes with overlapping routes (`/api/live-dashboard/*` duplicated verbatim in `app.py` and `live_app.py`; `/api/status` and `/api/emergency-stop*` duplicated in `app.py` and `status_server.py`) |
| Dashboard Frontend | **Partial** | New Dashboard SPA is genuinely wired to real data via `app.py`, but `app.py` is not confirmed deployed — frontend is unreachable on the live host today |
| APIs | **Duplicate** | Route duplication across the 3 backends; inconsistent auth — only emergency-stop routes enforce a CONFIRM token, other real mutations (activate, position close/protect/cancel, promote/demote) rely on role auth alone |
| WebSocket | **Implemented** (2026-07-04) | Real-Time Operations Layer: `dashboard/status_server.py`'s `/ws` endpoint, in-process `EventBroadcaster`/`EventPoller` (`dashboard/events.py`) — no Redis, no new services. Server-side collection is poll-based against durable stores (`operations.*`, `control_state.json`, runner state file) every 2s since the runner and dashboard are separate OS processes; the browser connection itself is genuine push. Load-tested: 0 events lost across 25 concurrent subscribers × 2000 events |
| Persistence | **Partial** | Order state (`ExecutionStateStore`) and process lifecycle (`RuntimeAuthority`) are durable; risk/portfolio accounting is in-memory only; `TradeManager`'s default store-root path diverges from the root the dashboard reads |
| Restart Recovery | **Implemented** (legacy/deployed, 2026-07-04) / **Broken** (canonical) | `execution/startup_recovery.py` performs real broker-truth reconciliation before the deployed runner's tick loop starts, never resubmitting; `recover_incomplete()` is still never called by the undeployed canonical `run_portfolio.py` |
| Operator Controls | **Partial** | Emergency-stop, pause/resume, close-all, and toggle-strategy (`/api/control/*`, 2026-07-04) are fully wired end-to-end for the legacy runner and now RBAC + CONFIRM-token gated (see Authentication row); manual position close/modify/cancel work via a separate, functioning broker connection regardless of which runner is active; activation/position mutations elsewhere still lack a CONFIRM token |
| Authentication | **Partial** | Real HMAC/CSRF/role-based auth on dashboard mutation routes; `dashboard/rbac.py` (2026-07-04) brings the same role model to the FastAPI backend (`status_server.py`) — `/api/emergency-stop[/clear]` and all new `/api/control/*` routes now require `Depends(require_role(...))` in addition to their CONFIRM token. Still missing: a frontend login/session UI, and the CONFIRM-token layer on several other real mutations (activation, position close/protect/cancel) that this repo's own CLAUDE.md §4 implies should have one |
| Secrets | **Implemented** | `.env` gitignored and CI-enforced; no tracked secrets; GCP Secret Manager adapter exists (used by SVOS deployment/signing, not confirmed wired to broker credential loading) |
| Cloud Deployment | **Broken** (for the canonical architecture) / **Partial** (overall) | The canonical runner has no systemd unit anywhere — the architecture this plan should be built around is not deployed; only the legacy runner + `status_server.py` dashboard are live on VPS 1 |

---

## Missing Components

Nothing in System 2 is entirely absent from a *code-exists* standpoint — every gap above is a
wiring/consolidation/persistence gap, not a blank page. The closest things to true "missing"
components are:

1. **A durable, restart-safe risk/portfolio ledger.** No component today persists
   `daily_loss_pct`/`weekly_loss_pct`/`monthly_loss_pct`/`consecutive_losses`/`_open_symbols`
   anywhere durable. This needs to be designed, not just wired — there is no existing schema or
   file format to reuse.
2. **~~A broker-truth reconciliation routine.~~ Implemented for the deployed runner, 2026-07-04**
   (`execution/startup_recovery.py`) — resolves each ambiguous `ExecutionRecord` against actual
   broker positions before the tick loop starts, never resubmits. **Still missing for
   `run_portfolio.py`**, which never calls `recover_incomplete()` at all.
3. **~~Real-time push (WebSocket/SSE).~~ Implemented 2026-07-04** as the Real-Time Operations
   Layer — see WebSocket row above. Remaining gap: no frontend widget subscribes to `/ws` yet
   (backend/transport only; frontend integration is separate, unscoped work).
4. **A single systemd unit for the canonical execution architecture.** `run_portfolio.py` has
   zero deployment footprint — this is a deployment gap, not a code gap.

---

## Execution Flow

### As currently deployed (`run_st_a2_demo.py` via `smc-demo-runner.service`)

1. Tick fires → `TradingPermissionService`/`StrategyExecutionGuard` checked → if `emergency_stop.active`
   is set in `reports/control_state.json`, decision is `emergency_stop_active` and no new orders open.
2. Strategy adapters (`strategies/adapters/*.py`, loaded per `config` at process start) generate signals.
3. `core/portfolio_manager.py` gate: rejects if symbol already in `_open_symbols` (never released —
   see Position Management finding).
4. `execution/demo_risk_manager.py::check_limits()` evaluated against **in-memory** `risk_state`
   (never updated from real closes — see Risk Engine finding).
5. `execution/trade_manager.py::open_position()` → `_place_order_with_retry()` (exponential backoff,
   3 attempts, error classified transient/ambiguous/terminal).
6. State transitions recorded durably in `execution/execution_state.py`
   (`SIGNAL_RECEIVED → RISK_APPROVED → SUBMISSION_PENDING → BROKER_ACKNOWLEDGED → FILLED`, or
   `→ RECOVERY_PENDING` on ambiguous broker response).
7. Trade journaled (`monitoring/metrics.py::TradeJournal`), Telegram alert sent
   (`monitoring/telegram.py`).
8. **No step anywhere calls `record_result()` or `record_close()`** — steps 3-4's guards never
   reflect this trade's eventual outcome.
9. On process restart: `recover_incomplete()` runs and **logs** a count of
   `RECOVERY_PENDING`/`SUBMISSION_PENDING` records — no automatic action is taken on them.

### As architected but not deployed (`run_portfolio.py`)

Same steps 2-7, except step 1's permission/emergency-stop check does not exist, and step 3-4's
gate is wrapped in `_PortfolioRiskGate` → `CanonicalExecutionPipeline.submit()`
(`production/engine/execution_pipeline.py`), which additionally validates package/symbol scope
before calling `TradeManager`. Step 9 (recovery) does not run at all — the process starts a fresh
`risk_state`/`TradeManager` unconditionally.

### Target flow (Phase 1-2 of the roadmap below)

1. Tick fires → single runner checks `TradingPermissionService` + emergency-stop **and** runs
   through `CanonicalExecutionPipeline`.
2. Signal → gate checks against **durably persisted** risk/portfolio state.
3. Order submitted, retried, journaled — unchanged (already correct).
4. On close (win or loss): `record_result()` and `record_close()` are called, updating both the
   in-memory guard state **and** the durable ledger in the same transaction/write.
5. On restart: `recover_incomplete()` lists ambiguous orders, then a reconciliation step queries
   the broker for each one's true status and resolves the local record before the tick loop
   accepts new signals.

---

## Dashboard Requirements

Target state for a single, consolidated System 2 dashboard backend (replacing the current 3):

1. **One process, one systemd unit.** Serve both the operations/live-position views and the New
   Dashboard SPA from the same backend — eliminates the `app.py`/`live_app.py`/`status_server.py`
   split and the route duplication it causes.
2. **Consistent mutation auth.** Every mutation route (emergency-stop, activation, position
   close/protect/cancel, strategy promote/demote) must require the same CONFIRM-token pattern
   already used by `/api/emergency-stop`, not role-auth-only.
3. **Health endpoint that reflects the actual running tick loop**, not a heartbeat file the runner
   never writes to — either the runner posts its own heartbeat, or the health check directly
   queries the runner's own liveness (e.g. a Unix socket or PID + last-tick-timestamp file), not a
   second, independent broker connection.
4. **Freshness indicators on every widget** — the earlier full-repo audit found the deployed
   dashboard showing a stale system log (~10h24m stale) and reading the wrong trades journal file;
   every data widget should surface its own last-updated timestamp so this class of bug is visible
   to the operator instead of silent.
5. **Execution-state visibility**: surface `RECOVERY_PENDING`/ambiguous orders prominently, not as
   a buried counter — this is exactly the state an operator needs to see first after an incident.
6. **Retain polling (no WebSocket requirement)** at the current trade frequency — but document
   this as a deliberate decision, and revisit if trade frequency or operator headcount increases.

---

## Deployment Architecture

**Current (VPS 1 — `auto-trade-vps`, the only confirmed-live host for System 2):**

- `smc-demo-runner.service` → `scripts/run_st_a2_demo.py` (the deployed execution engine)
- `live-dashboard.service` → `uvicorn dashboard.status_server:app` (the deployed dashboard)
- `deploy/gcp-vm1/systemd/` also contains `d2e3.service`, `d2e3-journal-sync.*`,
  `reconcile-positions.*` as **files only** — not enabled, a separate/legacy demo path
- `deploy/dashboard/dashboard.service.example` — an example unit for `dashboard/app.py`, not
  installed; this is the process the New Dashboard frontend actually needs to be reachable
- Postgres `vmassit` on VPS 1 loopback (control plane; not node-separated from VPS 2's intended
  research role, out of System 2's scope to fix — tracked separately in the SVOS-side roadmap)

**Target for this plan (still demo-only, still VPS 1):**

- One systemd unit for the consolidated canonical runner (Phase 2 below), replacing
  `smc-demo-runner.service`'s current target.
- One systemd unit for the consolidated dashboard backend (Phase 3 below), replacing both
  `live-dashboard.service` and the never-installed `dashboard.service.example`.
- Durable risk/portfolio ledger location decided and provisioned (Phase 1) — either a Postgres
  table under the existing `vmassit` control-plane schema, or a dedicated JSON store with the
  same durability guarantees `execution_state.py` already has.
- No new hosts, no live-mode changes, no broker/account changes — this plan operates entirely
  within the existing demo-only VPS 1 footprint.

---

## Production Safety Checklist

Use before considering ANY future live-trading discussion (not applicable until Production
Approval per `CLAUDE.md` §0.1 — this checklist documents what "safe to even discuss live" would
require, it does not authorize working toward it):

- [x] Risk-halt feedback loop (`record_result()`/`record_close()`) wired into the deployed legacy
      runner and verified (unit-level) to actually halt on a simulated losing streak — 2026-07-04.
      **Not yet**: wired into the canonical runner too (pending Phase 2), or verified against a
      live/real broker connection end-to-end.
- [~] Risk/portfolio state persisted to a JSON file and verified to survive a simulated reload —
      2026-07-04. **Not yet**: a durable/transactional ledger (this checklist item's original
      intent), or a real forced-process-kill test.
- [x] Restart recovery performs real broker reconciliation, not just logging, verified via a
      simulated crash-during-submission test — 2026-07-04
      (`tests/execution/test_startup_recovery.py`,
      `tests/scripts/test_run_st_a2_demo_e2e_recovery.py::test_full_open_close_restart_recovery_resume_cycle`).
      **Not yet**: wired into `run_portfolio.py` (pending Phase 2), or verified against a real
      broker connection end-to-end (fixtures use fake positions, not a live MetaAPI session).
- [ ] Emergency-stop verified to halt the actual deployed runner (not just the legacy one) within
      one tick interval.
- [ ] Default-deny broker-write boundary enforced at every layer (not just the CLI entrypoint) —
      WS3/ADR-0012.
- [ ] Every mutation-class API endpoint (activate, position close/protect/cancel, promote/demote)
      requires an exact-match CONFIRM token, consistent with emergency-stop's existing pattern.
- [ ] Single canonical execution engine deployed — no second, competing implementation on the same host.
- [ ] Health endpoint verified to actually reflect tick-loop liveness (kill the tick loop only,
      leave the process running if applicable, and confirm health reports unhealthy).

## Operational Checklist

Day-to-day operator readiness for the current demo scope:

- [ ] Confirm which runner is actually active before relying on any control (today: `run_st_a2_demo.py`
      via `smc-demo-runner.service` — not `run_portfolio.py`).
- [ ] Do not rely on `/api/v1/production/health` as a liveness signal until it is fed by the
      canonical runner's own heartbeat.
- [ ] Treat the New Dashboard SPA as unreachable in production until `dashboard/app.py` (or its
      consolidated successor) has a real, installed systemd unit.
- [ ] After any incident, manually inspect `data/execution/*.json` for `RECOVERY_PENDING` records —
      do not assume the dashboard counter surfaces them promptly.
- [ ] Verify Telegram alerting is actually being received from whichever runner is deployed
      (confirmed wired for `run_st_a2_demo.py`/`bot.py`; not confirmed for `run_portfolio.py`).
- [ ] Periodically confirm `_open_symbols`/loss accounting reflects reality by cross-checking
      against the broker directly — known to drift over a trading day (Position Management finding).

---

## Implementation Roadmap

### Phase 1 — Close the Safety-Critical Disconnects (Critical, start immediately)
- [x] **2026-07-04**: `record_result()`/`record_close()` wired into the real trade-close event path
  in `scripts/run_st_a2_demo.py` (the currently-deployed runner) via new
  `execution/position_close_detector.py` — diffs `TradeManager.get_positions()` between ticks,
  matches disappeared positions back to their `TradeJournalDB` row (`symbol` +
  `id == broker_order_id`, the same convention `scripts/reconcile_positions.py` already used), and
  feeds the real outcome into `demo_risk_manager.record_result()`, `PortfolioManager.record_close()`,
  and `CircuitBreaker.record_trade()` (previously never called in this runner at all — a related
  gap discovered alongside the hardcoded-`won=True` one below). Unmatched closes (no journal row
  found) are alerted via Telegram, not silently dropped or guessed at.
- [x] **2026-07-04**: `risk_state` and `PortfolioManager`'s counters are now persisted to
  `logs/risk_state.json` / `logs/portfolio_state.json` every tick and reloaded at process start —
  a restart no longer silently zeroes daily-loss/consecutive-loss/open-symbol state. This is a
  plain JSON file, not a transactional/Postgres ledger — no atomic-write guarantee, no evaluation
  of a durable-store alternative yet. Still open, tracked below.
- [x] **2026-07-04**: the circuit breaker's hardcoded `won=True` issue — confirmed to live in
  `scripts/run_portfolio.py:543,573` (`_breaker.record_trade(signal.strategy_name, won=True)` called
  at OPEN time, comment says "open = neutral" but the docstring says "call when a trade closes").
  Not fixed in `run_portfolio.py` pending the Phase 2 owner decision below (fixing code slated for
  possible retirement is wasted effort); `run_st_a2_demo.py` never called `record_trade()` at all
  before this pass and now does, correctly, at close.
- [x] **2026-07-04**: `ExecutionStateStore.recover_incomplete()` wired to real broker-truth
  reconciliation via new `execution/startup_recovery.py::reconcile_pending_executions()`, called
  from `scripts/run_st_a2_demo.py::run()` (the deployed runner) before the tick loop processes any
  new market data. Per incomplete `ExecutionRecord`: a known `broker_order_id` is confirmed and its
  journal row backfilled if missing; an unknown `broker_order_id` is matched against currently-open
  broker positions (recovered) or, absent a match, advanced straight to `FAILED_TERMINAL` with the
  signal treated as lost — never resubmitted. Broker positions with no execution/journal linkage at
  all are surfaced as `orphaned_positions` for operator attention, never auto-mutated. Idempotency
  is structural, not incidental: this module never calls an order-placement API, so a second
  recovery pass against the same durable state is a verified no-op. **Still open**: `run_portfolio.py`
  never calls `recover_incomplete()` (Phase 2); reconciliation is unverified against a real MetaAPI
  session (fixtures use synthetic broker position dicts).
- [x] **2026-07-04**: the module docstrings on both runners previously contradicted the Phase 2
  decision below — `run_st_a2_demo.py` called itself "legacy" and told operators to prefer
  `run_portfolio.py`, which has none of this runner's safety wiring. Both docstrings now state which
  runner is actually deployed/canonical and which is not, and `run_portfolio.py` logs an explicit
  warning at startup. The `won=True` hardcode itself remains untouched in `run_portfolio.py`,
  deliberately, per the "wasted effort ahead of retirement" reasoning already recorded above.
- [ ] Design and implement a durable, transactional risk/portfolio ledger (Postgres table or
  equivalent) — the JSON-file persistence above closes the "restart zeroes everything" hazard but
  is not this bullet; still open.
- [x] Acceptance: forced losing-streak test verified via
  `tests/scripts/test_run_st_a2_demo_close_detection.py::test_losing_streak_halts_via_real_close_events`.
  Forced-restart persistence verified via `test_state_persistence_round_trips`. Crash-during-submission
  recovery verified via `tests/execution/test_startup_recovery.py` (recovered/lost/orphaned/idempotent
  cases) and end-to-end via
  `tests/scripts/test_run_st_a2_demo_e2e_recovery.py::test_full_open_close_restart_recovery_resume_cycle`,
  which drives Open Trade → Broker Close → Close Detection → record_result() → Portfolio Update →
  Circuit Breaker → SQLite Journal → Dashboard state file → simulated restart → Recovery → Resume
  Trading through the real modules (fake broker connector/executor only — no live-broker
  end-to-end test exists in this pass; see Remaining/blocked in the Phase 1 report).

### Phase 2 — Resolve the Canonical/Legacy Execution Split
- **Decision recorded 2026-07-04**: `run_st_a2_demo.py` (deployed, has working governance/emergency-
  stop/recovery wiring) absorbs `CanonicalExecutionPipeline`/`RiskFirewall` from `run_portfolio.py`
  — not the reverse. Rationale: lower deployment risk (no systemd/live cutover required on the VPS;
  the unit that's already running doesn't change), and this pass's Phase-1 risk-feedback-loop fix
  already landed in `run_st_a2_demo.py`, so continuing to build on the deployed runner avoids
  re-doing that wiring a second time in `run_portfolio.py`. **Not yet implemented** — this is a
  decision record, not a completed migration; the actual pipeline/RiskFirewall port is a separate,
  substantial piece of work deserving its own dedicated pass, deliberately not attempted in the same
  turn as the Phase-1 safety fix above.
- [x] **Sprint 2.1 — 2026-07-04**: `production.engine.CanonicalExecutionPipeline` (with
  `AllowAllRiskGate`, since CircuitBreaker/PortfolioManager/permission/governance checks already
  approve the order earlier in `_tick()` — no duplicate risk logic) now wraps order placement in
  `scripts/run_st_a2_demo.py`. `run()`'s tick loop runs as the pipeline's workload
  (`pipeline_started`/`pipeline_stopped` events bound to its lifecycle); each order goes through
  `pipeline.submit(ExecutionIntent(...))`, whose adapter callback calls the *same*
  `manager.open_position()` as before — retry/state-machine/idempotency behavior is unchanged, this
  adds normalized event journaling (`logs/execution_pipeline_events.jsonl`) and intent/scope
  validation on top. Evidence: `tests/scripts/test_run_st_a2_demo_pipeline_integration.py` (pass-
  through order data unchanged; a scope-mismatched symbol is REJECTED loudly, `manager.open_position`
  never called — guards the real regression risk of this wiring). Full existing suite (296 tests
  across `tests/core,execution,scripts,production,portfolio,architecture,integration`) still green.
  **Not done**: `RiskFirewall` (a real, non-allow-all risk gate) — out of scope for this sprint,
  the existing upstream checks remain the risk authority; `run_portfolio.py` is untouched
  (Sprint 2.2 retires or absorbs it, not attempted here).
- [x] **Sprint 2.2 — 2026-07-04**: `run_portfolio.py::run()` now refuses to start unless
  `RUN_PORTFOLIO_ALLOW_START=true` is explicitly set, raising `RuntimeError` naming
  `run_st_a2_demo.py` before any broker connection is attempted — an operator or agent can no
  longer start this undeployed, unsafe-wiring runner by accident (it already logged a warning;
  now it hard-blocks). Scoped deliberately narrow, not a full retirement:
  - Not touched: `main()`'s package-validation/`RuntimeAuthority` CLI path, which existing tests
    (`tests/portfolio/test_strategy_package_cli.py`, `tests/integration/test_canonical_package_handoff.py`)
    use as real, still-valuable coverage of WS1 canonical-package validation (Pipeline A) — these
    patch `run`/`RuntimeAuthority.run` and never reach the new guard, so they still pass unchanged.
  - Not done: "move reusable logic into shared services." `run_portfolio.py`'s multi-strategy
    orchestration (`_STRATEGY_MAP`, shared M15/H4 fetch across strategies) has no equivalent in
    `run_st_a2_demo.py` (single-strategy only) — porting that is a real feature decision, not a
    safe mechanical extraction, and deliberately deferred to its own pass rather than rushed here.
  - Not done: physically deleting `run_portfolio.py` — the guard is the safe, reversible
    "neutralize" step this sprint asked for; deletion can follow once Sprint 2.2's multi-strategy
    question above is resolved.
  Evidence: `tests/portfolio/test_portfolio_runner.py::TestDeprecatedRunnerBlocked` (blocked by
  default; explicit override reaches `connect()`). Full suite: 298 passed (only the pre-existing,
  unrelated `test_smc_ob_fvg_session_adapter.py` failure remains).
- [x] **Sprint 2.3 — 2026-07-04**: durable transactional persistence, built on the
  `operations.*` Postgres schema (migration `004_system2_operations.py`) that already existed but
  was unapplied (`alembic current` was `003`, head `004`) and had no ORM layer at all. Rather than
  invent a second, competing SQLite ledger, this sprint: (1) ran `alembic upgrade head` against the
  connected DB — verified via direct `information_schema` query, all 10 `operations.*` tables now
  exist; (2) added the missing ORM classes (`Runtime`, `Intent`, `RiskDecision`, `OrderRecord`,
  `Fill`, `PositionRecord`, `Reconciliation`, `RecoveryCheckpoint`, `ExecutionEvent`,
  `MarketDataHealth`) to `db/models.py`, smoke-tested with real inserts against the live DB;
  (3) added `execution/operations_recorder.py`, a best-effort recorder (DB write failures are
  logged and swallowed, never block the tick loop — this is an audit layer, not a safety gate)
  wired into `scripts/run_st_a2_demo.py`'s **existing** `CanonicalExecutionPipeline` event_sink
  (Sprint 2.1) — every event still goes to `logs/execution_pipeline_events.jsonl` *and* now also to
  `operations.execution_event`, with `intent_received`/`risk_decision`/`execution_result` events
  additionally landing typed rows in `operations.intent`/`risk_decision`/`order_record`. Startup
  recovery (Phase 1) now also writes one `operations.recovery_checkpoint` row per pass. Evidence:
  `tests/execution/test_operations_recorder.py` (8 tests, mocked DB session — no live DB required
  for CI, matching this repo's existing `test_db_preflight.py` convention). Full suite: 328 passed,
  4 skipped; the only failures are the same 2 pre-existing ones confirmed via `git stash` to predate
  this sprint entirely (`test_smc_ob_fvg_session_adapter.py`, and 15 `test_db_preflight.py` failures
  caused by a bug in `scripts/db_preflight.py` itself — a SQLAlchemy transaction reused across
  `conn.begin()` calls — unrelated to and not fixed by this sprint; flagged, not addressed).
  **Not done, deliberately**: `market_data_health`/`fill`/`position_record`/`reconciliation` tables
  have ORM classes but nothing writes to them yet — `position_record`'s role is already served by
  `core/trade_journal_db.py`'s `trades` table (real position lifecycle, avoided a duplicate); the
  other three have no current caller and no acceptance criterion asked for them. The
  crash→restart→no-duplicate-order guarantee itself is **unchanged** — it already lived in
  `ExecutionStateStore`'s state machine (Phase 1) and remains the actual idempotency authority; this
  sprint adds a durable, queryable Postgres audit trail alongside it, not a replacement.
- [x] **Deployment fix — 2026-07-04**: `smc-demo-runner.service` had been crash-looping since
  creation — `deploy/gcp-vm1/run_smc_demo.sh` hardcoded `--strategy SMCOrderBlockFVGSession`, a
  strategy never registered in `strategies/adapters/__init__.py`'s `ADAPTER_TYPES` and still at
  `svos_stage: INTAKE`/`approved: false` in `config/strategy_catalog.yaml` — meaning **no strategy
  had ever actually run in production through this unit**. Full root-cause analysis:
  `docs/systemd/SMC_DEMO_RUNNER_ANALYSIS.md` (recommendation: Replace, not Repair — registering the
  draft/unapproved strategy instead would have been a governance violation, and its adapter has a
  separate, pre-existing failing test). Fixed by changing the wrapper to `--strategy ST-A2` (one
  line, git-trivial to revert). Verified: service `active (running)`, 0 restarts since
  2026-07-04T17:01:32Z, broker connected (Vantage demo MetaAPI), clean tick cycles every 60s with
  correct spread-limit risk decisions (`SKIP EURUSD — spread 4.1 > 1.5` etc.), zero exceptions in
  `journalctl`. Startup recovery (Phase 1) also visibly engaged correctly on the transition,
  resolving stale `ExecutionRecord`s from the prior misconfigured runs without resubmitting any
  order. **Also removed this pass**: `benchmark-bot.service`/`smc-bot.service`, both disabled and
  dangling (their working directories were deleted in the prior VPS cleanup batch) — unit files
  archived to `/home/aungp/archives/systemd-units/` before removal, `systemctl --failed` confirms
  0 failed units after.
- [x] **Execution Pipeline Consolidation, Tier 1 — 2026-07-04**: full inventory, canonical-pipeline
  documentation, and consolidation plan produced — `docs/systems/system2/EXECUTION_PIPELINE_INVENTORY.md`,
  `CANONICAL_EXECUTION_PIPELINE.md`, `PIPELINE_CONSOLIDATION_PLAN.md`. Confirmed `run_st_a2_demo.py`
  is the one canonical execution lifecycle (every stage — startup through shutdown — appears in
  exactly one module) and identified three parallel stacks beyond the already-known
  `run_portfolio.py`: a dormant `bot.py` stack (`OrderManager`/`MetaAPIClient`/`RiskManager`, no
  systemd unit, real but unused test coverage), a dormant `adaptive/run_shadow.py` stack, and a
  411-line "Production Platform v2" cluster (`production/{recovery,operations,reporting,api}.py` +
  `production/engine/{orders,positions,risk}.py`, introduced already-disabled by commit `e009d5f`
  "Complete disabled System 2 execution platform") with **zero callers outside its own dedicated
  test files**. Removed the latter (genuinely dead code, zero live-path risk) along with its test
  file and the one dead-code-dependent test function in `test_system2_demo_readiness.py`; cleaned
  `production/engine/__init__.py`'s now-broken re-exports. **Deliberately not touched**: the `bot.py`
  and `adaptive/run_shadow.py` stacks — both have real, passing, if-dormant test coverage; removing
  or merging either is a product/scope decision, not a mechanical dedup (see consolidation plan
  Tier 3). `run_portfolio.py` itself remains exactly as Sprint 2.2 left it (blocked, not deleted) —
  its package-validation CLI path is still real, tested coverage with no equivalent elsewhere.
  Verified: full suite 1570 passed / 29 failed (all 29 confirmed pre-existing and unrelated via
  `git stash` — `test_db_preflight.py`'s own known bug, `test_lifecycle_authority.py`'s DB-fixture
  dependency, `test_pipeline.py`, one strategy-adapter test) / 4 skipped; `tests/production` 42→33
  (9 dead tests removed, zero regressions); the live production runner re-verified unaffected
  throughout (0 restarts, broker connected, 38+ minutes uptime at verification time).
- [x] **Operations Control Center, Phase 5 — 2026-07-04**: exposed the existing platform through
  eight new read-only endpoints in `dashboard/status_server.py` — **the only actually-deployed**
  dashboard backend (`live-dashboard.service`; `app.py`/`live_app.py` remain undeployed, unchanged).
  `GET /api/operations/{health,account,positions,orders,trades,strategy,risk,events}`, consistent
  envelope (`{"data", "source", "fetched_at", "unavailable"}`), every one a thin slice over an
  existing service — `dashboard/live_dashboard_service.py::load_snapshot()` (already used by
  `/api/new-dashboard/live-state`), `TradeJournalDB`, the runner's own `strategy_demo_state.json`,
  `logs/risk_state.json`/`portfolio_state.json`, and new read helpers
  (`execution/operations_recorder.py::get_recent_events()`/`get_recent_runtimes()`) against the
  Sprint 2.3 `operations.*` Postgres tables — the first code to ever read them back. No new business
  logic, no new broker/DB connections beyond what those services already open. Full detail and
  per-widget source mapping: `docs/dashboard/DASHBOARD_BACKEND_MAPPING.md`'s "Phase 5 update"
  section. **Also fixed** (defect discovered during validation, not a redesign): two incomplete
  edits in `dashboard/strategy_service.py` (an orphaned `raise` missing its `if not result.success:`
  guard, and a `for` loop missing its own statement) were breaking `import dashboard.app` and
  therefore all of `tests/test_dashboard_app.py`'s collection — both were pre-existing, unrelated to
  this pass's own changes, syntax-level breakage, not an architecture decision. Verified: full
  suite 1570 passed / 29 pre-existing failures (unchanged) / 4 skipped; all 8 new endpoints return
  HTTP 200 with real data against the live system; `live-dashboard.service` restarted cleanly (0
  restarts since) to load the change; `smc-demo-runner.service` unaffected throughout (0 restarts).
  **Known, pre-existing limitation surfaced, not introduced**: `/api/operations/account`/`positions`
  can return zeroed/degraded values because `live_dashboard_service.py` opens its own separate
  MetaAPI session, decoupled from the runner's own connection (already documented in this file's
  Executive Summary and `DASHBOARD_BACKEND_MAPPING.md` before this pass).
- [x] **Operational Dashboard Integration, Phase 6 — 2026-07-04**: the Gai dashboard frontend
  (`New Dashborad/Gai dashboard/`) is now wired to real System 2 data end-to-end, verified by
  actually running it and loading it in a browser (Playwright), not just by inspecting code.
  - Added `GET /api/new-dashboard/live-state` to `dashboard/status_server.py` — the same
    `LiveDashboardState`-shaped payload `dashboard/app.py` already served (via the existing,
    unchanged `dashboard/live_state_adapter.py::build_live_state()`), now also on the actually-deployed
    backend. No logic duplicated; a second route registration of an existing function.
  - `SocketContext.tsx`'s REST-fallback poll target changed from the incompatible `/api/status` to
    this endpoint. Its dev server (`server.ts`, an Express+`ws` simulator with hardcoded fake state)
    had its own fake WebSocket ticking **removed** (no real WebSocket backend exists —
    simulating one would show fake data instead of real backend state, defeating the integration)
    and gained a real HTTP proxy route forwarding to the actual Python backend
    (`BACKEND_URL`, default `http://127.0.0.1:8090`). The frontend's existing WS-fail→poll fallback
    now correctly engages against real data instead of a fake feed.
  - **Two real defects found only by loading the page in a browser** (exactly why this validation
    step matters, not a formality): (1) `dashboard/strategy_service.py::_build_strategy_packages()`'s
    real `risk_profile` object (`{stopLossPct, takeProfitPct, ...}`) crashed React, which only ever
    expected the mock's simple string label — fixed by widening `types.ts` and rendering the object
    sensibly (`StrategyRuntimeStatus.tsx`) instead of dumbing down the real, more detailed backend
    data to fit the mock's assumption. (2) `state.riskControls.autoDisableConditions` doesn't exist
    on the real backend (that's an editable-operator-controls feature not built yet, correctly
    deferred to the "Operator Controls" milestone) — crashed on `undefined.newsEvent`; fixed with
    defensive defaults in `LiveOperationsDashboard.tsx`, not fabricated backend values.
  - Verified via Playwright: LIVE tab renders real strategy catalog (`ST-A2`, `LondonBreakout`, etc.),
    real (if `DEGRADED`, honestly shown) broker gateway status, real $0.00/0.0% figures matching the
    actual empty-position state, a real EURUSD candlestick chart, zero console errors, zero crashes.
  - New tests: `tests/test_status_server.py` (6 new, covering `/api/new-dashboard/live-state`
    delegation and the full `/api/operations/*` family). Full suite: 1575 passed, same 29
    pre-existing failures, 4 skipped. Both `smc-demo-runner.service` and `live-dashboard.service`
    verified healthy (0 restarts) throughout; the dev server used for browser verification was
    stopped afterward — not a production deployment mechanism.
  - **Not done, deliberately, per this task's own scope**: building/deploying the frontend to be
    served by `status_server.py` itself (still requires `vite build` + a static-serving route
    decision — see `docs/dashboard/DASHBOARD_IMPLEMENTATION_PLAN.md`'s existing cutover note);
    the `SVOS`/`SUGGESTIONS` tabs (System 1/fabricated-data territory, out of scope); Operator
    Controls (pause/resume/kill-switch/risk-control-editing) — none of their backend endpoints exist
    yet, correctly left as the next-but-one milestone; WebSocket/Event Streaming itself.
- [x] **Legacy `/dashboard/` route staleness fix — 2026-07-04**: the pre-existing server-rendered
  HTML dashboard (`dashboard/status_server.py`'s `/dashboard/` route, publicly reachable at
  `http://34.87.36.159:8090/dashboard/` — a real, already-deployed surface distinct from the Gai
  SPA above) had two live staleness bugs, found by checking the actual public URL: (1) a hardcoded
  "Strategy Guide — SMCOrderBlockFVGSession" heading, reworded to not claim it describes whichever
  strategy is currently running (the header elsewhere on the same page already correctly showed
  `ST-A2`, dynamically, from `state.get("strategy")` — only this one static label was stale); the
  `state.get("strategy", ...)` fallback default in the page-header renderer was also changed from
  the hardcoded broken strategy name to a neutral `"unknown"`. (2) `_load_log()` returned the
  *first* candidate log file that merely existed (`smc_ob_fvg_demo.log`, last written 2026-07-01,
  three days stale) instead of the one actually being written to (`strategy_demo.log`, live) —
  fixed to pick whichever candidate has the most recent mtime. Verified against the live,
  running service: the `/dashboard/` route now shows current (today's) log timestamps and no
  remaining reference to the unregistered strategy name. New test:
  `tests/test_status_server.py::test_load_log_prefers_most_recently_written_file_not_first_existing`.
  Full suite: 1576 passed, same 29 pre-existing failures; both services healthy (0 restarts)
  throughout; `live-dashboard.service` restarted to load the fix.
- Port `execution/startup_recovery.py`'s broker-truth reconciliation (implemented for
  `run_st_a2_demo.py` in Phase 1, 2026-07-04) into whichever runner survives the pipeline port —
  or confirm it already covers `run_portfolio.py` once absorbed. **Not started** for
  `run_portfolio.py` itself; the reconciliation logic exists and is reusable, this is a wiring task
  now, not new-capability design.
- Retire `production/engine/orders.py`/`positions.py` if `execution/trade_manager.py` remains the
  chosen path, or migrate to them if the reverse is chosen — do not leave both. **Not started.**
- Deploy the winning runner via a proper systemd unit; retire the losing one's unit. **Not
  started** — no systemd/deployment change has been made; `run_portfolio.py` is still present and
  unretired pending the actual pipeline port above.
- Acceptance: exactly one execution engine has a systemd unit; crash-mid-order test resolves
  automatically on restart. **Not met yet.**

### Phase 3 — Consolidate Dashboard, API, and Strategy-Loader Duplication
- Merge `app.py`/`live_app.py`/`status_server.py` into one backend serving both operational and
  New Dashboard routes; install its systemd unit.
- Apply the CONFIRM-token pattern consistently to every real mutation endpoint.
- Connect Pipeline A (`production/importer.py`/`verifier.py`) to whatever the canonical runner
  actually loads, or formally retire Pipeline A in favor of Pipeline B's config-driven loading —
  do not leave them disconnected.
- Acceptance: one dashboard process reachable at one URL; `grep` confirms no duplicate route
  definitions across files; an imported/verified package is demonstrably what the runner executes.

### Phase 4 — Observability and Deployment Hygiene
- Feed `/api/v1/production/health`'s heartbeat from the actual canonical runner.
- Add freshness timestamps to every dashboard widget.
- Confirm/wire Telegram alerting for whichever runner is canonical post-Phase-2.
- Document the final deployment topology (systemd units, ports, processes) as the new
  `docs/architecture/system_architecture.md` source of truth, retiring stale duplicates.
- Acceptance: `/api/v1/production/health` correctly reports unhealthy when the tick loop is
  killed; every dashboard widget shows a last-updated indicator.

---

## Acceptance Criteria (platform-level, all phases)

1. Exactly one execution engine is deployed via systemd; `grep` across `deploy/gcp-vm1/systemd/`
   and any future unit files confirms no second competing unit exists.
2. A simulated losing streak past the configured threshold halts new order submission, verified
   by an automated test.
3. A simulated process kill mid-order-submission results in automatic, correct reconciliation on
   restart — no manual JSON inspection required.
4. Every mutation-class API endpoint requires the same CONFIRM-token contract; a test asserts a
   request without the token is rejected for each such endpoint.
5. Exactly one dashboard backend is deployed; the New Dashboard SPA is reachable on the live host.
6. `/api/v1/production/health` (or its successor) returns unhealthy within one heartbeat interval
   of the tick loop stopping, verified by an automated test that kills only the tick loop.
7. `LIVE_TRADING=false`/`DEMO_ONLY=true` remain enforced throughout — no phase of this plan
   changes, weakens, or adds a bypass for this gate.

## Definition of Done

System 2 is "done" for the purposes of this master plan (still demo-only — this is not a
live-trading readiness bar) when:

- All four roadmap phases have landed and their acceptance criteria pass.
- The Current Status table in this document has been re-run and every row reads **Implemented**
  or **Deprecated** (for anything intentionally retired) — no row remains **Partial**, **Missing**,
  **Broken**, or **Duplicate**.
- This document has been updated in place to reflect the new state (it remains the single source
  of truth — supersede, don't fork, a new report).
- A follow-on decision (explicitly out of this plan's scope) is made by the owner on whether to
  pursue SVOS Production Approval for any strategy, which is the only path that could ever make
  live trading a legitimate subsequent discussion.

### Production Candidate Checklist (added 2026-07-04, Phase 6 — the detailed gate the bullets above summarize)

This is the authoritative, itemized Definition of Done for reaching "Production Candidate" status
(still demo-only — Production Candidate is a review gate, not a live-trading authorization).
Updated in place as items land; do not fork a second copy of this checklist elsewhere.

**Execution Platform**
- [x] Single canonical runner — `run_st_a2_demo.py`, confirmed the only one with a systemd unit,
  actually trading ST-A2 (fixed 2026-07-04, `docs/systemd/SMC_DEMO_RUNNER_ANALYSIS.md`).
- [x] Stable broker connection — verified, 0 restarts across multiple sessions this pass.
- [x] Recovery validated — `execution/startup_recovery.py`, tested end-to-end (Phase 1).
- [x] Risk feedback operational — real close events feed `record_result()`/`record_close()`/
  `CircuitBreaker.record_trade()` (Phase 1).
- [ ] Durable *risk/portfolio* ledger (transactional, not JSON-file) — still open.
- [ ] `run_portfolio.py` Tier 2/3 disposition (retire or feature-port) — still open.

**Dashboard**
- [x] No mock data on integrated widgets — LIVE tab confirmed browser-verified against real
  backend data (Phase 6); mock `server.ts` simulation retained only as an offline fallback for
  the SVOS/Suggestions tabs, not the LIVE tab's actual data path.
- [ ] All widgets consume production APIs — per the Phase 6 coverage matrix
  (`docs/dashboard/DASHBOARD_BACKEND_MAPPING.md`), roughly half; the rest are "Backend Ready"
  (real data exists, e.g. `/api/operations/events`, full health grid) but not yet bound to a widget.
- [x] Backend contracts documented — `docs/dashboard/DASHBOARD_BACKEND_MAPPING.md`, per-endpoint
  and per-widget.
- [ ] Health dashboard operational — `state.health`/`/api/operations/health` are real but no LIVE
  tab widget renders the health grid yet (Backend Ready, not connected).

**Security**
- [~] Authentication implemented — `dashboard/rbac.py` (2026-07-04) brings `dashboard/auth.py`'s
  bearer-token/trusted-proxy identity model to the FastAPI backend; `status_server.py`'s
  emergency-stop and all `/api/control/*` mutation routes now enforce it (`Depends(require_role
  (...))`, verified live: unauthenticated POST returns 401). Still missing: a frontend
  session/login UI, and other Flask-side mutations (position close/protect/cancel, activation)
  are not yet ported to the same FastAPI dependency.
- [~] RBAC implemented — same role model (`research_operator`/`incident_operator`/
  `risk_operator`/`admin`) now enforced on both backends; `strategy:toggle`/`trading:pause`/
  `trading:resume` added to `_ROLE_ACTIONS` (`dashboard/auth.py`) for the new controls. Not yet
  wired onto the remaining unauthenticated Flask mutation routes noted above.
- [x] Audit logging enabled — `operations.execution_event`/`recovery_checkpoint` (Sprint 2.3),
  `TradeJournalDB`, dashboard control-state changes.
- [x] Operator confirmations enforced (2026-07-04) — `/api/emergency-stop[/clear]` plus the new
  `/api/control/pause`, `/api/control/resume`, `/api/control/close-all`,
  `/api/control/toggle-strategy` all require an exact-match CONFIRM token in addition to RBAC.
  Other mutation-class endpoints outside this family (activation, position close/protect/cancel)
  still lack one.

**Observability**
- [x] Monitoring available — `/api/operations/*` (Phase 5), `/metrics` (Prometheus format).
- [x] Alerts operational — Telegram, real, wired into the live runner.
- [~] Event history accessible — real and durable via Postgres (`/api/operations/events`,
  Phase 5), but not yet surfaced in the dashboard UI (Phase 6 coverage matrix).
- [ ] Health endpoints complete — `/api/v1/production/health` still reads a heartbeat file the
  canonical runner never writes to; `/api/operations/health` is real but runner-adjacent, not the
  same endpoint referenced elsewhere in this document's own acceptance criteria (§ above, item 6).

**Operations**
- [x] Deployment documented — `docs/systemd/SMC_DEMO_RUNNER_ANALYSIS.md`,
  `docs/vps/STABILIZATION_REPORT.md`, this document's own Deployment Architecture section.
- [x] Rollback documented — every change this pass included a one-line/`git checkout` rollback path
  (the runner fix, the removed dead-code cluster via `git status`, the dashboard changes).
- [~] Runbook available — **started 2026-07-04** (owner feedback: begin alongside implementation,
  not deferred to the end): `docs/vps/OPERATOR_RUNBOOK.md` covers daily checks, monitoring routines,
  broker-disconnect/VPS-reboot/risk-trigger/emergency-stop response, deployment rollback, and backup
  restore. Update it every remaining sprint, not just once at the end.
- [ ] Disaster recovery documented — backup/restore exists (`docs/database_authority_stabilization.md`
  §8 rollback plan for the DB authority model specifically, and `docs/vps/OPERATOR_RUNBOOK.md`'s
  restore-from-backup procedure) but no full-platform DR *rehearsal evidence* exists yet.

**Status: not yet a Production Candidate.** Roughly two-thirds of the Execution Platform and
Dashboard sections are done; Security is now partially closed (Real-Time Operations Layer,
2026-07-04 — RBAC + CONFIRM tokens on the emergency-stop/control family, WebSocket event
streaming) but a frontend login UI and the remaining unauthenticated Flask mutation routes are
still open, alongside most of Operations.
