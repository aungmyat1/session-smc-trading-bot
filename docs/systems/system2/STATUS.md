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
- **Not yet done:** the Gai dashboard frontend has not been built, deployed, or repointed at this
  new endpoint. No auth wiring, no WebSocket, no CONFIRM-token contract on its actions yet.
  Fabricated-data surfaces (`SvosQuantLab`, `SuggestionsTab`, Manual Sandbox mode) are un-gated.
  Full remaining scope: `docs/dashboard/DASHBOARD_IMPLEMENTATION_PLAN.md` Phases 0, 2-16.

## Test results (this milestone)

Full suite: 1530 passed, 8 failed, 4 skipped. All 8 failures are pre-existing and unrelated to this
milestone's changes (7 in `tests/svos/test_pipeline.py`, 1 in
`tests/core/test_smc_ob_fvg_session_adapter.py` — files not touched by this work; likely stem from
other already-uncommitted changes in this checkout, e.g. `svos/application/refinement.py`).
Everything touched by this milestone (execution/, core/portfolio_manager.py, dashboard/,
scripts/run_st_a2_demo.py and their tests) passes: 220+ tests across `tests/execution/`,
`tests/core/`, `tests/scripts/test_run_st_a2_demo_close_detection.py`, `tests/portfolio/`, plus the
full `tests/test_dashboard_app.py` suite (40 tests).

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

1. **Real-Time Operations Layer** (renamed from "WebSocket/Event Streaming," owner feedback
   2026-07-04 — scope was too price-stream-centric) — the LIVE tab now works correctly over polling
   (Phase 6), but still polls every 1.5s against `/api/new-dashboard/live-state` with no push
   mechanism. Rather than just streaming prices, this should unify every runtime event behind one
   subscription instead of the dashboard polling many endpoints: **Trading** (order created/filled,
   position opened/closed), **Strategy** (started/stopped/heartbeat/warning), **Risk** (daily-loss
   update, circuit breaker, cooldown, emergency stop), **Platform** (broker disconnect/reconnect,
   PostgreSQL reconnect, runner restart), **System** (service restart, health degraded, disk/memory
   warning). Most of these already have a durable source to stream from —
   `execution/operations_recorder.py`'s Postgres tables (Sprint 2.3) for Trading/Strategy/Risk
   events, `TelegramAlerter`'s call sites for Platform/System events (not yet persisted, see Phase 5
   note) — this is substantially a wiring/transport task, not a new-data-source task.
2. **Authentication & RBAC** — **must land before Operator Controls** (owner feedback: "little value
   in start/stop actions if any user can invoke them"). Apply the CONFIRM-token pattern consistently
   across all mutation-class dashboard endpoints, not just `/api/emergency-stop`; no frontend login
   exists yet either (`dashboard/auth.py` has no session UI wired to it).
3. **Operator Controls** (Start/Stop/Pause/Resume/Emergency Stop) — `SocketContext.tsx`'s action
   functions (`pauseTrading`, `triggerKillSwitch`, `updateRiskControls`, etc.) all target endpoints
   that don't exist on the deployed backend yet; building these, **on top of the authentication
   framework from step 2**, is what "Capital Risk Policies"/"Deploy Strategy Contract" panel
   actually needs to become live-editable rather than display-only.
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
