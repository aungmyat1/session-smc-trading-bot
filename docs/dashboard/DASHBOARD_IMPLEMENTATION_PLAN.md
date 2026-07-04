# Dashboard Production Integration Plan

- Date: 2026-07-04
- Dependency-ordered roadmap to make the Gai dashboard the operator interface for System 2,
  building on [DASHBOARD_STATUS.md](DASHBOARD_STATUS.md),
  [DASHBOARD_BACKEND_MAPPING.md](DASHBOARD_BACKEND_MAPPING.md), and
  [DASHBOARD_GAP_ANALYSIS.md](DASHBOARD_GAP_ANALYSIS.md). Sequenced per the brief's Phase-4
  ordering (API → WS → Auth → live status → positions → orders → history → strategy → risk →
  health → alerts → logs → e-stop → deployment → analytics → settings), adjusted where a strict
  dependency forces reordering (e.g. auth must gate mutation endpoints before they're wired, not
  after).
- This plan operates entirely within `SYSTEM2_MASTER_PLAN.md`'s existing constraints: demo-only,
  `LIVE_TRADING=false`, no phase here authorizes live trading or touches that gate.
- Integration point: **`dashboard/app.py`** (Flask) — it already has real broker/candle access
  (`live_dashboard_service.py`), SVOS catalog reads, session auth, CONFIRM-token emergency-stop,
  and static-SPA hosting for the old `New Dashborad/dist/`. Extend it; do not stand up a 4th
  backend process. This is also consistent with `SYSTEM2_MASTER_PLAN.md` Phase 3's own goal of
  consolidating to one dashboard backend.

---

## Phase 0 — De-risk the fabricated-data surfaces (prerequisite, do first)

Before any real wiring, stop the dashboard from being able to ship convincing fake data
unlabeled. Add a lightweight `SIMULATED` banner wrapper (or exclude from the production build
entirely) around `SvosQuantLab`, `SuggestionsTab`, and `LiveOperationsDashboard`'s Manual Sandbox
mode. Cheapest possible change, removes the single biggest "actively misleading operator" risk
identified in the gap analysis, and does not block anything downstream.

## Phase 1 — Backend API layer

- Add a `dashboard/live_state_adapter.py` module that assembles a best-effort
  `LiveDashboardState`-shaped JSON from real services already mapped in
  `DASHBOARD_BACKEND_MAPPING.md`: broker snapshot + candles (`live_dashboard_service.py`), trade
  history/analytics (`TradeJournalDB.summary()`), strategy list (`strategy_catalog.yaml` via
  `strategy_service.py`), health (`scripts/health_check.py`'s existing checks), control state
  (`control_state.py`). Fields with no real backing (SMC pipeline checklist, active OB/FVG objects,
  HTF bias/swing/ATR, CPU/RAM/disk, Redis) are returned as explicit empty/neutral defaults, not
  fabricated values — and the response includes a `dataQuality`/`unavailable` field listing which
  top-level keys are placeholders, so the frontend (Phase 5+ follow-up) can render an honest
  "not available" state instead of silently showing zeros as if real.
- Add `GET /api/new-dashboard/live-state` to `dashboard/app.py` returning this object directly,
  matching the shape `SocketContext.tsx`'s REST-fallback path expects (raw `LiveDashboardState`,
  not wrapped, verified against `server.ts`'s `/api/status` handler). **Do not reuse the path
  `/api/status`** — it already exists twice (`app.py:831` and `status_server.py`) with an
  unrelated SVOS/EVF-summary contract; landing a third, incompatible `/api/status` would either
  collide or require breaking existing consumers. The frontend's `SocketContext.tsx` fetch URL
  must be updated to call the new path.
- Add `GET /api/new-dashboard/trades`, `GET /api/new-dashboard/rejections` mirroring the same
  source for parity with the frontend's (currently orphaned) direct-fetch endpoints, in case
  they're wired in later.
- Acceptance: `GET /api/new-dashboard/live-state` returns 200 with a JSON body matching
  `types.ts`'s `LiveDashboardState` keys, backed by real data where mapped, explicit placeholders
  where not.

## Phase 2 — WebSocket integration

- `SYSTEM2_MASTER_PLAN.md` already treats "retain polling, no WebSocket requirement" as an
  acceptable deliberate decision at current trade frequency. Recommendation: **do not build a new
  WS server yet.** Instead, make `SocketContext.tsx`'s existing REST-polling fallback path the
  primary path (it already exists and works), by having WS connection attempts fail fast/be
  disabled via a build-time flag, rather than building new server-side WS infrastructure to satisfy
  a frontend affordance the backend doesn't need yet.
- If real-time push is later decided to be worth the investment (operator headcount or trade
  frequency increases — the trigger condition `SYSTEM2_MASTER_PLAN.md` already names), add a
  minimal Flask-SocketIO or ASGI WS endpoint that just re-broadcasts the same
  `live_state_adapter.py` payload on an interval; do not design a second, divergent payload shape.
- Acceptance: dashboard is fully functional and real-data-backed over polling alone; WS remains an
  explicitly deferred, documented decision, not a silent gap.

## Phase 3 — Authentication

- Wire the frontend's `fetch` calls to send whatever `dashboard/auth.py` already requires (Bearer
  token + `X-SVOS-Actor`/`X-SVOS-Role`, or trusted-proxy headers) — add a thin auth-header injector
  in `SocketContext.tsx`/a new `api.ts` client module, sourced from a login step or an
  operator-provided token (scope of the login UI itself is a follow-up, not blocking).
  `status_server.py`'s auth gap (no role check on its emergency-stop routes) is a backend fix, out
  of this plan's scope — flag it, don't silently route around it by preferring `status_server.py`.
- Acceptance: every mutation call from the dashboard includes the same auth headers `app.py`
  already validates on other routes; a request missing them is rejected with 401/403 exactly as
  today's `/api/emergency-stop` route already demonstrates the pattern for.

## Phase 4 — Live account status

- Backed by Phase 1's adapter (`brokerConnection`, `health.broker`). No new work beyond exposing it.

## Phase 5 — Positions

- Map `live_dashboard_service.py`'s real broker snapshot into `state.pairs`/an open-positions list
  distinct from the mock's per-pair `activeTrade` concept. Reconcile against
  `TradeJournalDB.get_open_trades()` explicitly (mapping doc flags these as two independent,
  unreconciled views) — pick the broker snapshot as canonical (it's the ground truth), and
  surface, don't hide, any disagreement with the journal's OPEN rows as a data-quality warning.

## Phase 6 — Orders

- Wire `forceCloseTrade`/position close-protect-cancel actions to the real
  `live_dashboard_service.py` mutation routes (`app.py:1259/1274/1296`), replacing the mock's fake
  order simulation. Apply the CONFIRM-token pattern here too, per the gap analysis's operator-
  workflow finding — do not ship these as one-click actions without it, consistent with this
  repo's own `CLAUDE.md` §4.

## Phase 7 — Trade history

- Add a dedicated `GET /api/new-dashboard/trade-history` (or reuse Phase 1's `/api/trades`) backed
  by `TradeJournalDB` — this is the "quick win" from the gap analysis: `TradeExecutionHistory.tsx`
  and `TradesTable.tsx` are already finished and prop/context-driven; only the data source changes.
  MAE/MFE/slippage/latency/commission fields remain null/omitted until `execution/trade_manager.py`
  is instrumented to capture them (a backend change out of this plan's scope — do not fabricate
  these values to fill the UI).

## Phase 8 — Strategy runtime

- Decide explicitly which file is canonical for "what's running": recommend exposing **both**
  `strategy_catalog.yaml` (via existing `strategy_service.py`, SVOS-lifecycle view) and
  `strategy_portfolio.yaml` (new, currently unexposed — the file that actually gates live/shadow
  order routing) as separate, clearly-labeled fields, rather than picking one and hiding the
  divergence the backend mapping doc identified.
- Wire `StrategyRuntimeStatus.tsx` to this combined view.

## Phase 9 — Risk monitor

- Expose configured risk limits (from `strategy_portfolio.yaml` per-strategy `risk` values) as
  read-only until Phase 1 of `SYSTEM2_MASTER_PLAN.md` (durable, transactional risk ledger) lands —
  label explicitly as "configured limits," not "live enforced state," per the gap analysis's
  risk-interface finding.
  **Update 2026-07-04**: the risk-halt feedback loop is no longer fully dead code — it is now wired
  and JSON-persisted in the deployed runner (`scripts/run_st_a2_demo.py`, see
  `docs/systems/system2/STATUS.md`). This still does not meet this phase's bar for a "live enforced
  state" label: the persistence is a plain JSON file (no atomic write, no transactional guarantee),
  it only covers the deployed legacy runner (not the canonical one), and it has not been verified
  against a real broker end-to-end. Continue treating any risk widget as showing configured limits
  until the durable ledger itself lands.

## Phase 10 — Health monitor

- Wire the orphaned `SystemHealth.tsx` into `App.tsx`'s header (quick win — component is finished).
  Feed it from Phase 1's adapter (`scripts/health_check.py`'s real checks). Remove the mock's
  Redis health row entirely (no Redis exists in this architecture — do not fake a health check for
  infrastructure that isn't part of the stack).
- Add per-widget last-updated timestamps everywhere, per `SYSTEM2_MASTER_PLAN.md`'s explicit
  requirement (past incident: stale log shown with no visual cue).

## Phase 11 — Alert center

- New panel, not present in any tab today. Backed by existing `TelegramAlerter` call sites — add a
  simple in-process ring buffer or the existing `control_events` list
  (`reports/control_state.json`, already bounded to last 200) as the source, exposed read-only.

## Phase 12 — Logs

- Reuse the existing event-stream concept (`EventStream.tsx`) but source from real log files
  (`logs/*.log`, `logs/trades.jsonl`) via a paginated tail endpoint, not the mock's fabricated
  event strings.

## Phase 13 — Emergency stop

- Wire `triggerKillSwitch` to the real `POST /api/emergency-stop` (`app.py:1403`), including its
  exact `confirm_token` contract (`"CONFIRM-EMERGENCY-STOP"` / `"CONFIRM-CLEAR-EMERGENCY-STOP"`) —
  the frontend must prompt for and pass this token, not auto-fill it. Surface
  `RECOVERY_PENDING`/ambiguous execution-state records prominently here too
  (`status_server.py`'s `/api/execution/timeline/{execution_id}`), per `SYSTEM2_MASTER_PLAN.md`'s
  highest-priority operator-visibility gap.

## Phase 14 — Deployment status

- New panel: surface which systemd unit/runner is actually active
  (`run_st_a2_demo.py`/`smc-demo-runner.service` today, per `SYSTEM2_MASTER_PLAN.md`) versus what's
  architecturally canonical (`run_portfolio.py`) — this directly answers the master plan's central
  "which system is actually running" operational risk. Requires a small new backend read (process/
  systemd status query) not covered by any existing route today.

## Phase 15 — Analytics

- Backed by Phase 1/7's `TradeJournalDB.summary()` — no new backend work, just ensure
  `RejectionsAndAnalytics.tsx` reads the real summary instead of the mock's fabricated numbers.
  Signal-rejection log itself remains a **Missing** data model (no strategy adapter emits
  rejection reasons today) — ship this panel with rejections empty/labeled unavailable rather than
  fabricated, until a strategy adapter is instrumented to emit them.

## Phase 16 — Settings

- Lowest priority per the brief. Scope to session/auth-token entry and notification preferences
  only; do not build a generic settings framework speculatively.

---

## Explicitly out of scope for this plan (tracked elsewhere, do not duplicate)

- Consolidating `app.py`/`live_app.py`/`status_server.py` into one process — that's
  `SYSTEM2_MASTER_PLAN.md` Phase 3; this plan assumes `app.py` remains the integration target but
  does not itself retire the other two processes.
- The durable risk/portfolio ledger, restart-recovery reconciliation, and canonical/legacy runner
  split — `SYSTEM2_MASTER_PLAN.md` Phases 1-2. This dashboard plan surfaces these gaps honestly; it
  does not fix them.
- SMC-strategy-specific pipeline instrumentation (12-stage checklist, OB/FVG object tracking) is a
  strategy-adapter-level change, not a dashboard change — noted as Missing throughout, not
  scheduled here.

## Update cadence

At the end of each phase above, update `docs/systems/system2/STATUS.md`,
`docs/systems/system2/ROADMAP.md`, and this file's phase entry (mark done, note deviations) — per
the task brief. Do not create new audit reports; extend these three living documents instead.
