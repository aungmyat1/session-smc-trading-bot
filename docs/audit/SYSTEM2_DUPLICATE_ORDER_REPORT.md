---
Date: 2026-07-12
Author: Lead Architect / QA (Claude)
Authority: Level 8 — informational evidence. Does not supersede `docs/00_Project/DOC_AUTHORITY.md`.
Scope: Phase 2 of the System2 Completion Mission (Production Hardening Sprint). HIGHEST PRIORITY.
---

# System 2 Duplicate-Order Report

## Executive Summary

Implemented deterministic duplicate-order prevention in the deployed order-
placement path (`TradeManager.open_position()`), closing the gap identified
in `docs/audit/SYSTEM2_CORRECTNESS_AUDIT.md`. The fix is additive — one new
pure function, one new store method, and a check inserted before the
existing order-placement logic — not a rewrite of `TradeManager`,
`ExecutionStateStore`'s state machine, `StartupRecovery`, or any pipeline
component. 21 new tests cover every duplicate scenario the mission
specifies, including the explicit acceptance criterion (100 duplicate
requests → exactly 1 broker order). Full regression suite: 256 passed
(scope and two pre-existing, unrelated environment gaps noted below).

## Design — mapped onto existing infrastructure, not a new pipeline

The mission describes the target flow as:

```
Signal → IntentIdentity → ExecutionJournal → PendingExecutions →
RecoveryState → BrokerState → Broker.submit()
```

This maps directly onto infrastructure that already exists:

| Mission concept | Existing implementation |
|---|---|
| ExecutionJournal | `ExecutionStateStore` (disk-backed, one JSON record per execution) |
| PendingExecutions | `SUBMISSION_PENDING` state |
| RecoveryState | `RECOVERY_PENDING` state |
| BrokerState | `BROKER_ACKNOWLEDGED` (and later: `PARTIALLY_FILLED`, `FILLED`, `JOURNALED`, `RECONCILED`) |
| Broker.submit() | `TradeManager._place_order_with_retry()` → `executor.place_order()` |

The only missing piece was **IntentIdentity** and the **gate that checks it
before Broker.submit()**. Both are new, small, and additive:

1. **`execution/execution_state.py::build_intent_identity()`** (new pure
   function) — deterministic identity from `strategy_id`, `symbol`,
   `direction` (case/whitespace-normalized), a **time bucket** (signal
   timestamp floored to a configurable window, default 60s — not wall-clock
   "now," so the identity doesn't depend on *when* `open_position()` happens
   to be called), and `trading_session` (the session label, e.g.
   "london"/"ny" — not a process/run ID, since a process restart must
   produce the *same* identity for the same signal or duplicate detection
   would not survive a restart). A SHA-256-derived hash of these components
   forms the "signal hash" the mission specifies.
2. **`ExecutionStateStore.find_active_by_identity()`** (new method) — scans
   all non-terminal records (same disk-backed glob pattern
   `recover_incomplete()` already uses) for one matching the given identity.
   Matches `SUBMISSION_PENDING`, `RECOVERY_PENDING`, and every
   broker-acknowledged-or-later non-terminal state in one unified check,
   since they are all, by construction, "an active record already exists for
   this intent."
3. **`TradeManager.open_position()`** (modified) — calls
   `find_active_by_identity()` immediately after computing the identity and
   **before** `create_record()` or any broker call. If a match exists:
   - Already has a `broker_order_id` → return the existing order's details
     with `duplicate_suppressed: True, duplicate_reason: "already_broker_acknowledged"`.
     No second broker call.
   - No `broker_order_id` yet (still pending/ambiguous) → return
     `duplicate_reason: "in_flight_ambiguous"`. No second broker call; the
     existing recovery reconciliation (`SYS2-T014`, already on `main`)
     resolves the original record on its own schedule.

Between the identity check and `create_record()` there is **no `await`** —
both are synchronous. This means the gate is also safe against same-process
concurrent duplicate calls (e.g. a duplicated event dispatched twice via
`asyncio.gather`), not only sequential retries, since Python's cooperative
scheduler cannot interleave another coroutine between the check and the
write.

### What was deliberately not added

An early version also checked open broker positions (matching symbol +
direction) as a secondary safety net for the mission's "existing open
position" bullet. **This was reverted before being committed** — running the
existing test suite immediately surfaced false positives against legitimate
order flow (a test fixture modeling an unrelated pre-existing position
caused every new-order test to be wrongly suppressed). Open-position/broker-
truth drift detection is already the responsibility of
`execution/close_reconciliation.py` and `execution/position_close_detector.py`
(confirmed real and tested in `SYSTEM2_CORRECTNESS_AUDIT.md`), which run
every tick — duplicating that logic inside `open_position()`'s hot path
added risk without adding coverage. This is recorded in code comments at the
point where the check was removed, not silently dropped.

## Evidence

- `tests/execution/test_duplicate_order_prevention.py` — 21 new tests:
  `build_intent_identity()` determinism and differentiation (8),
  `find_active_by_identity()` correctness (4), and the full `TradeManager`
  integration (9): duplicate-after-broker-ack, duplicate-while-pending,
  duplicate-after-recovery-pending, **duplicate-survives-process-restart**
  (fresh `TradeManager`/`ExecutionStateStore` pointed at the same disk path),
  duplicate-after-timeout-then-retry, duplicate-websocket-double-dispatch
  (`asyncio.gather`, true concurrency), **100-duplicate-requests-produce-
  exactly-1-broker-order** (the mission's explicit acceptance criterion),
  different-signals-are-not-deduped (false-positive regression guard), and
  duplicate-after-broker-reconnect.
- A real, pre-existing test-isolation bug was found and fixed as part of
  this work: `tests/execution/test_trade_manager.py`'s `_make_manager()`
  never passed an explicit `execution_store`, so every test in that module
  silently shared the same default `./data/execution` directory. This was
  harmless before duplicate detection existed; once the gate was added, it
  caused 5 pre-existing tests to fail against leftover state from earlier
  tests in the same run. Fixed by giving each test its own isolated
  temp-directory store — a minimal, directly-required fix, not unrelated
  refactoring.
- Full run: `tests/production tests/execution tests/scripts tests/core
  tests/svos/test_lifecycle_authority.py` (excluding
  `tests/core/test_smc_ob_fvg_session_adapter.py`, pre-existing
  `numpy`/`pandas` import gap in this sandbox, unrelated to this change) —
  **256 passed, 0 failed**.
- `tests/dashboard` could not be run in this sandbox (Flask install
  conflicts with a Debian-managed `blinker` package) — a pre-existing
  environment limitation, not a code issue; `dashboard/` was not modified by
  this change.
- `ruff check` on all changed files — clean.

## Risk

- The in-flight/ambiguous case (`duplicate_reason: "in_flight_ambiguous"`)
  returns without placing an order and relies on the existing periodic
  reconciliation (SYS2-T014) to eventually resolve the original record. This
  is a deliberate choice — placing a second order when uncertain is strictly
  worse than briefly refusing a signal that recovery will resolve within one
  reconciliation cycle (default: every 5 ticks / configurable
  `RECONCILE_MIN_PENDING_AGE_S`).
- `find_active_by_identity()` scans every non-terminal record on disk on
  every call. At current single-strategy demo scale (a handful of records at
  any time) this is negligible; if execution volume grows substantially,
  this may warrant an index rather than a full scan — not a concern at
  current scale, noted for future awareness only.

## Recommendation

Merge as its own PR, after Phase 1's already-verified PR #25 and PR #33 (no
dependency between them, but keeping the sequence small and reviewable per
this mission's rules).

## Priority

Highest, per the mission's own explicit designation.

## Estimated effort

Already complete: ~4 hours (design + implementation + test-isolation bug
fix + 21 new tests + full regression verification).

## Rollback

See `ROLLBACK.md` for the full guide. Summary: this is a single, additive
change across 2 files (`execution/execution_state.py`,
`execution/trade_manager.py`) plus 1 new test file and 1 test-isolation fix.
`git revert` of the commit cleanly restores the pre-Phase-2 behavior (no
duplicate-order protection, same as before this mission). No database
migration, no schema change, no config change.

## Dependencies

None — independent of Phases 1, 3-8.

## Acceptance criteria

- [x] IntentIdentity includes strategy, symbol, direction, time bucket,
      signal hash, and trading session (execution-session interpreted as
      trading session, not process ID — see Design rationale)
- [x] Existing pending order, broker-acknowledged order, and recovery record
      all checked via one unified `find_active_by_identity()` call before
      any broker interaction
- [x] No duplicate broker execution possible for a repeated identical signal
      — verified by direct test, including true concurrency
- [x] All existing tests still pass (256/256 in the verifiable scope)
- [x] New tests pass (21/21)
- [x] No architecture regression — additive only, verified by diff review
- [x] 100 duplicate requests → exactly 1 broker order (explicit test)
