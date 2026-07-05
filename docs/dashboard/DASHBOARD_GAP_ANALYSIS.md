# Dashboard Gap Analysis

- Date: 2026-07-04
- Compares the Gai dashboard (per [DASHBOARD_STATUS.md](DASHBOARD_STATUS.md)) against System 2's
  actual capabilities (per [DASHBOARD_BACKEND_MAPPING.md](DASHBOARD_BACKEND_MAPPING.md) and
  `SYSTEM2_MASTER_PLAN.md`) to produce a dependency-ordered gap list for
  [DASHBOARD_IMPLEMENTATION_PLAN.md](DASHBOARD_IMPLEMENTATION_PLAN.md).

## Missing pages

- None structurally — LIVE/SVOS/SUGGESTIONS covers the two required system views plus an extra.
  `SUGGESTIONS` has no real backend concept behind it at all (no recommendation engine exists) —
  treat as low-priority/cut candidate, not a gap to fill.
- A dedicated **Alert Center** page/panel does not exist (events are a scrolling log inside LIVE,
  not a filterable/ackable alert list) — needed per the brief's Phase-4 ordering (#11).
- A dedicated **Settings** page does not exist (risk controls are edited inline in
  `LiveOperationsDashboard`, no user/session/notification preferences anywhere).
- A dedicated **Deployment status** page does not exist — strategy promote/demote exists as an
  action, but there's no view of "what's staged vs what's actually running," which matters given
  the confirmed catalog/portfolio-YAML split.

## Missing APIs

- No real backend implements the frontend's exact expected contract at all
  (`/api/status`, `/api/action`, `/api/live/*`) — every one of these needs to be newly added,
  not just pointed at an existing route (see mapping doc's per-field API column).
- No API exposes `TradeJournalDB` trade history/analytics directly to any dashboard today (only
  consumed internally by `status_server.py`'s merged `/api/status` and `check_journal()`).
- No API exposes `config/strategy_portfolio.yaml` (the file that actually gates live/shadow
  routing) — only `strategy_catalog.yaml` is exposed, which is the wrong file for a "what's
  actually running" view.
- No API exposes CPU/RAM/disk (`systemResources`) — no resource-monitoring code exists at all.
- No API exposes risk controls as a structured, editable object matching `RiskControls`.

## Missing websocket events

- All of them — there is no WebSocket server anywhere in the Python backend. This is the single
  largest structural gap between the frontend's design and the backend's reality: the frontend was
  built WS-first with REST as a fallback; the real backend is REST-only.

## Missing database models

- No unified trades table with slippage/latency/commission/MAE/MFE columns (three fragmented,
  incompatible journals exist instead — `TradeJournalDB` SQLite, `logs/trades.jsonl`,
  `logs/strategy_demo_trades.jsonl`).
- No durable risk/portfolio ledger (this is also `SYSTEM2_MASTER_PLAN.md`'s #1 platform-level
  finding, independent of the dashboard — the dashboard cannot show accurate live risk state until
  this exists, because the state it would read is in-memory-only and never updated from real
  closes today).
- No resource-usage table/timeseries.
- No SMC-pipeline-stage event log (the 12-stage checklist, active OB/FVG objects) — this is a new
  data model, not just a missing API; no strategy adapter emits this today.

## Missing services

- No WebSocket broadcast service.
- No unified "live state assembler" service that composes broker snapshot + journal summary +
  health checks + strategy catalog into one coherent payload — today these are 6+ separate,
  independently-shaped service calls across 3 processes.
- No resource-monitoring service.
- No alerting/ack service (Telegram alerts exist and fire, but there's no queryable "alert history
  with ack state" the dashboard could read).

## Missing operator workflows

- No CONFIRM-token contract on the dashboard's own action endpoints (frontend's
  `pauseTrading`/`forceCloseTrade`/`triggerKillSwitch` etc. have no token concept at all) — this
  actively contradicts this repo's `CLAUDE.md` §4 and `SYSTEM2_MASTER_PLAN.md`'s stated target of a
  single consistent CONFIRM-token pattern across every mutation route.
- No login/session flow in the frontend at all — real backend auth (`dashboard/auth.py`) is
  entirely bypassed.
- No reconciliation-status workflow (surfacing `RECOVERY_PENDING`/ambiguous orders) — flagged in
  `SYSTEM2_MASTER_PLAN.md` as the single most operator-critical missing view, and absent from every
  Gai dashboard tab today.

## Missing monitoring

- CPU/RAM/disk, Redis (Redis doesn't exist in this stack at all — the mock's Redis health row
  should be **removed**, not wired, since faking a health check for infrastructure that isn't part
  of the architecture is actively misleading).
- No per-widget "last updated" freshness indicator — `SYSTEM2_MASTER_PLAN.md` explicitly calls this
  out as a requirement given a past incident (dashboard showed a ~10h-stale log with no visual cue).
- Health checks only run inside `scripts/health_check.py` invocations, not continuously — nothing
  currently pushes a live heartbeat the dashboard could poll every few seconds without re-running
  the full check script.

## Missing controls

- No risk-limit editing wired to a real, persisted store (only static YAML values today; editing
  from the UI has nowhere durable to write to).
- No resource/CPU throttle or alerting threshold controls.

## Missing risk management interface

- The entire risk-halt feedback loop is dead code in the backend itself (per
  `SYSTEM2_MASTER_PLAN.md`) — no dashboard change can show accurate daily/weekly/monthly loss-halt
  state until that backend gap closes. Any risk widget built before then must be explicitly labeled
  as showing configured limits, not enforced/live state.

## Missing execution interface

- No unified view of the two competing execution engines (`run_st_a2_demo.py` legacy vs
  `run_portfolio.py` canonical) — an operator using this dashboard today would have no way to tell
  which one is actually running, which `SYSTEM2_MASTER_PLAN.md` identifies as the platform's
  central operational risk.
- No visibility into `ExecutionStateStore`'s state machine (`SIGNAL_RECEIVED → ... → FILLED` /
  `RECOVERY_PENDING`) anywhere in the frontend, despite a real, working API for it
  (`status_server.py`'s `/api/execution/timeline/{execution_id}`).

## Missing deployment interface

- No dashboard view of which systemd unit/process is actually active on the VPS (the split-brain
  the master plan is most worried about) — this is arguably the single highest-value new panel:
  "which runner is live, which dashboard backend is live."
- No wiring of `production/importer.py`/`verifier.py` (Pipeline A, checksum/signature verified
  packaging) to anything the dashboard shows — it's disconnected from the runners entirely per the
  master plan, and invisible in the dashboard too.

---

## Cross-cutting risk: fabricated data if shipped as-is

Three tabs/modes (`SvosQuantLab`, `SuggestionsTab`, Manual Sandbox mode) render confident,
detailed, numeric output with **zero backend backing** — synthetic win rates, fabricated
suggestion percentages, a fake $10,000 paper-trading balance. Shipping these unchanged into a
"production operator interface" would be actively misleading, not just incomplete. Recommendation:
gate these behind an explicit "Simulation / Not Live Data" banner until real backing exists, or cut
them from the production build entirely (see implementation plan, Phase 0).

## Quick wins available before any backend work

- `SystemHealth.tsx` is a finished component with a real backend equivalent
  (`scripts/health_check.py` + `_health_snapshot()`) and is simply not imported anywhere in the
  current component tree.
- `TradeExecutionHistory.tsx`/`TradesTable.tsx` are finished and only need real data shaped to
  their existing props — no frontend rework needed, only a backend endpoint.
