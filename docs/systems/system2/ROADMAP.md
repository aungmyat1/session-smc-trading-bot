# System 2 — Roadmap

- Last updated: 2026-07-04
- Platform-level roadmap (execution engine consolidation, risk ledger, restart recovery,
  observability): `SYSTEM2_MASTER_PLAN.md` Phases 1-4 at the repo root — authoritative, status
  summarized below, not duplicated in full.

## Platform phases (SYSTEM2_MASTER_PLAN.md)

| Phase | Scope | Status |
|---|---|---|
| 1 | Close safety-critical disconnects (risk feedback loop, durable state, restart recovery) | **Done for the deployed runner** — risk-halt feedback, JSON-persisted state, and real broker-truth startup recovery all wired and tested (2026-07-04); durable *risk/portfolio* ledger still open |
| 2 | Resolve canonical/legacy execution split | **In progress** — Sprint 2.1 (`CanonicalExecutionPipeline` ported into the deployed runner) and Sprint 2.2 (`run_portfolio.py` blocked from accidental start) landed 2026-07-04; broker-truth reconciliation wiring for `run_portfolio.py` and full retirement/feature-port decision remain not started |
| 2.3 | Transactional persistence | **Done** — `operations.*` Postgres schema (migration 004) applied, ORM added, best-effort recorder wired into the deployed runner's pipeline events and recovery checkpoints (2026-07-04) |
| 2.x | Deployment fix: `smc-demo-runner.service` | **Done, 2026-07-04** — was crash-looping since creation on an unapproved strategy name, never actually running anything in production; fixed to run `ST-A2`, verified stable (0 restarts, broker connected, clean tick cycles). See `docs/systemd/SMC_DEMO_RUNNER_ANALYSIS.md` |
| 2.y | Execution Pipeline Consolidation, Tier 1 | **Done, 2026-07-04** — one canonical lifecycle confirmed and documented; 411-line dead "Production Platform v2" cluster removed; two dormant-but-real stacks (`bot.py`, `adaptive/run_shadow.py`) documented, deliberately not touched (Tier 3, owner decision needed). See `EXECUTION_PIPELINE_INVENTORY.md`, `CANONICAL_EXECUTION_PIPELINE.md`, `PIPELINE_CONSOLIDATION_PLAN.md` |
| 3 | Consolidate dashboard/API/strategy-loader duplication | **Backend done, frontend integrated, deployed, and authenticated (LIVE tab)** — 8 `/api/operations/*` endpoints (Phase 5) plus `/api/new-dashboard/live-state` (Phase 6) now on `status_server.py`, the only deployed backend; the Gai dashboard's LIVE tab consumes the latter end-to-end, browser-verified (2026-07-04). **Landed 2026-07-05**: the built SPA is served in production at `GET /new-dashboard/` (+ `/assets`); a real operator login (`OperatorLogin.tsx`) plus repointed Pause/Resume/Toggle-Strategy/Emergency-Stop/-Clear controls close the Operator Controls gap this row previously listed as unwired (Close-All still has no UI button — see `DASHBOARD_READINESS.md` §9.5). `app.py`/`live_app.py` themselves not yet retired; SVOS/Suggestions tabs and (activate/risk-controls/reconnect/force-close) remain unwired — each deliberately, per §9.2, since none has a safe real backend equivalent yet |
| 4 | Observability and deployment hygiene | **Partial** — `operations.*` Postgres tables (Sprint 2.3) have a read path (Phase 5), now also a real-time push path (`/ws`, below), but the LIVE tab doesn't surface either yet (console-logs panel still empty); `/api/v1/production/health` heartbeat-file gap remains. **Landed 2026-07-05**: fail-closed readiness validation (`GET /api/system2/readiness`, `GET /system2/readiness`) — 10-point checklist covering DB reachability, runtime authority, strategy approval, risk firewall, broker, emergency stop, incidents, heartbeat, duplicate-runtime, reconciliation. Tested (24 unit/API tests), documented (`docs/systems/system2/DASHBOARD_READINESS.md`), **not yet deployed** to `live-dashboard.service` — code is committed-ready but the running process hasn't been restarted to load it |
| 5 | Real-Time Operations Layer (backend) | **Done end-to-end, 2026-07-05** — `dashboard/events.py` (unified event schema + in-process broadcaster/poller), `GET /ws`, and 5 new REST endpoints landed in `status_server.py`; no Redis, no new services, per owner decision. Load-tested: 0 event loss, 25 concurrent subscribers. Frontend connects via a short-lived signed ticket (`GET /api/ws-ticket`) since browsers can't send the header-based auth `/ws` originally required — fixed, not weakened (header auth still works as a fallback) — and now has a real operator credential to present, via the Authentication row below. Verified live: authenticated connection, replay rejection, real event delivery, reconnection |
| 6 | Authentication & RBAC (FastAPI backend) | **Done, 2026-07-04; frontend-integrated 2026-07-05** — `dashboard/rbac.py` reuses `dashboard/auth.py`'s role model; gates `/api/emergency-stop[/clear]`, all `/api/control/*`, `GET /api/ws-ticket`, and `/ws`. `OperatorLogin.tsx` (new) closes the frontend login-UI gap this row previously listed — validates a token/actor pair against the real backend, sessions via `sessionStorage`, every mutation call now sends real auth headers. Flask backend's other mutation routes remain open (that backend isn't deployed). Found, not fixed (same reason): `dashboard/auth.py` still lets a bearer caller self-declare `X-SVOS-Role` — the exact gap `dashboard/rbac.py` already closed |
| 7 | Operator Controls (backend) | **Done, 2026-07-04; frontend wired 2026-07-05** — `/api/control/{pause,resume,close-all,toggle-strategy}`, RBAC + CONFIRM-token gated, delegating to the existing `activate_emergency_stop`/`clear_emergency_stop` state machine. `SocketContext.tsx` now calls pause/resume/toggle-strategy/emergency-stop/-clear for real; no UI button yet for close-all |
| 8 | Shared Broker Runtime | **Done, 2026-07-06** — `dashboard/live_dashboard_service.py` reads the deployed runner's own state files instead of opening a second MetaAPI session. Fixes `brokerConnection.status: DEGRADED` (now `CONNECTED`, verified live). Write actions (close/modify/cancel) intentionally still use their own connection |
| 9 | Monitoring & Observability | **Done, 2026-07-06** — `GET /api/system2/monitoring`: platform health, broker, runner, database, risk engine, WebSocket subscribers, CPU/memory/disk, execution latency (honestly null pending real trade data) |
| 10 | Telegram Alert Persistence | **Implemented + tested, not deployed, 2026-07-06** — `monitoring/telegram.py` persists every alert into `operations.execution_event` before sending. Blocked from going live by another session's unreviewed WIP already loaded in `smc-demo-runner.service`'s code — restarting the runner would deploy both at once, deliberately not done |
| 11 | Configuration Hardening | **Reviewed, 2026-07-06** — no new placeholder secrets found beyond the already-known `SVOS_OPERATOR_TOKEN`; rotation plan documented, not executed (needs owner approval) |
| 12 | Extended Demo Validation | **Started, not complete** — ~2 days real uptime (0 restarts), but genuine multi-day validation under real order flow hasn't happened (0 trades executed yet). 119 MetaAPI subscription-timeout errors and 58 unexplained non-terminal `ExecutionRecord`s found, not yet root-caused |
| 13 | Infrastructure Hardening & MT5 Integration Prep | **Blocked, 2026-07-07** — `ADR-0011`/`ADR-0012` (connector + hosting strategy), storage governance tooling, and supporting audits landed 2026-07-06. Provisioning attempts on `auto-trade-vps` (2026-07-06/07) found: (1) Wine is non-functional on this host, root cause not determined after a structured 10-hypothesis investigation (`docs/audit/wine-investigation-report.md`); (2) disk cannot reach the 75% capacity target via cleanup alone — ~15G is structurally protected (`docs/audit/capacity-plan.md` Phase 5B). One approved cleanup (`~/.mt5-terminal`, 900M) recovered disk from a critical 90% (hit during the failed attempt) back to 87%. `ADR-0012`'s dedicated-node recommendation now carries stronger evidence (2026-07-07 update) as the likely path past both blockers. Zero production impact across all attempts — all 6 monitored services verified active throughout |

### Next implementation milestones (in order)

1. **Real-Time Operations Layer, frontend integration** — backend/transport is done (Phase 5 row
   above); no Gai dashboard widget subscribes to `/ws` yet. See `STATUS.md` for the full event
   taxonomy landed.
2. **Authentication & RBAC, remaining scope** — FastAPI backend done (Phase 6 row above); still
   needed: a frontend login/session UI, and porting the Flask backend's other mutation routes
   (position close/protect/cancel, activation) onto the same RBAC + CONFIRM-token pattern.
3. **Operator Controls, frontend integration** — backend done (Phase 7 row above);
   `SocketContext.tsx`'s action functions (`pauseTrading`, `triggerKillSwitch`, `updateRiskControls`,
   etc.) need to be repointed at the real `/api/control/*` endpoints; needed before the "Capital Risk
   Policies"/"Deploy Strategy Contract" panels can become live-editable.
4. **Monitoring & Observability** — feed `/api/v1/production/health` from the real tick loop; add
   freshness timestamps to every widget; wire `/api/operations/events` into the console-logs panel.
5. **Extended Multi-Day Demo Validation**, then **Production Candidate Review** (checklist:
   `SYSTEM2_MASTER_PLAN.md` Definition of Done), then **Execution Pipeline Consolidation Tier 2/3**
   (`run_portfolio.py`, `bot.py`/`adaptive/run_shadow.py` dispositions) — all lower priority than
   the above per the owner-prioritized sequence.

**Cross-cutting, started now (owner feedback):** `docs/vps/OPERATOR_RUNBOOK.md` — begun alongside
this sprint's documentation sync rather than deferred to Production Candidate Review. Every
remaining sprint should sync this file plus `SYSTEM2_MASTER_PLAN.md`/`STATUS.md`/`ROADMAP.md` at
both the start and the end of the work, not just the end.

## Dashboard integration workstream

This file also tracks the **dashboard integration workstream** roadmap. Full detail per phase:
`docs/dashboard/DASHBOARD_IMPLEMENTATION_PLAN.md`.

### Dashboard integration phases

| Phase | Scope | Status |
|---|---|---|
| 0 | De-risk fabricated-data surfaces (`SvosQuantLab`, `SuggestionsTab`, Manual Sandbox mode) | Not started |
| 1 | Backend API layer | **Partial** — `GET /api/new-dashboard/live-state` real-data endpoint landed; frontend not yet repointed to it |
| 2 | WebSocket integration | **Landed 2026-07-05** — `SocketContext.tsx` mints a ticket (`GET /api/ws-ticket`) and subscribes to `/ws`, verified against live production (auth, reconnection, real event delivery), now using a real operator session rather than an unset credential. Polling retained as automatic fallback |
| 3 | Authentication | **Landed 2026-07-05** — `OperatorLogin.tsx` (new component) provides a minimal login form, validates against the real backend, stores the session in `sessionStorage`, and every mutation/`ws-ticket` call sends real `Authorization`/`X-SVOS-Actor` headers via a new `authenticatedFetch()` wrapper. A 401 auto-triggers logout. No new auth system — reuses `dashboard/rbac.py` entirely |
| 4 | Live account status | Backed by Phase 1's adapter already; no frontend wiring yet |
| 5 | Positions | Not started (frontend-side) |
| 6 | Orders | Not started — must include CONFIRM-token contract |
| 7 | Trade history | Not started (frontend-side); backend data available via Phase 1 endpoint |
| 8 | Strategy runtime | Not started — must reconcile `strategy_catalog.yaml` vs `strategy_portfolio.yaml` divergence |
| 9 | Risk monitor | Not started — must label as "configured," not "live enforced," per platform risk-ledger gap |
| 10 | Health monitor | Not started — quick win available: `SystemHealth.tsx` is finished but unimported |
| 11 | Alert center | Not started — new panel |
| 12 | Logs | Not started |
| 13 | Emergency stop | **Landed 2026-07-05** — `triggerKillSwitch`/`clearEmergencyStop` reuse the exact CONFIRM-token strings `/api/emergency-stop[/clear]` require, gated by an explicit `window.confirm()` and a real operator session; `clearEmergencyStop` has no UI button yet (context-layer only, verified directly against the backend) |
| 14 | Deployment status | Not started — new panel; answers "which runner is actually live" |
| 15 | Analytics | Not started (frontend-side); backend data available via Phase 1 endpoint |
| 16 | Settings | Not started — lowest priority |

## Execution/SVOS Governance Decoupling (Scope 2, done 2026-07-06)

Tracks the execution-hot-path decoupling from SVOS/research code, independent of the
platform-phase and dashboard tables above.

**Previous architecture:** `execution/governance_guard.py` (or its equivalent
deployment-gate logic) had a live dependency surface reaching into `svos.*`/`research.*`
governance/registry services on the execution hot path — the same process making
ALLOW/DENY/WARN runtime decisions could import research-side code.

**Current architecture:**
- `execution/governance_guard.py` has zero `svos.*`/`research.*` imports (enforced by
  `tests/execution/test_governance_guard_no_svos_import.py`, which asserts both on AST
  imports and on raw source strings).
- The ALLOW/DENY/WARN decision is driven exclusively by
  `core.strategy_registry.can_deploy_strategy()` / `get_strategy_manifest()` — a
  catalog-backed (`config/strategy_catalog.yaml`), SVOS-free module. Shadow-mode behavior
  (`WARN_SHADOW_GOVERNANCE_INCOMPLETE`) is unchanged.
- `execution/governance_snapshot.py` defines `GovernanceSnapshot`, a frozen, pure-data
  audit projection (`strategy_name`, `latest_version`, `evidence_count`,
  `decision_count`, `approval_count`, `latest_approval`). It never participates in the
  deployment decision — deliberately excludes any status/approval/gating field that
  could tempt a decision branch.
- `execution/governance_snapshot_provider.py` (`GovernanceSnapshotProvider`) is the sole
  SVOS-free reader: it loads `artifacts/svos/strategy_snapshots.json` (schema: a dict of
  `strategy_name -> {latest_version, evidence_count, decision_count, approval_count,
  latest_approval}`, optionally wrapped under a top-level `"strategies"` key) and returns
  `None` on any missing/malformed data. A missing snapshot degrades gracefully to
  zero/empty defaults in `evidence_snapshot` — it never denies or changes `allowed`.
  Since Scope 3 (below), it can also read the same shape extracted from a verified
  package's `governance_snapshot.json` member (preferred over the loose file when a
  `package_path` is supplied and yields data); the loose-file-only default behavior is
  unchanged for callers that don't pass `package_path`.
- **Manual bridge:** `scripts/export_governance_snapshot.py` is the only place that still
  imports `svos.governance.service.GovernanceService` /
  `svos.registry.service.StrategyRegistryService`. It runs out-of-band (manual, no
  event-driven writer yet) and writes the JSON artifact execution reads.

**Rationale:** execution must be able to start, evaluate strategies, and run under
`LIVE_TRADING=false`/`DEMO_ONLY=true` even if SVOS research services are unavailable,
broken, or mid-migration — research never trades, and now execution can never
accidentally import into research either. Audit richness (evidence/decision/approval
counts) is preserved as best-effort metadata rather than a hard dependency.

**Validated 2026-07-06:** snapshot export runs cleanly against the current
`config/strategy_catalog.yaml` (8 strategies); `StrategyExecutionGuard.evaluate()`
produces identical `allowed`/`reason_code`/`decision_source` with the snapshot file
present vs. renamed-away (only `evidence_snapshot` counts change, falling back to
zero/empty); no exceptions in either case. Full `tests/execution/` suite (124 tests)
passes.

## Approved Package Contract — governance snapshot (Scope 3, done 2026-07-06)

Extends the existing `shared/strategy_package.py` `strategy-package/v2` contract (not a
new deployment mechanism) so a built package carries its own governance snapshot instead
of requiring a separate loose-file bridge at consumption time.

- `governance_snapshot.json` is now a **required** archive member
  (`shared.strategy_package.REQUIRED_MEMBERS`), and — since `SIGNED_MEMBERS` is derived
  from `REQUIRED_MEMBERS` — it is automatically a signed member too, with no new signing
  code. Its content shape matches the loose-file export:
  `{"strategies": {strategy_name: {latest_version, evidence_count, decision_count,
  approval_count, latest_approval}}}`.
- `shared.strategy_package.RUNTIME_API_VERSION` bumped `system2-runtime/v1` ->
  `system2-runtime/v2` to signal this schema change. `validate_canonical_package`'s
  existing runtime-api-version mismatch rejection is the enforcement mechanism — no
  second compatibility mechanism was added. `schemas/strategy-package-v2.schema.json`
  updated to match (`runtime_api_version` const, `members.minProperties` 6 -> 7).
- Computation is shared, not duplicated: `svos/governance/snapshot.py` provides
  `compute_strategy_governance_snapshot()` (single strategy) and
  `compute_all_governance_snapshots()` (all catalog strategies). Both
  `scripts/export_governance_snapshot.py` (loose-file dev path, behavior unchanged) and
  `svos/deployment/service.py`'s `DeploymentStatusService.build_strategy_package`
  (packaged path) call the same helper.
- Lifecycle: **built by SVOS** (System 1) at package-build time — `build_strategy_package`
  is gated on `manifest.approved is True and current_stage == "PRODUCTION_APPROVAL"`, so
  the governance data is always available when a package is legitimately built. **Consumed
  read-only by execution** (System 2) via `GovernanceSnapshotProvider`, which now accepts
  an optional `package_path` and prefers a packaged snapshot over the loose file when both
  are available — the loose-file path is untouched for strategies without a built package.
  This does not touch `execution/governance_guard.py`'s ALLOW/DENY/WARN decision logic at
  all; a missing/malformed snapshot from either source still degrades to `None` and never
  changes `allowed`.
- **Compatibility:** no strategy currently holds `PRODUCTION_APPROVAL`, so no package has
  ever been built and there is nothing to migrate. A future real approved-strategy package
  build will simply include `governance_snapshot.json` from the start; there is no
  v1-package upgrade path (v1 archives are rejected outright by the v2 validator's
  `runtime_api_version` check, which is intentional — packages are immutable, evidence-backed
  artifacts, not something patched in place).

**Remaining work (Scopes 4-6, not started):**
- Scope 4: Event-driven snapshot writer (replace the manual
  `scripts/export_governance_snapshot.py` invocation with a triggered/scheduled writer).
- Scope 5: CI forbidden-import rule generalizing
  `test_governance_guard_no_svos_import.py`'s pattern beyond a single file.
- Scope 6: Database separation between SVOS registry/governance storage and execution's
  operational tables.
- Package signing and deployment-pipeline redesign remain explicitly out of scope until
  a future, separately-approved task.

## Next milestone

Repoint `New Dashborad/Gai dashboard/src/context/SocketContext.tsx`'s REST-fallback fetch from
`/api/status` to `/api/new-dashboard/live-state`, build the Vite app, and serve it from
`dashboard/app.py` at a new static path (do not overwrite the existing `/new-dashboard/` route
without a separate, explicit decision — see gap analysis's cutover note). Verify in a browser
per this repo's UI-change verification requirement before marking done.
