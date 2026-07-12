---
Date: 2026-07-12
Author: Lead Architect / QA audit (Claude)
Authority: Level 8 — informational evidence. Does not supersede `docs/00_Project/DOC_AUTHORITY.md`.
Scope: Phase 6 of the System2-first reconciliation program.
---

# System 2 Execution Correctness Audit

## Executive Summary

The deployed execution path (`scripts/run_st_a2_demo.py` → `execution/trade_manager.py`
→ `execution/mt5_connector.py`) is materially more correct than a first read
suggests: several defects that appear open in older docs (including on the
`codex/demo-smoke-test` branch) are **already fixed on `main`** via PR #22 and
PR #27 (SYS2-T014). One real, unmitigated gap remains and is high-priority:
**no deterministic duplicate-order prevention** — `TradeManager.open_position()`
never checks for an existing execution record before creating a new one and
placing a broker order. This is Phase 4's target, tracked separately in
`NEXT_IMPLEMENTATION_SEQUENCE.md` as a design (not yet implemented — touching
the live order-placement path without full test coverage in the same sitting
would violate this program's own "small PRs, tests required" rule).

## Method

Read (not just grepped) `execution/trade_manager.py`, `execution/execution_state.py`,
`execution/startup_recovery.py`, `execution/close_reconciliation.py`,
`execution/position_close_detector.py`, `execution/operations_recorder.py`,
`execution/risk_manager.py` / `execution/demo_risk_manager.py`, and
`execution/control_plane.py` on current `main`. Cross-checked each finding
against PR #22's and PR #27's recorded fix descriptions to determine current
(not historical) status. Ran the actual test suite for `tests/production`,
`tests/execution`, `tests/scripts` (157 passed) as part of Phase 3's
verification — reused here as evidence this audit's conclusions match a
green baseline, not a stale read.

## Findings by dimension

### Idempotency — **FAIL (one real gap, otherwise strong)**

- `execution/execution_state.py::ExecutionStateStore.create_record()`
  generates an idempotency key as `f"{strategy_id}:{signal_id}:{uuid4().hex[:12]}"`
  when none is explicitly passed — **always unique by construction** (the
  `uuid4()` suffix guarantees it), so the key itself can never collide and
  therefore can never be used to detect a duplicate.
- `execution/trade_manager.py::TradeManager.open_position()` (lines ~60-104)
  builds a deterministic `signal_id` (`f"{strategy_name}:{symbol}:{direction}:{timestamp}"`)
  but passes it as `signal_id`, not `idempotency_key`, and **never queries
  the store for an existing record matching that `signal_id` before calling
  `create_record()` and proceeding to place a broker order.** There is no
  `find_by_signal_id`, `find_by_idempotency`, or equivalent lookup anywhere
  in `execution_state.py` — confirmed by grep across `execution/*.py`.
  Concretely: if `open_position()` is invoked twice for the same signal (a
  retry at a caller layer, a race between the main tick loop and a recovery
  path, or a bug that double-dispatches a signal), two independent
  `ExecutionRecord`s and two independent broker orders result. Nothing in
  this path detects or prevents that.
- What **does** exist and is real: per-attempt retry-with-backoff inside a
  single `open_position()` call (`_place_order_with_retry`, 3 attempts,
  transient/ambiguous/terminal error classification) — this protects against
  duplicate orders from a single call's own retries, not from the call being
  made twice.
- **Verdict: no duplicate-order protection across separate calls.** This is
  Phase 4's target — see `NEXT_IMPLEMENTATION_SEQUENCE.md`.

### Recovery — **PASS (confirmed fixed, was previously flagged as open)**

- `execution/startup_recovery.py::reconcile_pending_executions()` resolves
  both `BROKER_ACKNOWLEDGED` records (immediately, unconditionally — `_reconcile_one()`
  line ~139-149, `advance_to_terminal(..., "COMPLETED", ...)`) and
  `RECOVERY_PENDING` records (age-gated to avoid racing an in-flight order —
  `min_pending_age_seconds`, default 0 preserves original startup-only
  semantics for that specific branch).
- This runs **both at startup and periodically mid-session**
  (`scripts/run_st_a2_demo.py` lines ~820, ~855-865, tagged `SYS2-T014`) —
  landed via PR #27, already merged to `main`.
- Cross-reference: `codex/demo-smoke-test`'s commit `8694a5a` (2026-07-07)
  describes this exact symptom ("`BROKER_ACKNOWLEDGED` records never advance
  forward, `RECOVERY_PENDING` only clears on startup") as an **open, unfixed
  defect** as of that branch's investigation. That description is now **stale**
  — `main`'s independent SYS2-T014 implementation (also dated 2026-07-07,
  merged via PR #27) resolves both halves of the symptom. This is the
  clearest confirmed instance of the "two independent SYS2-T014
  implementations" risk flagged in `BRANCH_RECONCILIATION_REPORT.md` — in
  this case `main`'s version is further along and should not be replaced by
  the branch's.

### Broker truth — **PARTIAL**

- `execution/close_reconciliation.py` scores closed positions using real
  broker close data (`VantageDemoExecutor.get_closing_deal()`, added in PR #22's
  safety-critical fix pass) rather than stale unrealized P&L from the last
  poll — confirmed current.
- `execution/position_close_detector.py::diff_closed_positions()` matches
  broker-disappeared positions back to journal rows; its own docstring notes
  a known limitation (MetaAPI market orders return `orderId`, not a separate
  `positionId`) — this is a documented constraint, not a silent failure.
- Three broker-client implementations coexist (`execution/mt5_connector.py`
  — live; `execution/metaapi_client.py`, `execution/mt5_executor.py` —
  dormant, serve only the disconnected `bot.py`/`order_manager.py` path).
  Not a correctness bug today (only one is on the live call path), but a
  real risk for any future change that touches the wrong one by mistake.
  Tracked as technical debt, not urgent.

### Journal / position consistency — **PASS**

- `execution/trade_journal.py` / `core/trade_journal_db.py`: `get_trade_by_broker_order_id()`
  rejects a blank id before querying (PR #22 fix) — previously could match an
  arbitrary unrelated trade.
- `execution/operations_recorder.py` best-effort records every pipeline
  event, intent, risk decision, order record, and recovery checkpoint to a
  durable Postgres table (migration 004, applied) — a queryable audit trail
  exists; this is additive to, not a replacement for, `ExecutionStateStore`'s
  own idempotency responsibility (correctly separated).

### Risk consistency — **PASS**

- `execution/demo_risk_manager.py` (0.25%/trade, 4 trades/day, 2 open
  positions, 1.5% daily loss, 3 consecutive losses) is wired to real close
  outcomes via `position_close_detector.py` (PR #22 Sprint work) — circuit
  breakers can actually fire from real P&L, not just simulated state.
  `risk_state`/`portfolio_state` persist to JSON and reload at process start
  (a restart no longer silently zeroes them).
- **Emergency stop**: `execution/control_plane.py::TradingPermissionService`
  checked per-tick before any order logic; as of PR #25 (this program's
  Phase 3, reconciled and pushed as part of this audit), also enforced a
  second time at the pipeline/risk-gate layer via `EmergencyStopRiskGate`
  (`production/engine/execution_pipeline.py`) — reads `control_state.json`
  fresh on every evaluation, never cached, rejects before the broker
  adapter is reached. Resume-scoping (a resume must not clear an emergency
  stop it didn't create) fixed in PR #22 (`emergency_stop.source` tracking).
- **Remaining gap, not urgent**: `risk_state`/`portfolio_state` durability is
  JSON-file persistence, not a transactional ledger — acceptable mitigation
  for current single-instance deployment, flagged as open in
  `SYSTEM2_MASTER_PLAN.md`, not re-litigated here.

### Silent failures — **PASS, with one documented exception**

- `close_reconciliation.py`: a balance-fetch failure defers the whole
  reconciliation to the next tick with a logged error, rather than recording
  zeroed P&L (PR #22 critical fix).
- `position_close_detector.py`: broker-disconnect during emergency stop
  degrades gracefully (empty/best-effort data), doesn't crash the tick —
  covered by PR #25's own test (`test_tick_degrades_gracefully_when_broker_disconnected_during_emergency_stop`).
- **Documented, accepted exception**: `execution/trade_manager.py` catches
  broad exceptions around `get_account_info()` in the blocked-tick path and
  leaves a default value rather than propagating — this is intentional
  (avoids crashing a paused tick over a transient broker read), not a silent
  data-integrity risk, since no order placement happens on that path.

## Summary table

| Dimension | Verdict | Evidence |
|---|---|---|
| Idempotency | **FAIL** | `open_position()` — no pre-order dedup check (this audit, code-read) |
| Recovery | **PASS** | `reconcile_pending_executions()`, periodic since PR #27 (this audit, code-read + cross-referenced against stale branch finding) |
| Broker truth | **PARTIAL** | Real close-data scoring (PASS); 3 parallel broker-client stacks (debt, not a bug) |
| Journal consistency | **PASS** | Blank-id guard, durable ops audit trail (PR #22, code-read) |
| Position consistency | **PASS**, documented limitation | `position_close_detector.py` orderId/positionId caveat is in its own docstring |
| Risk consistency | **PASS** | Real P&L-driven circuit breakers, dual emergency-stop enforcement (PR #22 + PR #25) |
| Silent failures | **PASS** | No fabricated data found; deferred-not-zeroed on balance-fetch failure |

## Acceptance criteria for this report

- [x] `trade_manager.py`, `startup_recovery.py`, `close_reconciliation.py`, `operations_recorder.py`, `risk_manager.py`, dashboard control path inspected
- [x] Idempotency, recovery, broker-truth, journal, position, risk consistency each verdict'd with code citations
- [x] No silent failures found beyond one documented, intentional exception
- [x] One real gap identified (duplicate-order prevention) and handed to Phase 4/`NEXT_IMPLEMENTATION_SEQUENCE.md`, not left implicit
