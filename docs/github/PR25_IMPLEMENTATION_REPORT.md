---
Date: 2026-07-05
Status: Awaiting merge decision
Owner: Repository governance
Related: docs/audit/EXECUTION_LAYER_GAP_ANALYSIS.md, docs/audit/STABILIZATION_ROADMAP.md, docs/github/PR22_FIX_REPORT.md
---

# PR #25 Implementation Report — Emergency-Stop RiskFirewall

PR link: https://github.com/aungmyat1/session-smc-trading-bot/pull/25

## Design decision: redirected scope

The original ask (PR #24 spec) was to wire the emergency-stop check into `run_portfolio.py`. Before writing code, I found that `run_portfolio.py`'s own file header and `SYSTEM2_MASTER_PLAN.md`'s Phase 2 section both explicitly record a decision that this would work against: `run_st_a2_demo.py` (the deployed runner) is meant to *absorb* `run_portfolio.py`'s `CanonicalExecutionPipeline`/`RiskFirewall` architecture, not the reverse — and `run_portfolio.py` has no systemd unit, is hard-blocked from starting (`RUN_PORTFOLIO_ALLOW_START`), and its own docstring says extending it independently is "wasted effort ahead of the Phase 2 port."

Given the choice, you redirected scope to close the gap on the deployed runner's architecture instead — specifically, `SYSTEM2_MASTER_PLAN.md` Sprint 2.1 explicitly left "`RiskFirewall` (a real, non-allow-all risk gate) — out of scope for this sprint" as unfinished work. That's the gap this PR closes.

## What was built

**`production/engine/execution_pipeline.py`** — new `EmergencyStopRiskGate` class:
- Wraps an inner `RiskGate` (here, `AllowAllRiskGate`).
- `evaluate()` calls `state_loader()` (bound to `dashboard.control_state.load_control_state`) fresh on every invocation — never cached — so a stop activated or cleared mid-run takes effect on the very next intent, not just at gate construction.
- Rejects with `RiskDecision(False, "emergency stop active", details={reason, activated_at, source})` whenever `control_state.json`'s `emergency_stop.active` is true; otherwise delegates to the inner gate unchanged.

**`scripts/run_st_a2_demo.py`** — wired `EmergencyStopRiskGate(AllowAllRiskGate(), state_loader=load_control_state)` into the existing `CanonicalExecutionPipeline` in place of the bare `AllowAllRiskGate()`. Also added a per-tick structured log line (`"Trading paused: emergency stop active (reason=..., source=..., activated_at=...)"`) that fires on every blocked tick — previously only the *first* tick of a new activation logged anything.

## Why this is correct, not redundant

`_tick()` already returns before reaching signal generation whenever the emergency stop is active (existing Phase 1 behavior) — so in the *current* runner, this gate never actually gets exercised in practice; `AllowAllRiskGate` was already safe. The value is structural: `pipeline.submit()` is now safe on its own, independent of any caller correctly replicating `_tick()`'s early-return. This matters directly for the Phase 2 port this PR deliberately avoided doing early — whatever code eventually absorbs `run_portfolio.py`'s pipeline usage inherits this protection automatically, rather than needing to rediscover and re-implement the same early-return pattern.

## Requirements coverage (against the original PR #24 spec, reinterpreted per the redirect)

1. **Integrate the existing emergency-stop check** — done, at the pipeline level (structural) in addition to the existing tick-level check.
2. **When active:**
   - Prevent new order submissions — `EmergencyStopRiskGate` rejects before `adapter.execute()` (verified: `adapter.calls == 0` in the full-pipeline test).
   - Continue monitoring positions/broker connectivity — already true in `_tick()` (unchanged): `get_account_info()`/`get_positions()` are still called, wrapped in try/except.
   - Structured log entries — added (see above); previously missing on repeat ticks.
   - Expose to dashboard/monitoring — already true; `control_state.json` is read directly by `/api/operations/health`, `/overview`, and the control endpoints. No new work needed.
3. **When inactive: no regression** — verified by `test_emergency_stop_gate_allows_submission_when_inactive` and the full existing suite passing unchanged.
4. **Tests for all 4 required scenarios** — all added:
   - Active at startup: `test_tick_blocks_from_the_very_first_tick_when_already_active_at_startup`
   - Activated during runtime: pre-existing `test_tick_closes_positions_once_per_emergency_activation`, still passing
   - Cleared during runtime: `test_tick_resumes_normal_processing_after_emergency_stop_cleared`
   - Broker disconnect while active: `test_tick_degrades_gracefully_when_broker_disconnected_during_emergency_stop`
5. **Docs updated**: `docs/systems/system2/STATUS.md`, `docs/systems/system2/ROADMAP.md`, `SYSTEM2_MASTER_PLAN.md` (new Sprint 2.4 entry).
6. **Scope discipline**: `run_portfolio.py` was not touched. No unrelated execution features added.

## Test evidence

- 11 new tests: 7 in `tests/production/test_canonical_execution_pipeline.py` (gate unit tests: rejects when active, delegates when inactive, rejects even when inner would approve, reads state fresh not cached; full-pipeline tests: blocks submission end-to-end with 0 adapter calls, allows submission when inactive), 4 in `tests/execution/test_emergency_stop_integration.py` (the four required scenarios).
- 217 passed across `tests/production/`, `tests/execution/`, `tests/scripts/`, `tests/dashboard/`, `tests/test_status_server.py`, `tests/svos/test_lifecycle_authority.py`, `tests/core/test_trade_journal_db.py`. 0 failed.
- `ruff check` on all touched files: identical findings to `origin/main` (confirmed via diff) — nothing new.
- `scripts/lint_docs.py` and `scripts/check_docs_drift.py`: both exit 0.

## Remaining execution-layer work (from `docs/audit/EXECUTION_LAYER_GAP_ANALYSIS.md` / `docs/audit/STABILIZATION_ROADMAP.md`, unaffected by this PR)

- **P0**: idempotency guard on order placement (`execution/trade_manager.py::open_position()` — the generated key is randomized per call, never checked against a prior one).
- **P0**: `/api/v1/production/health` heartbeat never written by the canonical runner.
- **P1**: retry-with-backoff on broker read calls (`get_positions`, `get_account_info` — order placement already has this, reads don't).
- **P1**: consolidate the three parallel broker-client implementations (`mt5_connector.py` live, `metaapi_client.py` and `mt5_executor.py` dormant).
- **P1**: unify or formally document the three-mechanism reconciliation cadence.
- **P2**: operations-recorder write-confirmation signal; realistic broker-response-shape test fixtures.
- **Separately, unresolved**: the actual `run_portfolio.py` retirement/feature-port decision (SYSTEM2_MASTER_PLAN.md Phase 2) remains not started — this PR closes one specific sub-gap (RiskFirewall) independently of that larger decision, as scoped.

## Follow-up commit (`97f7504`) — CodeRabbit finding

CodeRabbit's review caught a real latent bug: `evaluate()` forwarded a `context` argument to `self.inner.evaluate(intent, context)` whenever `context` was non-`None`, but `RiskGate`/`AllowAllRiskGate` only declare `evaluate(self, intent)` — a `TypeError` waiting to happen if this gate is ever paired with a `risk_context_provider` (not currently wired anywhere, but exactly the kind of future reuse this gate exists for). Fixed by checking `inner.evaluate`'s signature once at construction (not exception-handling at call time) and only forwarding context when the inner gate actually accepts it. 2 new regression tests; 22 passed across both affected test files; ruff clean.

## Deliverable status

- [x] Small, self-contained PR (9 files across 2 commits, +390/−8)
- [x] All required CI checks passing
- [x] All review threads addressed
- [x] Test evidence above
- [x] This implementation report

Not yet done: merge. Awaiting your go-ahead, same as PR #23.
