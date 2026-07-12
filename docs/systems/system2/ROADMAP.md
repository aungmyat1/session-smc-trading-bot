# System 2 — Roadmap

- Last updated: 2026-07-12
- **Feature Expansion: FROZEN as of 2026-07-07** (SYS2-T014 closure) — new execution
  features, broker integrations, execution abstractions, and dashboard expansion require a
  new, explicitly-scoped milestone decision. Bug/security/reliability fixes (and production
  blockers) remain allowed.
  Rationale and lift criteria: `docs/governance/releases/SYS2-T014-CLOSURE.md`.
  (The Emergency-Stop RiskFirewall row below is a reliability/safety fix — permitted under
  this freeze, not a feature-expansion exception.)
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
| 2.z | Emergency-Stop RiskFirewall (PR #24) | **Done, 2026-07-05** — `production.engine.EmergencyStopRiskGate` closes the "RiskFirewall — out of scope for Sprint 2.1" gap for the deployed runner: wired into `run_st_a2_demo.py`'s `CanonicalExecutionPipeline`, rejects any submission at the pipeline level while `control_state.json`'s emergency stop is active (defense-in-depth on top of `_tick()`'s existing early-return). Deliberately does not touch `run_portfolio.py` — that stays gated on the Tier 2/3 retirement/feature-port decision above. See `docs/github/PR22_FIX_REPORT.md` for the related resume-scoping fix (`emergency_stop.source` tracking) this builds on. |
| 3 | Consolidate dashboard/API/strategy-loader duplication | **Backend done, frontend integrated (LIVE tab)** — 8 `/api/operations/*` endpoints (Phase 5) plus `/api/new-dashboard/live-state` (Phase 6) now on `status_server.py`, the only deployed backend; the Gai dashboard's LIVE tab consumes the latter end-to-end, browser-verified (2026-07-04). `app.py`/`live_app.py` themselves not yet retired; SVOS/Suggestions tabs and Operator Controls remain unwired |
| 4 | Observability and deployment hygiene | **Partial** — `operations.*` Postgres tables (Sprint 2.3) have a read path (Phase 5), now also a real-time push path (`/ws`, below), but the LIVE tab doesn't surface either yet (console-logs panel still empty); `/api/v1/production/health` heartbeat-file gap remains |
| 5 | Real-Time Operations Layer (backend) | **Done, 2026-07-04** — `dashboard/events.py` (unified event schema + in-process broadcaster/poller), `GET /ws`, and 5 new REST endpoints landed in `status_server.py`; no Redis, no new services, per owner decision. Load-tested: 0 event loss, 25 concurrent subscribers. Frontend integration not started |
| 6 | Authentication & RBAC (FastAPI backend) | **Done, 2026-07-04** — `dashboard/rbac.py` reuses `dashboard/auth.py`'s role model; gates `/api/emergency-stop[/clear]` and all `/api/control/*`. Flask backend's other mutation routes and any frontend login UI remain open |
| 7 | Operator Controls (backend) | **Done, 2026-07-04** — `/api/control/{pause,resume,close-all,toggle-strategy}`, RBAC + CONFIRM-token gated, delegating to the existing `activate_emergency_stop`/`clear_emergency_stop` state machine. Frontend wiring (`SocketContext.tsx`) not started |
| SYS2-T014 | Periodic execution-record reconciliation | **Done, 2026-07-07 (PR #27)** — `ExecutionRecord`s stuck at `BROKER_ACKNOWLEDGED`/`RECOVERY_PENDING` (risk-register #14) previously only resolved at process startup; `reconcile_pending_executions()` (unmodified) now also runs mid-session on a configurable cadence with a minimum pending-age gate. No execution-state-machine, `TradeManager`, or database changes. Design record: `docs/systems/system2/SYS2-T014-DESIGN.md`. Follow-ups tracked as SYS2-T015–T018 (CI matrix coverage, logging clarity, scheduler docs, integration test), not blocking |

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
| 2 | WebSocket integration | Deferred by design — polling retained, per `SYSTEM2_MASTER_PLAN.md`'s existing stance; revisit if trade frequency/headcount increases |
| 3 | Authentication | Not started — frontend has no auth headers wired to `dashboard/auth.py`'s scheme |
| 4 | Live account status | Backed by Phase 1's adapter already; no frontend wiring yet |
| 5 | Positions | Not started (frontend-side) |
| 6 | Orders | Not started — must include CONFIRM-token contract |
| 7 | Trade history | Not started (frontend-side); backend data available via Phase 1 endpoint |
| 8 | Strategy runtime | Not started — must reconcile `strategy_catalog.yaml` vs `strategy_portfolio.yaml` divergence |
| 9 | Risk monitor | Not started — must label as "configured," not "live enforced," per platform risk-ledger gap |
| 10 | Health monitor | Not started — quick win available: `SystemHealth.tsx` is finished but unimported |
| 11 | Alert center | Not started — new panel |
| 12 | Logs | Not started |
| 13 | Emergency stop | Not started — must reuse exact CONFIRM-token strings already used by `/api/emergency-stop` |
| 14 | Deployment status | Not started — new panel; answers "which runner is actually live" |
| 15 | Analytics | Not started (frontend-side); backend data available via Phase 1 endpoint |
| 16 | Settings | Not started — lowest priority |

## Next milestone

Repoint `New Dashborad/Gai dashboard/src/context/SocketContext.tsx`'s REST-fallback fetch from
`/api/status` to `/api/new-dashboard/live-state`, build the Vite app, and serve it from
`dashboard/app.py` at a new static path (do not overwrite the existing `/new-dashboard/` route
without a separate, explicit decision — see gap analysis's cutover note). Verify in a browser
per this repo's UI-change verification requirement before marking done.
