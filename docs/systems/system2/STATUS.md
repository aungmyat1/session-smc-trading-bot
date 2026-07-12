# System 2 — Status

- Last updated: 2026-07-04
- Authoritative platform document: `SYSTEM2_MASTER_PLAN.md` at the repo root — "supersede, don't
  fork" per its own Definition of Done. This file is a shorter status index across both the
  platform (execution/risk) and dashboard-integration workstreams, updated at the end of each
  implementation milestone.

## Platform (execution / risk engine) — current state

- **Landed 2026-07-04 (P0, SYSTEM2_MASTER_PLAN.md Phase 1, partial):** the risk-halt feedback loop
  is wired into the currently-deployed runner (`scripts/run_st_a2_demo.py`):
  - New `execution/position_close_detector.py` diffs `TradeManager.get_positions()` between ticks
    and matches disappeared positions back to their `TradeJournalDB` row.
  - Real close outcomes now call `demo_risk_manager.record_result()`, `PortfolioManager.record_close()`,
    and `CircuitBreaker.record_trade()` (none were called from a real close in this runner before —
    daily/weekly/monthly loss halts and consecutive-loss halts can now fire from real P&L).
  - `risk_state` and `PortfolioManager`'s counters are persisted to `logs/risk_state.json` /
    `logs/portfolio_state.json` every tick and reloaded at process start — a restart no longer
    silently zeroes them.
  - Unmatched broker closes (no matching journal row) are alerted via Telegram
    (`send_reconciliation_mismatch`), not silently dropped or guessed at.
  - Tests: `tests/execution/test_position_close_detector.py`,
    `tests/scripts/test_run_st_a2_demo_close_detection.py` (includes a forced-losing-streak halt
    test and a persistence round-trip test), `tests/core/test_portfolio_manager.py` additions.
- **Landed 2026-07-04 (Sprint 2.1):** order placement in the deployed runner now flows through
  `production.engine.CanonicalExecutionPipeline` (`AllowAllRiskGate` — upstream checks already
  decide, this adds normalized event journaling on top). Additive; `run_portfolio.py` untouched.
- **Landed 2026-07-04 (Sprint 2.2):** `run_portfolio.py::run()` now refuses to start unless
  `RUN_PORTFOLIO_ALLOW_START=true` is explicitly set — can no longer be started by accident.
- **Landed 2026-07-04 (Sprint 2.3):** durable transactional persistence via the already-designed but
  previously-unapplied `operations.*` Postgres schema (migration 004) — applied, ORM added,
  `execution/operations_recorder.py` best-effort-records every pipeline event, intent, risk
  decision, order record, and recovery checkpoint. Restart/no-duplicate-order idempotency itself is
  unchanged (still `ExecutionStateStore`'s job) — this adds a durable, queryable audit trail.
- **Resolved 2026-07-04 (found and fixed same day, VPS stabilization pass):** the deployed
  `smc-demo-runner.service` had been crash-looping since its creation on an unapproved,
  `INTAKE`-stage strategy name (`SMCOrderBlockFVGSession`) — it had **never actually run ST-A2 or
  any strategy in production** before this fix. Root cause and options:
  `docs/systemd/SMC_DEMO_RUNNER_ANALYSIS.md`. Fixed by pointing `deploy/gcp-vm1/run_smc_demo.sh` at
  `--strategy ST-A2`; verified stable (0 restarts, broker connected, clean 60s tick cycles, no
  exceptions) since 2026-07-04T17:01:32Z. All of the Sprint 1-3 work above is now, for the first
  time, running against a live (demo) broker connection rather than only tests. Also removed this
  pass: two disabled, dangling systemd units (`benchmark-bot.service`, `smc-bot.service`) whose
  target directories no longer exist — archived before removal.
- **Execution Pipeline Consolidation, Tier 1 — 2026-07-04:** confirmed `run_st_a2_demo.py` as the
  one canonical execution lifecycle (`docs/systems/system2/CANONICAL_EXECUTION_PIPELINE.md`) and
  removed a 411-line dormant "Production Platform v2" cluster with zero live callers
  (`production/{recovery,operations,reporting,api}.py` + `production/engine/{orders,positions,risk}.py`,
  introduced already-disabled by commit `e009d5f`). Two other dormant stacks found (`bot.py`,
  `adaptive/run_shadow.py`) were deliberately **not** touched — both have real, if-dormant, test
  coverage; removing or merging either is a product decision, not a mechanical dedup. Full detail:
  `docs/systems/system2/EXECUTION_PIPELINE_INVENTORY.md`, `PIPELINE_CONSOLIDATION_PLAN.md`. Zero
  regressions (confirmed via `git stash` that all 29 remaining test failures predate this work);
  live production runner re-verified unaffected throughout.
- **Operations Control Center, Phase 5 — 2026-07-04:** eight new read-only endpoints
  (`GET /api/operations/{health,account,positions,orders,trades,strategy,risk,events}`) landed in
  `dashboard/status_server.py` — confirmed the *only actually-deployed* dashboard backend, not
  `app.py`/`live_app.py`. Every endpoint reuses an existing service (`live_dashboard_service.py`,
  `TradeJournalDB`, the runner's own state file, persisted risk/portfolio JSON) — no new business
  logic. New capability: read helpers on `execution/operations_recorder.py` expose the Sprint 2.3
  `operations.*` Postgres tables for the first time (`get_recent_events`/`get_recent_runtimes`).
  Also fixed two incomplete, pre-existing edits in `dashboard/strategy_service.py` that were
  breaking `import dashboard.app` (discovered during test validation, not introduced this pass).
  Full mapping: `docs/dashboard/DASHBOARD_BACKEND_MAPPING.md`. Verified: all 8 endpoints return
  HTTP 200 with real data; full suite unchanged (1570 passed, same 29 pre-existing failures); both
  `live-dashboard.service` and `smc-demo-runner.service` healthy, 0 restarts, throughout.
- **Operational Dashboard Integration, Phase 6 — 2026-07-04:** the Gai dashboard's LIVE tab now
  consumes real backend data end-to-end — verified by actually running the dev server and loading
  it in a browser via Playwright, not just by inspecting code. Added the missing
  `GET /api/new-dashboard/live-state` route to `status_server.py` (reusing the existing
  `live_state_adapter.build_live_state()` unchanged), repointed `SocketContext.tsx` at it, and
  replaced the dev server's fake WebSocket ticking with a real proxy to the Python backend (no real
  WebSocket exists to simulate — faking one would show fake data). **Two real crashes found only by
  loading the page** — a real `risk_profile` object the mock never sent (fixed by rendering it
  properly, not dumbing down the real data) and a nonexistent `autoDisableConditions` field (an
  unbuilt operator-controls feature; fixed with safe defaults, not fabricated values). Confirmed via
  screenshot: real strategy catalog, real (honestly-shown `DEGRADED`) broker status, zero console
  errors. 6 new tests (`tests/test_status_server.py`); full suite 1575 passed, same 29 pre-existing
  failures; both services healthy throughout; the verification dev server was stopped afterward
  (not a production deployment mechanism — building/serving the frontend for real remains open).
- **Real-Time Operations Layer, Phases 1-5 — 2026-07-04:** owner-directed consolidated build (no
  Redis, no new services — extends the one deployed backend, `dashboard/status_server.py`).
  - `dashboard/events.py` (new): unified `BaseEvent` schema (`execution`/`strategy`/`system`
    source tags) + in-process `EventBroadcaster` (one `asyncio.Queue` per WebSocket client, bounded
    at 500, drops oldest for a saturated client only — never blocks the publisher) + `EventPoller`,
    which collects from the durable stores that already exist (`operations_recorder.get_recent_events`,
    `control_state.load_control_state`, the runner's state file's `broker_status`) since the runner
    and dashboard are separate OS processes with no shared memory.
  - `GET /ws` (WebSocket) + a 2s background poll loop landed in `status_server.py`; five new REST
    endpoints — `/overview`, `/live/trades`, `/svos/status`, `/strategies/performance`,
    `/system/health` — each delegates to an existing service (`TradeJournalDB`, `load_control_state`,
    `strategy_service.list_strategies`, or an alias of the Phase 5 `/api/operations/*` handlers); new
    `TradeJournalDB.summary_by_strategy()` is the one new piece of business logic, a per-strategy
    breakdown using the same query pattern as the existing `summary()`.
  - `dashboard/rbac.py` (new): FastAPI-native `require_role()` dependency reusing
    `dashboard/auth.py`'s actual `_ROLE_ACTIONS`/`_permitted_actions` model (not a second, divergent
    one) — bearer-token or trusted-proxy identity, same CSRF double-submit check for proxy mode.
    `strategy:toggle`/`trading:pause`/`trading:resume` added to `_ROLE_ACTIONS` for `risk_operator`/
    `admin`.
  - New RBAC + CONFIRM-token-gated operator controls: `POST /api/control/{pause,resume,close-all,
    toggle-strategy}` — each a thin, named entry point onto the *same* `activate_emergency_stop`/
    `clear_emergency_stop` state machine (scope `block_only` for pause, `close_positions` for
    close-all), not a parallel control state. `toggle-strategy` is the one new capability, validated
    against whichever strategy is actually running (single-strategy deployment) rather than
    pretending multi-strategy control exists. The pre-existing `/api/emergency-stop[/clear]`
    endpoints were retrofitted with the same `Depends(require_role("risk_operator","admin"))` — they
    had no RBAC before this pass, only a CONFIRM token.
  - Verified live against the running `live-dashboard.service` (not just `TestClient`): all 5 new
    GET endpoints return HTTP 200 with real data; `/ws` accepts a real connection; unauthenticated
    `POST /api/emergency-stop` and `POST /api/control/pause` both now return 401 (previously
    unauthenticated). 0 restarts on `live-dashboard.service` and `smc-demo-runner.service` throughout.
  - Load-tested (Phase 5): 25 concurrent subscribers × 2000 published events, 0 loss, when consumers
    get realistic scheduling opportunities; separately confirmed the documented overload-protection
    path (a burst exceeding one client's 500-deep queue drops only that client's oldest entries,
    never raises) is a deliberate safety net, not a bug.
  - Tests: `tests/dashboard/test_events.py` (7), `tests/dashboard/test_rbac.py` (5),
    `tests/test_status_server.py` additions (operator-control RBAC/CONFIRM-token matrix, all 5 new
    endpoints, WebSocket delivery), `tests/core/test_trade_journal_db.py::test_summary_by_strategy_*`.
  - Not yet done: no frontend widget subscribes to `/ws`; the remaining Flask-side mutation routes
    (position close/protect/cancel, activation) are not yet ported to `dashboard/rbac.py`.
- **Still open, unchanged from `SYSTEM2_MASTER_PLAN.md`:** durable/transactional risk *ledger for
  risk_state/portfolio_state specifically* (JSON persistence remains a mitigation, not this item —
  Sprint 2.3 covers order/event/recovery durability, not this), real broker-truth reconciliation
  wiring for `run_portfolio.py`, dashboard/API/strategy-loader consolidation, observability hygiene.
  See `SYSTEM2_MASTER_PLAN.md` Phases 1-4 and `docs/systems/system2/INFRASTRUCTURE_READINESS.md`
  for full detail and current per-item status.

## Dashboard integration — current state

- Assessment, backend mapping, gap analysis, and phased plan complete: see
  `docs/dashboard/DASHBOARD_STATUS.md`, `DASHBOARD_BACKEND_MAPPING.md`,
  `DASHBOARD_GAP_ANALYSIS.md`, `DASHBOARD_IMPLEMENTATION_PLAN.md`.
- Gai dashboard (`New Dashborad/Gai dashboard/`) confirmed as the more complete of two "New
  Dashboard" deliveries in this repo; not yet built or deployed anywhere.
- **Landed (Implementation Plan Phase 1, backend API layer, partial):**
  `dashboard/live_state_adapter.py` + `GET /api/new-dashboard/live-state` in `dashboard/app.py`
  assembles a best-effort `LiveDashboardState`-shaped payload from real services. Fields with no
  real backend source are returned as explicit neutral placeholders and listed in the response's
  `unavailable` array — not fabricated. Deliberately mounted at `/api/new-dashboard/live-state`,
  **not** `/api/status` (already taken twice, incompatible contract — see mapping doc). Covered by
  `tests/test_dashboard_app.py::test_new_dashboard_live_state_uses_real_broker_and_journal_data`.
- **Not yet done (superseded for the LIVE tab, see below):** the Gai dashboard frontend has not
  been built, deployed, or repointed at this new endpoint. No auth wiring, no WebSocket, no
  CONFIRM-token contract on its actions yet. Fabricated-data surfaces (`SvosQuantLab`,
  `SuggestionsTab`, Manual Sandbox mode) are un-gated. Full remaining scope:
  `docs/dashboard/DASHBOARD_IMPLEMENTATION_PLAN.md` Phases 0, 2-16.
- **Landed 2026-07-05: Gai dashboard SPA built and served from the deployed backend.**
  - Frontend source: `New Dashborad/Gai dashboard/` (React 19 + Vite). Build command:
    `npm install && npx vite build`, run from that directory — outputs to
    `New Dashborad/Gai dashboard/dist/` (gitignored, not committed; rebuild on deploy).
  - `dashboard/status_server.py` (the only actually-deployed backend, via `live-dashboard.service`)
    now serves the built SPA at `GET /new-dashboard/`, with its JS/CSS bundle mounted at
    `/assets` (`StaticFiles`). Distinct from `dashboard/app.py`'s own, unrelated `/new-dashboard/`
    route (an older, undeployed dashboard) — no collision since only one of the two processes runs
    at a time.
  - The LIVE tab is fully live: it reads same-origin `/api/new-dashboard/live-state` (already
    implemented) and posts to `/api/emergency-stop` (already implemented) — no proxy/CORS config
    needed. Verified in production: `/new-dashboard/` and its bundled assets return 200 from
    `live-dashboard.service`.
  - **Known gap, not fixed by this change:** a handful of operator-control actions in the UI
    (strategy activate/pause, risk-controls edit, broker reconnect) call `/api/action`,
    `/api/live/strategy/*`, `/api/live/risk-controls`, `/api/live/broker/reconnect` — none of
    which exist on `status_server.py` yet. Clicking those buttons will 404. Tracked in this
    document's roadmap counterpart (`ROADMAP.md`, Phase 3 row) and
    `docs/dashboard/DASHBOARD_IMPLEMENTATION_PLAN.md` Phase 13-ish (operator controls); not
    scheduled here.
- **Landed 2026-07-05: fail-closed System 2 readiness validation.** New
  `GET /api/system2/readiness` (JSON) and `GET /system2/readiness` (server-rendered
  HTML, no frontend build needed) aggregate 10 checks — database reachability,
  runtime authority, strategy-package approval, risk-firewall presence, broker
  reachability, emergency-stop visibility, critical-incident state, heartbeat
  freshness, duplicate-runtime detection, and reconciliation availability — into
  a single READY/NOT_READY verdict. Every check fails closed on missing/unreachable
  data; today it honestly reports `NOT_READY` (ST-A2 is unapproved per
  `config/strategy_catalog.yaml`, consistent with `CLAUDE.md` §1/§6). Read-only:
  does not touch `LIVE_TRADING`/`DEMO_ONLY`/secrets/broker config. Full detail:
  `docs/systems/system2/DASHBOARD_READINESS.md`.
- **Landed 2026-07-05: `/ws` repaired for real browser use.** The Real-Time Operations Layer's
  `/ws` endpoint and the Gai dashboard's WebSocket client both had real code, but a live test
  proved the connection could never actually authenticate: browsers cannot set
  `Authorization`/`X-SVOS-Actor` headers on a WebSocket upgrade, and `/ws` only accepted
  header-based auth. Fixed with a short-lived (30s), single-use, signed connection ticket
  (`dashboard/rbac.py::mint_ws_ticket`/`validate_ws_ticket`, obtained via the new, authenticated
  `GET /api/ws-ticket`) — header auth is unchanged and still works as a fallback. Two more real
  bugs fixed in the same pass: the frontend alternated reconnects between `/ws` and a nonexistent
  `/api/ws` (confirmed live 404); and its `onmessage` handler expected a `{type, state}` message
  shape the real backend never sends (only the app's original mock server did) — it now treats any
  real event as a refresh signal and fetches `/api/new-dashboard/live-state` on open, since the
  server sends no bootstrap snapshot. Verified against the live production process: ticket
  issuance, ticket-authenticated connection, replay rejection, and real event delivery (exact
  `BaseEvent` shape from `dashboard/events.py`) all confirmed working; REST polling preserved as
  the automatic fallback. **Known remaining gap**: the browser has no way to obtain an operator
  credential yet (no login screen exists) — `getOperatorAuthHeaders()` reads an optional
  `localStorage` credential that nothing currently sets, so real-world browser behavior today is
  still "poll" until Priority 1 (operator-control integration) adds a credential source. Full
  detail: `docs/systems/system2/DASHBOARD_READINESS.md` §8.
- **Landed 2026-07-05 (second pass): operator authentication integrated end-to-end.** Closed the
  gap the previous entry flagged — `OperatorLogin.tsx` (new) is a minimal login form (token + actor
  name, no registration/account-management) that validates against the existing backend via
  `GET /api/ws-ticket` before storing anything, in `sessionStorage` (moved from `localStorage`).
  Every operator-control call now sends real `Authorization`/`X-SVOS-Actor` headers via a new
  `authenticatedFetch()` wrapper; a `401` auto-triggers logout (this backend is stateless, so
  that's the closest analog to session expiry). Pause/Resume/Toggle-Strategy(pause)/Emergency-Stop
  were repointed from nonexistent mock-server routes (`/api/action`, `/api/live/*`) to the real,
  already-existing `/api/control/*`/`/api/emergency-stop*` endpoints; a new `clearEmergencyStop`
  context method wires `/api/emergency-stop/clear` (no UI button yet). Every mutation now requires
  an explicit `window.confirm()` before sending — closing the "must prompt, not auto-fill" gap the
  original dashboard design doc called for but the first kill-switch integration never built.
  `forceCloseTrade`/`activateStrategy`/`updateRiskControls`/`reconnectBroker` were deliberately left
  unimplemented rather than mapped to the wrong endpoint or a fabricated one (see
  `docs/systems/system2/DASHBOARD_READINESS.md` §9.2 for why each one specifically isn't safe to
  wire yet). Verified: full local success-path testing of all five real actions (pause, resume,
  toggle-strategy, emergency-stop, emergency-stop-clear) with exact frontend payloads — all
  correctly authenticate, enforce RBAC-before-CONFIRM-token ordering, and mutate
  `reports/control_state.json` with correct actor attribution. Live production verification limited
  to auth/rejection paths only (401 unauthenticated, 403 wrong CONFIRM token, state confirmed
  unchanged) — the actual mutation path was deliberately not exercised against production, since it
  writes to the same control-state file the live trading runner reads every tick; full regression
  suite (140 tests) passed throughout, `smc-demo-runner.service` confirmed unaffected. Also
  reviewed, not rotated: `SVOS_OPERATOR_TOKEN` is confirmed a placeholder value (rotation plan
  documented, execution requires explicit owner approval per this repo's secrets boundary). Full
  detail: `docs/systems/system2/DASHBOARD_READINESS.md` §9.

## Test results (this milestone)

Real-Time Operations Layer pass: full suite 1591 passed, 29 failed, 4 skipped. Confirmed via
`git stash` that the same 29 failures occur with this milestone's changes removed entirely
(`tests/database/test_db_preflight.py`, `tests/svos/test_lifecycle_authority.py`,
`tests/svos/test_pipeline.py`, `tests/core/test_smc_ob_fvg_session_adapter.py` — none touched by
this work). Everything touched by this milestone (`dashboard/events.py`, `dashboard/rbac.py`,
`dashboard/status_server.py`, `dashboard/auth.py`, `core/trade_journal_db.py`) passes: 21/21 in
the three dashboard test files plus the new `summary_by_strategy` test.

Prior milestone (Phase 1-3/Sprint 2.x) results: 1530 passed, 8 failed (pre-existing, unrelated), 4
skipped — see history above for detail.

## Production readiness estimate

Still **not** a Production Candidate; `LIVE_TRADING=false`/`DEMO_ONLY=true` unaffected throughout.
This milestone closes the single most consequential item from `SYSTEM2_MASTER_PLAN.md`'s risk list
(the dead risk-feedback-loop), lands Sprints 2.1-2.3 (canonical pipeline, legacy-runner block,
durable Postgres operations recording), fixes the deployed runner so it is, for the first time,
actually trading ST-A2 in demo rather than crash-looping on an unapproved strategy, and confirms +
partially cleans up the execution architecture (one canonical lifecycle, one dead 411-line cluster
removed, two dormant-but-real stacks documented and left for a future scope decision). Remaining
before "Production Candidate": full `run_portfolio.py` retirement or feature-port decision, durable
*risk/portfolio* ledger, dashboard **frontend** wiring (backend now exposes real data — see Phase 5
above — but no frontend consumes it yet), WebSocket/event system, auth/RBAC, monitoring dashboards,
extended demo validation, and the safety-critical test suite this all implies — each remains a
substantial, separately-scoped piece of work.

## Next implementation milestones (in order)

1. **~~Real-Time Operations Layer~~ — backend/transport landed 2026-07-04, browser-usable and
   credentialed 2026-07-05.** `/ws` + the 5 new REST endpoints are live and RBAC-gated; the Gai
   dashboard's `SocketContext.tsx` mints a ticket and subscribes on load, now using a real operator
   session (`OperatorLogin.tsx`) instead of an unset placeholder credential — verified against the
   live production process. Complete for this milestone's scope.
2. **~~Authentication & RBAC~~ — landed 2026-07-04 for the FastAPI backend, frontend-integrated
   2026-07-05.** `dashboard/rbac.py` gates `/api/emergency-stop[/clear]`, all `/api/control/*`
   routes, `GET /api/ws-ticket`, and `/ws` itself. `OperatorLogin.tsx` now provides the missing
   frontend login/session UI — validates against the real backend, stores the session, and every
   mutation call sends real `Authorization`/`X-SVOS-Actor` headers. **Remaining:** the Flask
   backend's own mutation routes (position close/protect/cancel, activation) still rely on
   `dashboard/auth.py`'s `require_operator` alone without a CONFIRM token on several of them
   (`SYSTEM2_MASTER_PLAN.md`'s Authentication row) — that backend isn't deployed, so no live
   exposure, but tracked for if it ever is. Also found there (not fixed, same reason): a bearer
   caller can still self-declare `X-SVOS-Role` in `dashboard/auth.py`, the exact gap
   `dashboard/rbac.py` already closed.
3. **~~Operator Controls~~ — backend landed 2026-07-04, frontend wired 2026-07-05.**
   `/api/control/{pause,resume,close-all,toggle-strategy}` and `/api/emergency-stop[/clear]` are
   RBAC + CONFIRM-token gated. `SocketContext.tsx`'s action functions now call the real endpoints
   (previously targeted nonexistent mock-server routes) with an explicit confirm dialog before
   sending. **Remaining:** no UI button exists yet for Close All or Emergency Clear (both wired at
   the context layer, verified directly against the backend, just not exposed on a component) —
   see `docs/systems/system2/DASHBOARD_READINESS.md` §9.5.
4. **Monitoring & Observability** — feed `/api/v1/production/health` from the actual tick loop
   (still a heartbeat-file gap), add freshness timestamps to dashboard widgets, surface
   `/api/operations/events` in the console-logs panel (backend ready, not yet consumed by the LIVE tab).
5. **Extended Multi-Day Demo Validation** — longer-horizon observation of the now-actually-trading
   `smc-demo-runner.service` before any Production Candidate review.
6. **Production Candidate Review** — gated on the checklist in `SYSTEM2_MASTER_PLAN.md`'s
   "Production Candidate Definition of Done" section.
7. **Execution Pipeline Consolidation, Tier 2/3** — `run_portfolio.py`'s full retirement or
   feature-port decision, and the `bot.py`/`adaptive/run_shadow.py` disposition (both deferred,
   `PIPELINE_CONSOLIDATION_PLAN.md`), remain open, lower priority than the above.

**Cross-cutting, started now rather than deferred to the end (owner feedback 2026-07-04):**
`docs/vps/OPERATOR_RUNBOOK.md` — daily checks, monitoring routines, broker-disconnect/VPS-reboot/
risk-trigger/emergency-stop response, deployment rollback, backup restore. Complements this
document's Definition of Done; update it alongside each remaining milestone above, not only at the
end. Every remaining sprint should sync this file, `SYSTEM2_MASTER_PLAN.md`, `STATUS.md`, and
`ROADMAP.md` at both its start and its end (owner's stated methodology going forward).

Milestone work itself not started in this pass; sequencing/doc updates only, per explicit
instruction not to begin implementation ahead of a commissioned sprint.

## Known cross-cutting risks

Per `SYSTEM2_MASTER_PLAN.md`: two competing execution engines still exist (decision made to
consolidate, not yet done); restart recovery still has no broker reconciliation; dashboard/API/
strategy-loader duplication is unresolved. Risk widgets in any dashboard work must still be
labeled "configured limits," not "live enforced state," until the durable ledger (not just the
JSON persistence landed this milestone) is in place.

## Production Hardening pass — 2026-07-06

Four of five phases landed and verified live; one implemented-but-not-deployed for a documented,
deliberate reason. Full detail: `docs/systems/system2/DASHBOARD_READINESS.md` §10-12.

- **Shared Broker Runtime (done)**: dashboard no longer opens a second MetaAPI session for
  account/positions/market-watch/chart data — reads the deployed runner's own state files
  instead. Fixes the previously-documented `brokerConnection.status: DEGRADED` defect (now
  honestly `CONNECTED`). 7 new tests; old threaded/caching RPC apparatus removed (also
  eliminated a latent thread-exception bug it had). Manual close/modify/cancel actions
  deliberately still use their own connection — routing writes through the runner needs an
  IPC channel, out of scope.
- **Monitoring & Observability (done)**: new `GET /api/system2/monitoring` — platform health,
  broker, runner uptime, database, risk engine, WebSocket subscriber count, CPU/memory/disk,
  execution latency (honestly `null`, zero trades to measure from). 4 new tests.
- **Telegram Alert Persistence (implemented + tested, NOT yet deployed)**: every alert now
  persists into the existing `operations.execution_event` table before sending (including
  suppressed/unconfigured cases) — same table `/api/operations/events` already reads, no new
  API needed. 13 new tests. **Not active**: requires restarting `smc-demo-runner.service`,
  which currently has ~77 uncommitted lines of a different session's unreviewed
  `RiskPortfolioStore` work loaded — deliberately not restarted to avoid deploying that
  alongside this.
- **Configuration Hardening (reviewed)**: `SVOS_OPERATOR_TOKEN` reconfirmed a placeholder
  (shape-checked, never printed); all other reviewed credentials look real/generated. Rotation
  plan documented, not executed (needs owner approval).
- **Extended Demo Validation (honest snapshot, not a multi-day report)**: ~2 days uptime, 0
  restarts, 21 reconnects, 119 `[ERROR]` entries (all MetaAPI subscription timeouts, handled
  gracefully), 0 trades executed. At the time this pass was written, 58 non-terminal
  `ExecutionRecord`s were newly flagged; SYS2-T014 later root-caused and resolved that
  reconciliation gap without changing the execution state machine.

## SYS2-T014 — Periodic execution-record reconciliation (2026-07-07, PR #27)

**Landed:** `ExecutionRecord`s that reached `BROKER_ACKNOWLEDGED` (successful order placement) or
`RECOVERY_PENDING` (ambiguous timeout) previously stayed stuck until the process next restarted,
since `execution/startup_recovery.py::reconcile_pending_executions()` was only ever invoked once
at startup (risk-register #14, root-caused via
`docs/audit/execution-record-nonterminal-investigation.md`). The same, unmodified function now
also runs mid-session from the tick loop (`scripts/run_st_a2_demo.py::_reconcile_periodic`),
gated by `RECONCILE_EVERY_N_TICKS` (cadence, default 5 ticks) and `RECONCILE_MIN_PENDING_AGE_S`
(minimum age before resolving an ambiguous record, default 60s, so it can't race an order still
in flight at the broker). Periodic reconciliation now alerts via Telegram on
recovered/lost outcomes, matching the startup path's existing behavior (CodeRabbit finding on
PR #27, fixed same-day).

**Scope discipline:** no changes to `execution/trade_manager.py`, `execution/execution_state.py`'s
state machine, or any database schema — confirmed via architecture audit before merge. Full
design/implementation/audit trail: `docs/systems/system2/SYS2-T014-DESIGN.md`.

**Tests:** 4 new age-gate cases (`tests/execution/test_startup_recovery.py`), new
`tests/scripts/test_run_st_a2_demo_periodic_reconciliation.py` (periodic-execution policy,
duplicate-reconciliation idempotency, timeout-ambiguity preservation, startup-signature
regression lock). CI's unit-tier command passing at the merged tip: 241/241.

**Follow-ups (tracked separately, not blocking):** SYS2-T015 (add `tests/scripts/` to the CI unit
test matrix — a pre-existing gap predating this task), SYS2-T016 (differentiate periodic-
reconciliation errors from tick errors in logging), SYS2-T017 (document the tick-interval /
reconciliation-cadence coupling as an operational constraint), SYS2-T018 (integration-level test
for orphan-suppression during the age-gate window at the wiring level).
