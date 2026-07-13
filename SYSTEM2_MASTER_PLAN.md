# SYSTEM 2 MASTER PLAN — Production Execution Readiness

- Date: 2026-07-12
- Status: Current master plan for System 2 readiness
- Scope: System 2, the production execution layer. System 1/SVOS appears here
  only as the upstream approval/package handoff.
- Governing authority: `docs/00_Project/TWO_SYSTEM_ARCHITECTURE_TRUTH.md`.
  If this plan conflicts with that document, the architecture truth wins.
- Safety invariant: this document does not authorize live trading, strategy
  approval, or broker-write configuration changes. `LIVE_TRADING=false` and
  `DEMO_ONLY=true` remain mandatory until the owner explicitly changes them
  after all gates pass.

---

## Executive Summary

System 2 is ready for controlled shadow/disabled rehearsals. It is not ready
for paper execution and not ready for live trading.

Local evidence collected on 2026-07-12:

- `python3 scripts/validate_runtime_config.py` passed.
- `python3 scripts/health_check.py --no-broker --no-db --json` reported
  `READY (shadow mode)`, with warnings for stale runner activity and no restart
  recovery state.
- Focused package/deployment readiness tests passed: `39 passed`.
- ST-B1 historical validation is BLOCKED, not failed: Dukascopy returned 403
  and no real EURUSD/GBPUSD H1+M15 data was reachable from this environment.
- No strategy currently has Production Approval.

The next work is not to enable more execution. The next work is to close the
remaining System 2 safety gaps, rehearse disabled deployment on the real host,
bind imported packages to the runtime, and prove broker telemetry/recovery
before any paper execution discussion.

---

## Current Readiness Verdict

| Capability | Readiness | Notes |
|---|---|---|
| Runtime configuration safety | PASS locally | Runtime validator passes. |
| Strategy package validation | PASS locally | Package/import/handoff tests pass. |
| Disabled package staging | Partial PASS | Code paths and tests pass; remote rehearsal still required. |
| Shadow-mode health | Conditional PASS | Offline health says shadow-ready but reports stale runner activity and missing recovery state. |
| Broker/data-feed evidence | BLOCKED | Skipped in local run; must be proven against demo broker only. |
| Cloud release/deploy path | BLOCKED | GitHub environments, WIF, GCS, KMS, Secret Manager and host install need proof. |
| Paper execution | BLOCKED | Requires approved package, broker evidence, durable recovery/journal proof and owner approval. |
| Live trading | BLOCKED | Out of scope; requires separate explicit approval after all production gates. |

---

## Non-Negotiable Gates

1. No live trading changes are permitted from this plan.
2. No strategy may be marked current, approved, paper-enabled or demo-enabled
   unless SVOS Production Approval exists and the execution gate is satisfied.
3. A failed, blocked, deferred or synthetic-only strategy result may not be used
   as approval evidence.
4. Disabled deployment rehearsal must reach `STAGED_DISABLED`; `activated` and
   `live_trading_enabled` must remain false.
5. Every broker-write or activation-class action must retain exact-match
   confirmation-token control where applicable.
6. Broker credentials and tokens stay outside git.

---

## Open Blockers

### Strategy and Governance

- No catalog strategy is approved for release.
- ST-B1 historical validation and walk-forward validation are BLOCKED, not
  failed. Real Dukascopy data was unreachable from this environment
  (`403 Forbidden`), so no real-data trades, PF, Sharpe, MaxDD or walk-forward
  verdict exists. See `docs/audit/ST_B1_VALIDATION_REPORT.md`.
- ST-A2 remains legacy/deferred from the SVOS perspective unless revalidated
  through the current gate.

### Local System 2 Safety

- Offline health reports stale runner activity.
- Offline health reports no restart recovery state.
- Phase 1 local safety issues from risk-register rows #15, #17, #19, #20 and
  #21 were fixed on 2026-07-12 with regression coverage.

### Runtime and Execution

- Imported packages are not yet fully bound to an executable production runtime
  with immutable package identity visible at signal/order time.
- Execution contracts remain split across existing order/trade/demo executor
  surfaces and need one normalized behavior for success, rejection, timeout and
  recovery.
- Broker latency, rejection, slippage, stale-feed and close-event telemetry need
  retained evidence from the actual demo path.

### Infrastructure

- GitHub protected environments and required variables need owner-side
  provisioning/proof.
- GCP Workload Identity, GCS, KMS, Secret Manager, IAM and production-host
  installation need a disabled rehearsal.
- Backup/restore, rollback, restart and network-partition drills are not yet
  complete.

---

## Target Architecture

System 2 remains deliberately simple:

```text
Approved Strategy Package
  -> package import + checksum/signature preflight
  -> STAGED_DISABLED runtime binding
  -> permission/risk/position gates
  -> execution manager
  -> broker adapter
  -> trade journal + execution state + telemetry
  -> dashboard/alerts/reconciliation
```

The production runtime must not audit, optimize, backtest or approve
strategies. It only stages, verifies, observes and executes approved packages
inside the allowed mode.

---

## Implementation Plan

### Phase 1 — Close Local Safety Gaps

Status: completed for in-repo fixes on 2026-07-12.

Tasks:

1. Completed: `scripts/vps_health_check.sh` passes `last_tick_at` via argv.
2. Completed: `vps-health-check.service` no longer loads dashboard secrets.
3. Completed: System 2 operational JSON endpoints require authentication.
4. Completed: health-check/dashboard stale-tick thresholds are aligned at 180s.
5. Completed: the invalid `strategy-release` GitHub CLI action was removed.
6. Completed: regression tests cover the above.
7. Completed: `docs/operations/risk-register.md` records the evidence.

Exit criteria:

- Focused System 2 tests pass: 26 passed.
- Runtime config validator passes.
- Risk-register rows are updated.

### Phase 2 — Remote Disabled Deployment Rehearsal

Priority: after Phase 1.

Tasks:

1. Configure GitHub environments:
   `strategy-release`, `paper`, `production-disabled`.
2. Apply required reviewer and trusted-branch/tag protections.
3. Set and verify required release variables:
   `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_RELEASE_SERVICE_ACCOUNT`,
   `SVOS_KMS_KEY_VERSION`, `SVOS_GCS_BUCKET`.
4. Provision/verify WIF, GCS, KMS, Secret Manager, IAM and production VM access.
5. Install the deployment poller on the target host under a non-login
   `agtrade` service account.
6. Run a fake approved-package disabled deployment rehearsal.

Exit criteria:

- Deployment status is `STAGED_DISABLED`.
- On-host policy confirms `LIVE_TRADING=false` and `DEMO_ONLY=true`.
- Health, heartbeat and `/metrics` are reachable locally on the host.
- Rollback record can be created without mutating package bytes.

### Phase 3 — Runtime Package Binding

Priority: after disabled rehearsal proves the deployment path.

Tasks:

1. Bind imported package metadata to runtime signal/order records:
   package ID, strategy ID, version, checksum and signature verification result.
2. Ensure runtime strategy loading uses verified package identity rather than
   ungoverned config defaults.
3. Normalize execution behavior across order placement paths:
   success, broker rejection, ambiguous timeout, retry, recovery and terminal
   failure.
4. Prove one-position-per-symbol, max-open-position, duplicate-order and daily
   loss controls in tests.

Exit criteria:

- A staged-disabled package can produce shadow-only signals with immutable
  package identity in journal/telemetry.
- No broker write can occur from an unapproved package.
- Execution contract tests pass for success, rejection, timeout and recovery.

### Phase 4 — Broker, Recovery and Telemetry Evidence

Priority: before paper execution.

Tasks:

1. Run broker connectivity and data-feed checks in demo mode only.
2. Add or verify telemetry for:
   - broker connection state;
   - tick freshness;
   - order latency;
   - broker rejection;
   - slippage;
   - close-event feedback;
   - reconciliation status;
   - non-terminal execution records.
3. Prove periodic reconciliation resolves or escalates non-terminal execution
   records mid-session.
4. Reconcile journal, broker state and execution-state store after a controlled
   restart drill.

Exit criteria:

- Broker/data-feed checks pass without live trading.
- Health and dashboard report the same freshness status.
- Reconciliation evidence is retained.
- Restart drill leaves no unexplained open, orphaned or non-terminal records.

### Phase 5 — Paper Execution Gate

Priority: only after Phases 1-4 pass and a strategy has Production Approval.

Tasks:

1. Use only an approved strategy package.
2. Stage the package disabled.
3. Verify exact environment policy and owner approval.
4. Enable paper/demo execution only; never live.
5. Run a minimum observation window with retained broker, journal, telemetry,
   risk and reconciliation evidence.

Exit criteria:

- No critical execution failures.
- Journal, broker and execution-state records reconcile.
- Risk limits are proven from real close events.
- Operator runbook covers pause, emergency stop, restart, rollback and
  recovery.

---

## Current Test Commands

Use these as the local readiness smoke set:

```bash
python3 scripts/validate_runtime_config.py
python3 scripts/health_check.py --no-broker --no-db --json
python3 -m pytest -o addopts='' \
  tests/production/test_system2_demo_readiness.py \
  tests/production/test_deployment_agent.py \
  tests/production/test_deployment_importer.py \
  tests/integration/test_canonical_package_handoff.py \
  tests/portfolio/test_strategy_package_cli.py \
  tests/portfolio/test_demo_smoke_test.py \
  tests/test_execution_validation_example_payload.py \
  tests/test_validate_strategy_package.py \
  tests/shared/test_strategy_package.py -q
```

The last recorded local run produced `39 passed`.

---

## Implementation Roadmap

### Phase 1 — Close the Safety-Critical Disconnects (Critical, start immediately)
- [x] **2026-07-04**: `record_result()`/`record_close()` wired into the real trade-close event path
  in `scripts/run_st_a2_demo.py` (the currently-deployed runner) via new
  `execution/position_close_detector.py` — diffs `TradeManager.get_positions()` between ticks,
  matches disappeared positions back to their `TradeJournalDB` row (`symbol` +
  `id == broker_order_id`, the same convention `scripts/reconcile_positions.py` already used), and
  feeds the real outcome into `demo_risk_manager.record_result()`, `PortfolioManager.record_close()`,
  and `CircuitBreaker.record_trade()` (previously never called in this runner at all — a related
  gap discovered alongside the hardcoded-`won=True` one below). Unmatched closes (no journal row
  found) are alerted via Telegram, not silently dropped or guessed at.
- [x] **2026-07-04**: `risk_state` and `PortfolioManager`'s counters are now persisted to
  `logs/risk_state.json` / `logs/portfolio_state.json` every tick and reloaded at process start —
  a restart no longer silently zeroes daily-loss/consecutive-loss/open-symbol state. This is a
  plain JSON file, not a transactional/Postgres ledger — no atomic-write guarantee, no evaluation
  of a durable-store alternative yet. Still open, tracked below.
- [x] **2026-07-04**: the circuit breaker's hardcoded `won=True` issue — confirmed to live in
  `scripts/run_portfolio.py:543,573` (`_breaker.record_trade(signal.strategy_name, won=True)` called
  at OPEN time, comment says "open = neutral" but the docstring says "call when a trade closes").
  Not fixed in `run_portfolio.py` pending the Phase 2 owner decision below (fixing code slated for
  possible retirement is wasted effort); `run_st_a2_demo.py` never called `record_trade()` at all
  before this pass and now does, correctly, at close.
- [x] **2026-07-04**: `ExecutionStateStore.recover_incomplete()` wired to real broker-truth
  reconciliation via new `execution/startup_recovery.py::reconcile_pending_executions()`, called
  from `scripts/run_st_a2_demo.py::run()` (the deployed runner) before the tick loop processes any
  new market data. Per incomplete `ExecutionRecord`: a known `broker_order_id` is confirmed and its
  journal row backfilled if missing; an unknown `broker_order_id` is matched against currently-open
  broker positions (recovered) or, absent a match, advanced straight to `FAILED_TERMINAL` with the
  signal treated as lost — never resubmitted. Broker positions with no execution/journal linkage at
  all are surfaced as `orphaned_positions` for operator attention, never auto-mutated. Idempotency
  is structural, not incidental: this module never calls an order-placement API, so a second
  recovery pass against the same durable state is a verified no-op. **Still open**: `run_portfolio.py`
  never calls `recover_incomplete()` (Phase 2); reconciliation is unverified against a real MetaAPI
  session (fixtures use synthetic broker position dicts).
- [x] **2026-07-04**: the module docstrings on both runners previously contradicted the Phase 2
  decision below — `run_st_a2_demo.py` called itself "legacy" and told operators to prefer
  `run_portfolio.py`, which has none of this runner's safety wiring. Both docstrings now state which
  runner is actually deployed/canonical and which is not, and `run_portfolio.py` logs an explicit
  warning at startup. The `won=True` hardcode itself remains untouched in `run_portfolio.py`,
  deliberately, per the "wasted effort ahead of retirement" reasoning already recorded above.
- [ ] Design and implement a durable, transactional risk/portfolio ledger (Postgres table or
  equivalent) — the JSON-file persistence above closes the "restart zeroes everything" hazard but
  is not this bullet; still open.
- [x] Acceptance: forced losing-streak test verified via
  `tests/scripts/test_run_st_a2_demo_close_detection.py::test_losing_streak_halts_via_real_close_events`.
  Forced-restart persistence verified via `test_state_persistence_round_trips`. Crash-during-submission
  recovery verified via `tests/execution/test_startup_recovery.py` (recovered/lost/orphaned/idempotent
  cases) and end-to-end via
  `tests/scripts/test_run_st_a2_demo_e2e_recovery.py::test_full_open_close_restart_recovery_resume_cycle`,
  which drives Open Trade → Broker Close → Close Detection → record_result() → Portfolio Update →
  Circuit Breaker → SQLite Journal → Dashboard state file → simulated restart → Recovery → Resume
  Trading through the real modules (fake broker connector/executor only — no live-broker
  end-to-end test exists in this pass; see Remaining/blocked in the Phase 1 report).

### Phase 2 — Resolve the Canonical/Legacy Execution Split
- **Decision recorded 2026-07-04**: `run_st_a2_demo.py` (deployed, has working governance/emergency-
  stop/recovery wiring) absorbs `CanonicalExecutionPipeline`/`RiskFirewall` from `run_portfolio.py`
  — not the reverse. Rationale: lower deployment risk (no systemd/live cutover required on the VPS;
  the unit that's already running doesn't change), and this pass's Phase-1 risk-feedback-loop fix
  already landed in `run_st_a2_demo.py`, so continuing to build on the deployed runner avoids
  re-doing that wiring a second time in `run_portfolio.py`. **Not yet implemented** — this is a
  decision record, not a completed migration; the actual pipeline/RiskFirewall port is a separate,
  substantial piece of work deserving its own dedicated pass, deliberately not attempted in the same
  turn as the Phase-1 safety fix above.
- [x] **Sprint 2.1 — 2026-07-04**: `production.engine.CanonicalExecutionPipeline` (with
  `AllowAllRiskGate`, since CircuitBreaker/PortfolioManager/permission/governance checks already
  approve the order earlier in `_tick()` — no duplicate risk logic) now wraps order placement in
  `scripts/run_st_a2_demo.py`. `run()`'s tick loop runs as the pipeline's workload
  (`pipeline_started`/`pipeline_stopped` events bound to its lifecycle); each order goes through
  `pipeline.submit(ExecutionIntent(...))`, whose adapter callback calls the *same*
  `manager.open_position()` as before — retry/state-machine/idempotency behavior is unchanged, this
  adds normalized event journaling (`logs/execution_pipeline_events.jsonl`) and intent/scope
  validation on top. Evidence: `tests/scripts/test_run_st_a2_demo_pipeline_integration.py` (pass-
  through order data unchanged; a scope-mismatched symbol is REJECTED loudly, `manager.open_position`
  never called — guards the real regression risk of this wiring). Full existing suite (296 tests
  across `tests/core,execution,scripts,production,portfolio,architecture,integration`) still green.
  **Not done**: `RiskFirewall` (a real, non-allow-all risk gate) — out of scope for this sprint,
  the existing upstream checks remain the risk authority; `run_portfolio.py` is untouched
  (Sprint 2.2 retires or absorbs it, not attempted here).
- [x] **Sprint 2.2 — 2026-07-04**: `run_portfolio.py::run()` now refuses to start unless
  `RUN_PORTFOLIO_ALLOW_START=true` is explicitly set, raising `RuntimeError` naming
  `run_st_a2_demo.py` before any broker connection is attempted — an operator or agent can no
  longer start this undeployed, unsafe-wiring runner by accident (it already logged a warning;
  now it hard-blocks). Scoped deliberately narrow, not a full retirement:
  - Not touched: `main()`'s package-validation/`RuntimeAuthority` CLI path, which existing tests
    (`tests/portfolio/test_strategy_package_cli.py`, `tests/integration/test_canonical_package_handoff.py`)
    use as real, still-valuable coverage of WS1 canonical-package validation (Pipeline A) — these
    patch `run`/`RuntimeAuthority.run` and never reach the new guard, so they still pass unchanged.
  - Not done: "move reusable logic into shared services." `run_portfolio.py`'s multi-strategy
    orchestration (`_STRATEGY_MAP`, shared M15/H4 fetch across strategies) has no equivalent in
    `run_st_a2_demo.py` (single-strategy only) — porting that is a real feature decision, not a
    safe mechanical extraction, and deliberately deferred to its own pass rather than rushed here.
  - Not done: physically deleting `run_portfolio.py` — the guard is the safe, reversible
    "neutralize" step this sprint asked for; deletion can follow once Sprint 2.2's multi-strategy
    question above is resolved.
  Evidence: `tests/portfolio/test_portfolio_runner.py::TestDeprecatedRunnerBlocked` (blocked by
  default; explicit override reaches `connect()`). Full suite: 298 passed (only the pre-existing,
  unrelated `test_smc_ob_fvg_session_adapter.py` failure remains).
- [x] **Sprint 2.3 — 2026-07-04**: durable transactional persistence, built on the
  `operations.*` Postgres schema (migration `004_system2_operations.py`) that already existed but
  was unapplied (`alembic current` was `003`, head `004`) and had no ORM layer at all. Rather than
  invent a second, competing SQLite ledger, this sprint: (1) ran `alembic upgrade head` against the
  connected DB — verified via direct `information_schema` query, all 10 `operations.*` tables now
  exist; (2) added the missing ORM classes (`Runtime`, `Intent`, `RiskDecision`, `OrderRecord`,
  `Fill`, `PositionRecord`, `Reconciliation`, `RecoveryCheckpoint`, `ExecutionEvent`,
  `MarketDataHealth`) to `db/models.py`, smoke-tested with real inserts against the live DB;
  (3) added `execution/operations_recorder.py`, a best-effort recorder (DB write failures are
  logged and swallowed, never block the tick loop — this is an audit layer, not a safety gate)
  wired into `scripts/run_st_a2_demo.py`'s **existing** `CanonicalExecutionPipeline` event_sink
  (Sprint 2.1) — every event still goes to `logs/execution_pipeline_events.jsonl` *and* now also to
  `operations.execution_event`, with `intent_received`/`risk_decision`/`execution_result` events
  additionally landing typed rows in `operations.intent`/`risk_decision`/`order_record`. Startup
  recovery (Phase 1) now also writes one `operations.recovery_checkpoint` row per pass. Evidence:
  `tests/execution/test_operations_recorder.py` (8 tests, mocked DB session — no live DB required
  for CI, matching this repo's existing `test_db_preflight.py` convention). Full suite: 328 passed,
  4 skipped; the only failures are the same 2 pre-existing ones confirmed via `git stash` to predate
  this sprint entirely (`test_smc_ob_fvg_session_adapter.py`, and 15 `test_db_preflight.py` failures
  caused by a bug in `scripts/db_preflight.py` itself — a SQLAlchemy transaction reused across
  `conn.begin()` calls — unrelated to and not fixed by this sprint; flagged, not addressed).
  **Not done, deliberately**: `market_data_health`/`fill`/`position_record`/`reconciliation` tables
  have ORM classes but nothing writes to them yet — `position_record`'s role is already served by
  `core/trade_journal_db.py`'s `trades` table (real position lifecycle, avoided a duplicate); the
  other three have no current caller and no acceptance criterion asked for them. The
  crash→restart→no-duplicate-order guarantee itself is **unchanged** — it already lived in
  `ExecutionStateStore`'s state machine (Phase 1) and remains the actual idempotency authority; this
  sprint adds a durable, queryable Postgres audit trail alongside it, not a replacement.
- [x] **Deployment fix — 2026-07-04**: `smc-demo-runner.service` had been crash-looping since
  creation — `deploy/gcp-vm1/run_smc_demo.sh` hardcoded `--strategy SMCOrderBlockFVGSession`, a
  strategy never registered in `strategies/adapters/__init__.py`'s `ADAPTER_TYPES` and still at
  `svos_stage: INTAKE`/`approved: false` in `config/strategy_catalog.yaml` — meaning **no strategy
  had ever actually run in production through this unit**. Full root-cause analysis:
  `docs/systemd/SMC_DEMO_RUNNER_ANALYSIS.md` (recommendation: Replace, not Repair — registering the
  draft/unapproved strategy instead would have been a governance violation, and its adapter has a
  separate, pre-existing failing test). Fixed by changing the wrapper to `--strategy ST-A2` (one
  line, git-trivial to revert). Verified: service `active (running)`, 0 restarts since
  2026-07-04T17:01:32Z, broker connected (Vantage demo MetaAPI), clean tick cycles every 60s with
  correct spread-limit risk decisions (`SKIP EURUSD — spread 4.1 > 1.5` etc.), zero exceptions in
  `journalctl`. Startup recovery (Phase 1) also visibly engaged correctly on the transition,
  resolving stale `ExecutionRecord`s from the prior misconfigured runs without resubmitting any
  order. **Also removed this pass**: `benchmark-bot.service`/`smc-bot.service`, both disabled and
  dangling (their working directories were deleted in the prior VPS cleanup batch) — unit files
  archived to `/home/aungp/archives/systemd-units/` before removal, `systemctl --failed` confirms
  0 failed units after.
- [x] **Execution Pipeline Consolidation, Tier 1 — 2026-07-04**: full inventory, canonical-pipeline
  documentation, and consolidation plan produced — `docs/systems/system2/EXECUTION_PIPELINE_INVENTORY.md`,
  `CANONICAL_EXECUTION_PIPELINE.md`, `PIPELINE_CONSOLIDATION_PLAN.md`. Confirmed `run_st_a2_demo.py`
  is the one canonical execution lifecycle (every stage — startup through shutdown — appears in
  exactly one module) and identified three parallel stacks beyond the already-known
  `run_portfolio.py`: a dormant `bot.py` stack (`OrderManager`/`MetaAPIClient`/`RiskManager`, no
  systemd unit, real but unused test coverage), a dormant `adaptive/run_shadow.py` stack, and a
  411-line "Production Platform v2" cluster (`production/{recovery,operations,reporting,api}.py` +
  `production/engine/{orders,positions,risk}.py`, introduced already-disabled by commit `e009d5f`
  "Complete disabled System 2 execution platform") with **zero callers outside its own dedicated
  test files**. Removed the latter (genuinely dead code, zero live-path risk) along with its test
  file and the one dead-code-dependent test function in `test_system2_demo_readiness.py`; cleaned
  `production/engine/__init__.py`'s now-broken re-exports. **Deliberately not touched**: the `bot.py`
  and `adaptive/run_shadow.py` stacks — both have real, passing, if-dormant test coverage; removing
  or merging either is a product/scope decision, not a mechanical dedup (see consolidation plan
  Tier 3). `run_portfolio.py` itself remains exactly as Sprint 2.2 left it (blocked, not deleted) —
  its package-validation CLI path is still real, tested coverage with no equivalent elsewhere.
  Verified: full suite 1570 passed / 29 failed (all 29 confirmed pre-existing and unrelated via
  `git stash` — `test_db_preflight.py`'s own known bug, `test_lifecycle_authority.py`'s DB-fixture
  dependency, `test_pipeline.py`, one strategy-adapter test) / 4 skipped; `tests/production` 42→33
  (9 dead tests removed, zero regressions); the live production runner re-verified unaffected
  throughout (0 restarts, broker connected, 38+ minutes uptime at verification time).
- [x] **Operations Control Center, Phase 5 — 2026-07-04**: exposed the existing platform through
  eight new read-only endpoints in `dashboard/status_server.py` — **the only actually-deployed**
  dashboard backend (`live-dashboard.service`; `app.py`/`live_app.py` remain undeployed, unchanged).
  `GET /api/operations/{health,account,positions,orders,trades,strategy,risk,events}`, consistent
  envelope (`{"data", "source", "fetched_at", "unavailable"}`), every one a thin slice over an
  existing service — `dashboard/live_dashboard_service.py::load_snapshot()` (already used by
  `/api/new-dashboard/live-state`), `TradeJournalDB`, the runner's own `strategy_demo_state.json`,
  `logs/risk_state.json`/`portfolio_state.json`, and new read helpers
  (`execution/operations_recorder.py::get_recent_events()`/`get_recent_runtimes()`) against the
  Sprint 2.3 `operations.*` Postgres tables — the first code to ever read them back. No new business
  logic, no new broker/DB connections beyond what those services already open. Full detail and
  per-widget source mapping: `docs/dashboard/DASHBOARD_BACKEND_MAPPING.md`'s "Phase 5 update"
  section. **Also fixed** (defect discovered during validation, not a redesign): two incomplete
  edits in `dashboard/strategy_service.py` (an orphaned `raise` missing its `if not result.success:`
  guard, and a `for` loop missing its own statement) were breaking `import dashboard.app` and
  therefore all of `tests/test_dashboard_app.py`'s collection — both were pre-existing, unrelated to
  this pass's own changes, syntax-level breakage, not an architecture decision. Verified: full
  suite 1570 passed / 29 pre-existing failures (unchanged) / 4 skipped; all 8 new endpoints return
  HTTP 200 with real data against the live system; `live-dashboard.service` restarted cleanly (0
  restarts since) to load the change; `smc-demo-runner.service` unaffected throughout (0 restarts).
  **Known, pre-existing limitation surfaced, not introduced**: `/api/operations/account`/`positions`
  can return zeroed/degraded values because `live_dashboard_service.py` opens its own separate
  MetaAPI session, decoupled from the runner's own connection (already documented in this file's
  Executive Summary and `DASHBOARD_BACKEND_MAPPING.md` before this pass).
- [x] **Operational Dashboard Integration, Phase 6 — 2026-07-04**: the Gai dashboard frontend
  (`New Dashborad/Gai dashboard/`) is now wired to real System 2 data end-to-end, verified by
  actually running it and loading it in a browser (Playwright), not just by inspecting code.
  - Added `GET /api/new-dashboard/live-state` to `dashboard/status_server.py` — the same
    `LiveDashboardState`-shaped payload `dashboard/app.py` already served (via the existing,
    unchanged `dashboard/live_state_adapter.py::build_live_state()`), now also on the actually-deployed
    backend. No logic duplicated; a second route registration of an existing function.
  - `SocketContext.tsx`'s REST-fallback poll target changed from the incompatible `/api/status` to
    this endpoint. Its dev server (`server.ts`, an Express+`ws` simulator with hardcoded fake state)
    had its own fake WebSocket ticking **removed** (no real WebSocket backend exists —
    simulating one would show fake data instead of real backend state, defeating the integration)
    and gained a real HTTP proxy route forwarding to the actual Python backend
    (`BACKEND_URL`, default `http://127.0.0.1:8090`). The frontend's existing WS-fail→poll fallback
    now correctly engages against real data instead of a fake feed.
  - **Two real defects found only by loading the page in a browser** (exactly why this validation
    step matters, not a formality): (1) `dashboard/strategy_service.py::_build_strategy_packages()`'s
    real `risk_profile` object (`{stopLossPct, takeProfitPct, ...}`) crashed React, which only ever
    expected the mock's simple string label — fixed by widening `types.ts` and rendering the object
    sensibly (`StrategyRuntimeStatus.tsx`) instead of dumbing down the real, more detailed backend
    data to fit the mock's assumption. (2) `state.riskControls.autoDisableConditions` doesn't exist
    on the real backend (that's an editable-operator-controls feature not built yet, correctly
    deferred to the "Operator Controls" milestone) — crashed on `undefined.newsEvent`; fixed with
    defensive defaults in `LiveOperationsDashboard.tsx`, not fabricated backend values.
  - Verified via Playwright: LIVE tab renders real strategy catalog (`ST-A2`, `LondonBreakout`, etc.),
    real (if `DEGRADED`, honestly shown) broker gateway status, real $0.00/0.0% figures matching the
    actual empty-position state, a real EURUSD candlestick chart, zero console errors, zero crashes.
  - New tests: `tests/test_status_server.py` (6 new, covering `/api/new-dashboard/live-state`
    delegation and the full `/api/operations/*` family). Full suite: 1575 passed, same 29
    pre-existing failures, 4 skipped. Both `smc-demo-runner.service` and `live-dashboard.service`
    verified healthy (0 restarts) throughout; the dev server used for browser verification was
    stopped afterward — not a production deployment mechanism.
  - **Not done, deliberately, per this task's own scope**: building/deploying the frontend to be
    served by `status_server.py` itself (still requires `vite build` + a static-serving route
    decision — see `docs/dashboard/DASHBOARD_IMPLEMENTATION_PLAN.md`'s existing cutover note);
    the `SVOS`/`SUGGESTIONS` tabs (System 1/fabricated-data territory, out of scope); Operator
    Controls (pause/resume/kill-switch/risk-control-editing) — none of their backend endpoints exist
    yet, correctly left as the next-but-one milestone; WebSocket/Event Streaming itself.
- [x] **Legacy `/dashboard/` route staleness fix — 2026-07-04**: the pre-existing server-rendered
  HTML dashboard (`dashboard/status_server.py`'s `/dashboard/` route, publicly reachable at
  `http://34.87.36.159:8090/dashboard/` — a real, already-deployed surface distinct from the Gai
  SPA above) had two live staleness bugs, found by checking the actual public URL: (1) a hardcoded
  "Strategy Guide — SMCOrderBlockFVGSession" heading, reworded to not claim it describes whichever
  strategy is currently running (the header elsewhere on the same page already correctly showed
  `ST-A2`, dynamically, from `state.get("strategy")` — only this one static label was stale); the
  `state.get("strategy", ...)` fallback default in the page-header renderer was also changed from
  the hardcoded broken strategy name to a neutral `"unknown"`. (2) `_load_log()` returned the
  *first* candidate log file that merely existed (`smc_ob_fvg_demo.log`, last written 2026-07-01,
  three days stale) instead of the one actually being written to (`strategy_demo.log`, live) —
  fixed to pick whichever candidate has the most recent mtime. Verified against the live,
  running service: the `/dashboard/` route now shows current (today's) log timestamps and no
  remaining reference to the unregistered strategy name. New test:
  `tests/test_status_server.py::test_load_log_prefers_most_recently_written_file_not_first_existing`.
  Full suite: 1576 passed, same 29 pre-existing failures; both services healthy (0 restarts)
  throughout; `live-dashboard.service` restarted to load the fix.
- Port `execution/startup_recovery.py`'s broker-truth reconciliation (implemented for
  `run_st_a2_demo.py` in Phase 1, 2026-07-04) into whichever runner survives the pipeline port —
  or confirm it already covers `run_portfolio.py` once absorbed. **Not started** for
  `run_portfolio.py` itself; the reconciliation logic exists and is reusable, this is a wiring task
  now, not new-capability design.
- Retire `production/engine/orders.py`/`positions.py` if `execution/trade_manager.py` remains the
  chosen path, or migrate to them if the reverse is chosen — do not leave both. **Not started.**
- Deploy the winning runner via a proper systemd unit; retire the losing one's unit. **Not
  started** — no systemd/deployment change has been made; `run_portfolio.py` is still present and
  unretired pending the actual pipeline port above.
- Acceptance: exactly one execution engine has a systemd unit; crash-mid-order test resolves
  automatically on restart. **Not met yet.**
- [x] **Sprint 2.4 — 2026-07-05**: `RiskFirewall` — the "real, non-allow-all risk gate" Sprint 2.1
  explicitly left out of scope — landed as `production.engine.EmergencyStopRiskGate`, wrapping
  `AllowAllRiskGate` in `scripts/run_st_a2_demo.py`'s `CanonicalExecutionPipeline`. It reads
  `dashboard/control_state.py`'s `load_control_state()` fresh on every `pipeline.submit()` call
  (never cached, so a stop activated or cleared mid-run takes effect on the very next intent) and
  rejects before the adapter — and therefore the broker — is ever reached whenever an emergency
  stop is active. This is defense-in-depth, not a behavior change for the deployed runner: `_tick()`
  already returns before reaching signal generation while blocked (Phase 1), so `AllowAllRiskGate`
  alone was already safe in practice; this gate protects any *future* caller of `pipeline.submit()`
  that doesn't replicate that early-return exactly — including whatever this Phase 2 port eventually
  produces. Also added a per-tick structured log line explaining the pause (reason/source/
  activated_at) — previously only the first tick of a new activation logged anything, every
  blocked tick now does. Deliberately does **not** touch `run_portfolio.py`: extending that file
  independently of this port would recreate the exact two-runner drift this phase exists to close
  (confirmed against this file's own recorded decision above before starting). Dashboard/monitoring
  exposure needed no new work — `control_state.json`'s `emergency_stop` was already surfaced via
  `/api/operations/health`, `/overview`, and the control endpoints. Evidence:
  `tests/production/test_canonical_execution_pipeline.py` (7 new: gate unit tests, full-pipeline
  rejection/approval, fresh-state-not-cached regression), `tests/execution/test_emergency_stop_integration.py`
  (4 new: active-at-startup, cleared-during-runtime-resumes-normal-processing, broker-disconnect-
  while-active graceful degradation, structured pause logging). 11 new tests (20 total across both
  files), all passing; `run_portfolio.py`'s own known gaps (this table's Phase 2 row above) are
  unchanged.

### Phase 3 — Consolidate Dashboard, API, and Strategy-Loader Duplication
- Merge `app.py`/`live_app.py`/`status_server.py` into one backend serving both operational and
  New Dashboard routes; install its systemd unit.
- Apply the CONFIRM-token pattern consistently to every real mutation endpoint.
- Connect Pipeline A (`production/importer.py`/`verifier.py`) to whatever the canonical runner
  actually loads, or formally retire Pipeline A in favor of Pipeline B's config-driven loading —
  do not leave them disconnected.
- Acceptance: one dashboard process reachable at one URL; `grep` confirms no duplicate route
  definitions across files; an imported/verified package is demonstrably what the runner executes.

### Phase 4 — Observability and Deployment Hygiene
- Feed `/api/v1/production/health`'s heartbeat from the actual canonical runner.
- Add freshness timestamps to every dashboard widget.
- Confirm/wire Telegram alerting for whichever runner is canonical post-Phase-2.
- Document the final deployment topology (systemd units, ports, processes) as the new
  `docs/architecture/system_architecture.md` source of truth, retiring stale duplicates.
- Acceptance: `/api/v1/production/health` correctly reports unhealthy when the tick loop is
  killed; every dashboard widget shows a last-updated indicator.

---

## References

- `docs/operations/system2_readiness_implementation_plan.md`
- `docs/operations/production_readiness_report.md`
- `docs/operations/current_operational_status.md`
- `docs/operations/deployment_runbook.md`
- `docs/operations/risk-register.md`
- `docs/operations/monitoring_endpoints.md`
- `docs/VERDICT_LOG.md`
