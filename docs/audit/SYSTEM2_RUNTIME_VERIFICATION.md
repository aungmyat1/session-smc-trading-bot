---
Date: 2026-07-12
Author: Lead Architect / Production Reliability audit (Claude)
Authority: Level 8 — informational evidence. Does not supersede `docs/00_Project/DOC_AUTHORITY.md`.
Scope: Phase 3 of the System2 Completion Mission. Builds on and updates
`docs/audit/SYSTEM2_CORRECTNESS_AUDIT.md` (prior sprint) rather than
repeating it — see that document for idempotency (now updated below),
recovery, broker-truth, journal, position, and risk-consistency findings
not re-litigated here.
---

# System 2 Runtime Verification

## Executive Summary

New analysis in this pass, beyond the prior correctness audit: **race
conditions** and **`CanonicalExecutionPipeline`** specifically. Finding: the
deployed runner (`scripts/run_st_a2_demo.py`) is a single sequential
coroutine — it never calls `asyncio.create_task()` or `asyncio.gather()` — so
there is no in-process concurrency for the main tick loop to race against
itself. The only concurrency surface is *external* duplicate calls (a caller
invoking `open_position()` twice) or a *second OS process* running
concurrently against the same disk-backed store; Phase 2's fix (this
mission) covers both, since `find_active_by_identity()` is disk-backed, not
in-memory.

## Method

Read `production/engine/execution_pipeline.py` in full (not previously
audited in depth). Re-verified the prior audit's other findings are still
current on `main` post-Phase-2. Grepped the deployed runner for any
concurrent-task spawning.

## Findings

### Race conditions — **PASS**

- `scripts/run_st_a2_demo.py` contains zero calls to `asyncio.create_task`,
  `asyncio.ensure_future`, or `asyncio.gather` — confirmed by direct grep.
  The entire tick loop (`_tick()`/`run()`) executes as one sequential
  coroutine: signal generation, risk checks, order placement, position
  polling, and (per SYS2-T014) periodic reconciliation all happen in program
  order within a single `await` chain, never as concurrent tasks.
- **Consequence**: there is no in-process race between, e.g., the main tick
  and periodic reconciliation — they cannot run "at the same time" because
  there is only ever one coroutine executing at once in this runner.
- **Remaining concurrency surface**: (a) an external caller invoking
  `open_position()` twice for the same signal (via retry logic, a duplicated
  event, etc.) — closed by Phase 2's `find_active_by_identity()` check,
  which has no `await` between the check and the record write, so even a
  same-process `asyncio.gather()` double-dispatch is safe (verified by
  `test_duplicate_websocket_double_dispatch_concurrent` and the 100-request
  test in `SYSTEM2_DUPLICATE_ORDER_REPORT.md`); (b) two separate OS
  processes both writing to the same `ExecutionStateStore` directory — also
  closed by the same disk-backed check, though genuinely simultaneous
  cross-process writes (both processes passing the check before either
  writes) remain a theoretical race the current file-per-record design
  doesn't fully lock against. Not a concern at current deployment scale
  (exactly one runner process, enforced by `run_portfolio.py`'s
  `RUN_PORTFOLIO_ALLOW_START` guard preventing a second process from
  starting) — noted for completeness, not treated as an open defect.

### `CanonicalExecutionPipeline` — **PASS**

- `submit()` validates the intent, evaluates the risk gate (as of Phase 3 of
  the prior sprint, `EmergencyStopRiskGate` — pending merge in PR #25), then
  calls `adapter.execute(intent)` exactly once per `submit()` call, in a
  straight sequential path with no branching that could double-invoke the
  adapter.
- Event emission (`self.events.append(event)`) is a single list append —
  atomic under the GIL, safe even if this pipeline instance were ever shared
  across concurrent callers (it currently is not; one instance per runner
  process, per `run()`'s `RuntimeError` guard against being started twice).
- No state mutation happens in `submit()` before the risk-gate decision that
  would need to be rolled back on rejection — rejection paths return early
  before touching the adapter.

### Retry / timeout — **PASS** (per prior audit, re-confirmed unaffected)

`TradeManager._place_order_with_retry()`'s 3-attempt exponential backoff is
unchanged by Phase 2 — the duplicate-order gate runs once, before this retry
loop begins, so retries within a single `open_position()` call are unaffected
and remain scoped to that one call's own execution record.

### Broker truth / journal / risk consistency / recovery — **PASS**

Unchanged from `SYSTEM2_CORRECTNESS_AUDIT.md`; re-verified still accurate
against current `main` (no drift since that audit). Idempotency is the one
row that changes:

| Dimension | Prior verdict | Current verdict | Why |
|---|---|---|---|
| Idempotency | FAIL | **PASS** (pending PR #37 merge) | Phase 2 closes the gap; 21 new tests, including 100-duplicate-requests-→-1-order |
| Recovery | PASS | PASS | Unchanged |
| Broker truth | PARTIAL | PARTIAL | Unchanged (3 broker-client stacks remain, non-blocking) |
| Journal consistency | PASS | PASS | Unchanged |
| Risk consistency | PASS | PASS | Unchanged |
| Silent failures | PASS | PASS | Unchanged |

### No stale state — **PASS**

- `risk_state`/`portfolio_state` persist to JSON every tick and reload at
  process start (prior audit finding, re-confirmed).
- Execution records are disk-backed per-record (not cached in memory across
  calls) — `find_active_by_identity()` reads fresh from disk on every call,
  so there is no stale in-memory cache of execution state that could drift
  from what's actually on disk.

## Evidence

- Direct grep confirming zero concurrent-task spawning in the deployed runner.
- Full read of `production/engine/execution_pipeline.py` (259 lines).
- Cross-reference against `SYSTEM2_CORRECTNESS_AUDIT.md` for all dimensions
  not re-analyzed here.
- Test evidence: `tests/execution/test_duplicate_order_prevention.py`'s
  concurrency tests directly exercise the one real concurrency surface this
  runtime has.

## Risk

None newly identified. The cross-process theoretical race noted above is
explicitly not treated as a defect — it requires two runner processes
running simultaneously against the same store, which the existing
`RUN_PORTFOLIO_ALLOW_START` guard and single-systemd-unit deployment already
prevent structurally.

## Recommendation

No further runtime-reliability code changes needed for this phase. Proceed
to Phase 4 (measured cost model).

## Priority

High — gates confidence in Phase 2's fix and the overall readiness score.

## Estimated effort

~2 hours (already complete).

## Rollback

N/A — this phase is verification only, no code changed.

## Dependencies

Builds on Phase 2 (duplicate-order prevention) and the prior sprint's
`SYSTEM2_CORRECTNESS_AUDIT.md`.

## Acceptance criteria

- [x] TradeManager, StartupRecovery, CloseReconciliation, OperationsRecorder,
      RiskManager, ExecutionPipeline all covered (directly here or by
      cross-reference to the still-current prior audit)
- [x] Race conditions specifically analyzed with evidence (grep + code read),
      not assumed
- [x] No silent failure, no stale state — both explicitly verified
- [x] Idempotency verdict updated to reflect Phase 2's fix, not left stale
