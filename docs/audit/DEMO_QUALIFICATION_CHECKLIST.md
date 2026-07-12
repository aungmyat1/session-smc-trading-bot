---
Date: 2026-07-12
Author: Production Reliability / QA (Claude)
Authority: Level 8 — informational evidence. Does not supersede `docs/00_Project/DOC_AUTHORITY.md`.
Scope: Phase 7 of the System2 Completion Mission. Preparation only — per the
mission's explicit instruction, the 24-hour qualification run itself is NOT
executed here.
---

# 24-Hour Demo Qualification Checklist

## Executive Summary

This checklist prepares — but does not run — a 24-hour continuous demo
qualification window for the deployed `smc-demo-runner.service`. Each item
states what "pass" means, what evidence would demonstrate it, and its
current status based on everything verified so far in this mission and the
prior sprint. Items already verified by direct test/code-read are marked
accordingly; items that can only be verified by actually running the
24-hour window are marked "requires live run."

## Checklist

### 1. Restart survival
- **Pass condition**: the runner recovers cleanly from an OS-level restart
  (systemd `Restart=always`) without placing a duplicate order or losing
  track of an in-flight execution.
- **Evidence so far**: `smc-demo-runner.service` (`deploy/gcp-vm1/systemd/`)
  configured `Restart=always`, `RestartSec=15`. `execution/startup_recovery.py::reconcile_pending_executions()`
  runs at process start (prior sprint's correctness audit). Phase 2 (this
  mission) directly tests restart survival for duplicate-order prevention
  specifically (`test_duplicate_survives_process_restart`).
- **Status**: **Verified by test** for the duplicate-order dimension.
  **Requires live run** to confirm the full restart path end-to-end against
  a real broker connection (this sandbox cannot start the actual systemd
  service).

### 2. Recovery (crash mid-order)
- **Pass condition**: a record left `SUBMISSION_PENDING`/`RECOVERY_PENDING`
  by an interrupted run is resolved (not duplicated, not silently dropped)
  on the next reconciliation pass.
- **Evidence so far**: `reconcile_pending_executions()` — both startup and
  periodic (SYS2-T014, PR #27, already on `main`) — directly tested in the
  prior sprint's audit and this mission's Phase 3.
- **Status**: **Verified by test.**

### 3. Duplicate prevention
- **Pass condition**: no scenario (retry, restart, concurrent dispatch,
  broker reconnect) produces two broker orders for one signal.
- **Evidence so far**: Phase 2 of this mission — 21 new tests, including the
  explicit 100-duplicate-requests-→-1-order acceptance criterion.
- **Status**: **Verified by test** (pending PR #37 merge).

### 4. Broker reconnect
- **Pass condition**: a MetaAPI/Vantage connection drop and reconnect mid-session
  does not cause a duplicate order, a lost signal, or a crashed tick.
- **Evidence so far**: `execution/mt5_connector.py` connection handling
  (prior sprint's execution-readiness audit, code-verified, not just
  documented). `test_duplicate_after_broker_reconnect_same_signal` (this
  mission, Phase 2) confirms the dedup gate specifically survives a
  simulated reconnect. `TradingPermissionService` degrades gracefully on
  broker-disconnect while emergency-stopped (`test_tick_degrades_gracefully_when_broker_disconnected_during_emergency_stop`,
  PR #25).
- **Status**: **Partially verified by test** (dedup + graceful degradation
  under disconnect). **Requires live run** to observe an actual MetaAPI
  reconnect cycle against the real Vantage demo endpoint.

### 5. Dashboard
- **Pass condition**: operations endpoints (`/api/operations/*`, `/ws`)
  remain responsive and accurate throughout the window; no stale data shown
  as live.
- **Evidence so far**: 8 `/api/operations/*` endpoints load-tested (0 event
  loss, 25 concurrent subscribers) and browser-verified against real backend
  data (prior sprint). This mission did not modify `dashboard/`.
- **Status**: **Requires live run** — load-testing and one-time browser
  verification are not the same as sustained 24-hour accuracy; this is the
  one dimension with the least direct evidence of *sustained* correctness.

### 6. Risk
- **Pass condition**: circuit breakers (daily/weekly/monthly loss limits,
  consecutive-loss halt, max open positions, max trades/day) fire correctly
  from real P&L over the full window, and recover correctly when conditions
  clear.
- **Evidence so far**: `execution/demo_risk_manager.py` wired to real close
  outcomes via `position_close_detector.py` (prior sprint, PR #22).
  `risk_state`/`portfolio_state` persist and reload across restarts.
- **Status**: **Verified by test** for individual mechanisms. **Requires
  live run** to observe a full day's worth of real limit interactions
  (most limits are daily/weekly-scoped and can't be meaningfully exercised
  in a short test).

### 7. Journal
- **Pass condition**: every order placed, filled, or closed has a
  corresponding, accurate journal entry; no orphaned broker positions with
  no journal row.
- **Evidence so far**: `TradeJournalDB.get_trade_by_broker_order_id()` blank-id
  guard (PR #22 fix). `position_close_detector.py::diff_closed_positions()`
  matches broker-closed positions to journal rows, with a documented
  limitation (MetaAPI market orders return `orderId` not `positionId`).
- **Status**: **Verified by test** for the matching logic. **Requires live
  run** to confirm zero orphans over a real 24-hour order flow.

### 8. Operations recorder
- **Pass condition**: the durable Postgres `operations.*` audit trail
  captures every pipeline event, intent, risk decision, order record, and
  recovery checkpoint without gaps, and degrades gracefully (never blocks
  the tick loop) if the DB is briefly unavailable.
- **Evidence so far**: `execution/operations_recorder.py`, migration 004
  applied, best-effort recording confirmed in code (prior sprint).
- **Status**: **Requires live run** to confirm sustained, gap-free recording
  and graceful DB-unavailability handling under real conditions (not
  exercised by this mission's unit tests).

### 9. Emergency stop
- **Pass condition**: an emergency stop activated at any point blocks all
  new orders immediately (next tick, not next restart), is enforced at both
  the tick-loop level and the pipeline/risk-gate level, and a resume does
  not clear a stop it didn't create.
- **Evidence so far**: `execution/control_plane.py::TradingPermissionService`
  (per-tick, prior sprint) + `production.engine.EmergencyStopRiskGate`
  (pipeline-level, PR #25, this mission's Phase 3 reconciled it against
  current `main` and re-verified 157/157 tests). Resume-scoping
  (`emergency_stop.source` tracking) fixed in PR #22.
- **Status**: **Verified by test** — the most thoroughly covered item on
  this checklist (11 dedicated tests across both enforcement points).

## Summary table

| # | Item | Status |
|---|---|---|
| 1 | Restart survival | Verified by test (duplicate-order dimension); full path requires live run |
| 2 | Recovery | Verified by test |
| 3 | Duplicate prevention | Verified by test (pending PR #37 merge) |
| 4 | Broker reconnect | Partially verified by test; full cycle requires live run |
| 5 | Dashboard | Requires live run |
| 6 | Risk | Verified by test (mechanisms); full-window behavior requires live run |
| 7 | Journal | Verified by test (matching logic); full-window requires live run |
| 8 | Operations recorder | Requires live run |
| 9 | Emergency stop | Verified by test (most thoroughly covered) |

**5 of 9 items have direct unit/integration test evidence today. All 9 have
a plan for what "pass" means and what evidence would demonstrate it for the
actual 24-hour window — none require guessing at qualification criteria on
the day of the run.**

## Risk

Items 5 and 8 (dashboard sustained accuracy, operations recorder gap-free
recording) have the least direct evidence today — worth prioritizing
observation on those two specifically during the actual qualification run,
not just treating all 9 as equally covered.

## Recommendation

Do not execute the 24-hour window until PR #37 (Phase 2, duplicate-order
prevention) and PR #25 (emergency-stop) are merged — items 3 and 9 are the
two highest-severity checklist items and both depend on code not yet on
`main`.

## Priority

Medium — this is preparation for a validation step that itself depends on
Phase 2/Phase 3's PRs merging first; not blocking any other phase in this
mission.

## Estimated effort

Preparation (this document): complete. The actual 24-hour run: 24 hours of
wall-clock observation (owner/operator time), not engineering effort.

## Rollback

N/A — no code changed, checklist only.

## Dependencies

PR #37 (Phase 2) and PR #25 (emergency-stop) should merge before this
checklist's items 3 and 9 can be considered "live-verified" rather than
"verified by test only."

## Acceptance criteria

- [x] All 9 required dimensions covered (restart, recovery, duplicate
      prevention, broker reconnect, dashboard, risk, journal, operations
      recorder, emergency stop)
- [x] Each item states a concrete pass condition and current evidence status
- [x] The 24-hour run itself is NOT executed — preparation only
