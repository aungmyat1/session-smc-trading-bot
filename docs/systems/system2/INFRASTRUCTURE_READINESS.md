# System 2 — Infrastructure Readiness Check

Date: 2026-07-04
Status: Assessment only
Authoritative platform document: `SYSTEM2_MASTER_PLAN.md` (repo root) — this file assesses
*infrastructure* readiness for the next milestone against it; it does not re-derive platform status
from scratch (see that document's own Phase 1-4 tracking, current through Sprint 2.3 as of this pass).

---

## 1. What has actually landed (as of this session)

- **Phase 1 (Safety-Critical Disconnects):** risk-halt feedback loop, JSON-backed risk/portfolio
  persistence, and real broker-truth startup recovery are all wired into the deployed runner
  (`scripts/run_st_a2_demo.py`) and covered by tests, including a full end-to-end
  open→close→restart→recover→resume test.
- **Sprint 2.1:** order placement now flows through `production.engine.CanonicalExecutionPipeline`
  in the deployed runner (additive, `AllowAllRiskGate` since upstream checks already decide).
- **Sprint 2.2:** `run_portfolio.py` (the undeployed, architecturally "canonical" runner) is
  blocked from starting by default — can no longer be run by accident.
- **Sprint 2.3:** the `operations.*` Postgres schema (migration 004) is now applied and has an ORM
  layer; `execution/operations_recorder.py` durably logs every pipeline event, intent, risk
  decision, order record, and recovery checkpoint to Postgres, best-effort, alongside the existing
  JSONL log.
- **Dashboard (parallel workstream, this same day):** `dashboard/live_state_adapter.py` +
  `GET /api/new-dashboard/live-state` assembles a real-data payload for the New Dashboard SPA, with
  unavailable fields explicitly marked, not fabricated.

## 2. New infrastructure fact this pass changes the picture

**The deployed `smc-demo-runner.service` has never actually run ST-A2** (or any strategy) — see
`docs/systemd/SMC_DEMO_RUNNER_ANALYSIS.md`. It has been crash-looping since creation on an
unapproved, `INTAKE`-stage strategy name. This means every readiness assessment that assumed "the
deployed runner is trading ST-A2 in demo" (including this session's own Sprint 1-3 work and
`SYSTEM2_MASTER_PLAN.md`'s narrative) was accurate for the **code path**, but the **actual running
process** has not been exercising any of it end-to-end in production — only in tests. This is the
single most important infrastructure fact for readiness purposes: **there is currently no live
demo trading activity for the dashboard, monitoring, or operators to observe at all.** Fixing this
(per the Analysis doc's Replace recommendation) is a precondition for any of the milestones below
being meaningful in production, not just in tests.

## 3. Blockers by target milestone

### Dashboard integration
- **Blocked by**: (a) the crash-loop above — a dashboard wired to real data has no live data to
  show until the runner actually runs; (b) 3-backend duplication (`app.py`/`live_app.py`/
  `status_server.py`) unresolved (`SYSTEM2_MASTER_PLAN.md` Phase 3, not started); (c) the New
  Dashboard SPA frontend has not been built/deployed anywhere.
- **Not blocked**: the backend API layer itself (`live_state_adapter.py`) is real and tested; no
  infrastructure gap prevents continuing that specific track.

### WebSocket implementation
- **Not an infrastructure blocker** — this is a deliberate, already-recorded design deferral
  (`SYSTEM2_MASTER_PLAN.md`: "retain polling... revisit if trade frequency or operator headcount
  increases"). Nothing on this host prevents adding it; it's a scope decision, not a readiness gap.

### Authentication
- **Partial infrastructure exists** (`dashboard/auth.py` HMAC/CSRF/role-based auth, per
  `SYSTEM2_MASTER_PLAN.md`'s own audit) but is not applied consistently — several real mutation
  routes (activation, position close/protect/cancel) lack the CONFIRM-token pattern that
  `/api/emergency-stop` already uses. **Blocker**: a design decision on which routes need which auth
  tier, not a missing capability.

### Operator controls
- **Blocked by** the canonical/legacy execution split remaining undecided-in-practice (Sprint 2.2
  only blocked the undeployed runner from starting; the actual pipeline port/consolidation —
  Sprint 2.2's "5. move reusable logic" and Phase 2's systemd cutover — has not happened). Emergency
  stop is fully wired for the legacy runner only.

### Production monitoring
- **Materially un-blocked this session**: the `operations.*` Postgres schema (migration 004) is now
  live and being written to — this is real, durable, queryable data that did not exist before
  Sprint 2.3. **Remaining blocker**: nothing reads it yet. `/api/v1/production/health` is still fed
  by a heartbeat file the runner never writes to, not the new Postgres tables. Wiring a dashboard
  read-path to `operations.runtime`/`execution_event`/`recovery_checkpoint` is now a pure
  consumption task, not a new-capability build.

## 4. Infrastructure-level (this VPS audit's own findings) readiness factors

| Factor | State | Relevant to |
|---|---|---|
| Disk headroom | 81% used, 7.4 GiB free (`OPERATIONS_BASELINE.md`) | All milestones — adequate for now, no log retention policy enforced yet (`LOG_RETENTION_POLICY.md`, proposal only) |
| PostgreSQL health | Active, `SELECT 1` passes, `effective_cache_size` misconfigured for host RAM (`RESOURCE_OPTIMIZATION.md`) | Monitoring, dashboard — functional today, tuning recommended before adding more query load |
| Docker | Inactive, no daemon | Not required by any current System 2 component; not a blocker |
| Systemd | 0 failed units platform-wide; `smc-demo-runner.service` fixed and verified stable 2026-07-04T17:01:32Z (was crash-looping, see §2 and update below) | All milestones, per §2 above |

## 5. Readiness verdict — updated 2026-07-04 (later same day)

**Resolved**: `smc-demo-runner.service` now runs `ST-A2`, verified stable (0 restarts, broker
connected, clean 60s tick cycles, zero exceptions) since 2026-07-04T17:01:32Z — see
`SYSTEM2_MASTER_PLAN.md`'s "Deployment fix" entry. The blocker this section originally described is
closed. **Ready to proceed** on dashboard integration and operator-controls work: there is now real,
continuously-updating live (demo) data for the first time.

**Recommended next milestone, in order (unchanged from before the fix, now unblocked):**
1. ~~Resolve `smc-demo-runner.service`~~ — **done**.
2. Wire one dashboard read-path to the new `operations.*` tables (Sprint 2.3 follow-on) — small,
   additive, immediately valuable, no new infra required.
3. Then resume `SYSTEM2_MASTER_PLAN.md` Phase 2's execution-pipeline consolidation or the dashboard
   implementation plan's Phase 1 frontend wiring — both remain valid, larger next steps.
