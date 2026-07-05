# Execution Pipeline Inventory

Date: 2026-07-04
Status: Inventory — no code changed to produce this document
Scope: System 2 (production/demo execution) only. `execution_simulator/` (replay/backtest virtual
broker) is System 1/research-adjacent and out of scope per this task's "do not redesign SVOS"
constraint — noted in §6 for completeness, not analyzed further.

---

## 1. Runners (entry points)

| Runner | Purpose | Deployment | Classification |
|---|---|---|---|
| `scripts/run_st_a2_demo.py` (invoked via `scripts/run_strategy_demo.py` shim) | ST-A2 demo execution — the actual live production runner | **systemd: `smc-demo-runner.service`, active, deployed** | **Production — canonical** |
| `scripts/run_portfolio.py` | Multi-strategy (5-strategy) portfolio runner, architecturally uses `CanonicalExecutionPipeline` with a real `_PortfolioRiskGate` | No systemd unit; blocked from starting by default (`RUN_PORTFOLIO_ALLOW_START` guard, Sprint 2.2) | **Deprecated (intentionally blocked)** — still used by real tests as WS1 canonical-package-validation CLI coverage; not a live execution path |
| `bot.py` (repo root) | "DEP-01" original main loop: `MetaAPIClient` → `OrderManager` → `TradeLogger`, ST-A2 signal chain, no `strategies/adapters` registry | No systemd unit anywhere in this repo | **Deprecated/dormant** — earlier-generation architecture, superseded by `run_st_a2_demo.py` |
| `adaptive/run_shadow.py` | "S6" shadow/paper runner for adaptive strategies (regime+score+risk), DRY_RUN only, no real orders | No systemd unit | **Experimental/dormant** |
| `scripts/run_d2_e3_demo.py` | D2/D3 strategy demo runner | `deploy/gcp-vm1/systemd/d2e3.service` exists as a **file only** — never installed in `/etc/systemd/system/` (confirmed via `systemctl is-enabled` → `not-found`) | **Deprecated (file-only, never enabled)** |

## 2. Order managers

| Component | Used by | Classification |
|---|---|---|
| `execution/trade_manager.py::TradeManager` | `run_st_a2_demo.py`, `run_portfolio.py`, `production/engine/services.py` (clean re-export, not a fork), `dashboard/live_dashboard_service.py` | **Production — canonical.** Owns retry/backoff, the `ExecutionStateStore` state-machine wiring, and idempotency (Phase 1 work) |
| `execution/order_manager.py::OrderManager` | `bot.py` only (plus its own dedicated tests) | **Deprecated/dormant** — belongs to the `bot.py` stack, no live caller |
| `production/engine/orders.py`, `production/engine/positions.py` | Only `production/engine/__init__.py` (re-export) and `tests/production/test_system2_platform.py` (their own dedicated test) — **zero callers in any runner** | **Dead code**, part of the larger cluster below |

**Correction/expansion**: `tests/production/test_system2_platform.py` also imports
`production/recovery.py::RecoveryManager`, `production/operations.py::PostgresOperationsRepository`,
`production/reporting.py::OperationsReportService`, and `production/api.py::ProductionReadAPI`
(the latter also used by `tests/production/test_system2_demo_readiness.py`, with fake test doubles,
not the real Postgres-backed classes). Together with `production/engine/{orders,positions,risk}.py`,
this is a **complete, internally-consistent, 411-line parallel "Production Platform v2"** —
its own recovery-step framework (`RecoveryManager.STEPS = (ownership, package, checkpoint, adapter,
reconcile_account, reconcile_orders, reconcile_positions, ambiguous_submissions)`), its own
Postgres operations repository, its own reporting service — entirely disconnected from
`run_st_a2_demo.py`. Introduced by commit `e009d5f "Complete disabled System 2 execution platform"`
— disabled by its own commit message, not an accidental orphan. Exercised only by its own dedicated
test files, never by any real runner.

## 3. Broker adapters

| Component | Used by | Classification |
|---|---|---|
| `execution/mt5_connector.py::MT5Connector` + `execution/vantage_demo_executor.py::VantageDemoExecutor` | `run_st_a2_demo.py`, `run_portfolio.py`, `dashboard/live_dashboard_service.py`, `scripts/reconcile_positions.py`, `scripts/health_check.py`, `scripts/demo_status.py`, `scripts/demo_health_check.py` | **Production — canonical** |
| `execution/metaapi_client.py::MetaAPIClient` | `bot.py`, `scripts/run_d2_e3_demo.py`, `scripts/capture_spreads.py`, `execution/order_manager.py` | **Deprecated/dormant** — the `bot.py`/D2E3 stack's own broker client, a parallel implementation of what `mt5_connector.py` does for the live path |
| `execution/mt5_executor.py` | `adaptive/run_shadow.py` only | **Experimental/dormant** |

## 4. Risk integrations

| Component | Used by | Classification |
|---|---|---|
| `execution/demo_risk_manager.py` (functions: `new_state`, `check_limits`, `record_result`, `reset_daily`) + `core/portfolio_manager.py::PortfolioManager` + `core/circuit_breaker.py::CircuitBreaker` | `run_st_a2_demo.py` (all three), `run_portfolio.py` (`PortfolioManager`/`CircuitBreaker`) | **Production — canonical.** Independent implementation, not a fork of `execution/risk_manager.py` (verified — no import relationship) |
| `execution/risk_manager.py::RiskManager` | `bot.py`, `execution/order_manager.py`, `adaptive/engine/risk_manager.py` (a further adaptive-specific wrapper) | **Deprecated/dormant** — the `bot.py` stack's own risk engine |
| `production/engine/risk.py` (`RiskFirewall`, `AccountSnapshot`, `MarketSnapshot`, `RiskContext`) | Only `production/engine/__init__.py` re-export + `tests/production/test_system2_platform.py` | **Dead code** — part of the "Production Platform v2" cluster, see §2 correction |

## 5. Recovery logic

| Component | Used by | Classification |
|---|---|---|
| `execution/startup_recovery.py::reconcile_pending_executions()` + `execution/execution_state.py::ExecutionStateStore` | `run_st_a2_demo.py` only (wired at startup, Phase 1 work) | **Production — canonical, and currently the ONLY recovery implementation that actually runs.** `run_portfolio.py` never calls `recover_incomplete()` at all (confirmed, unchanged from Sprint 2.2's analysis) — not a duplicate, a genuine gap. `bot.py`/`adaptive/run_shadow.py` have no equivalent recovery logic at all. |

## 6. Scheduler / deployment entry points

| Unit | Installed in `/etc/systemd/system/`? | Points at |
|---|---|---|
| `smc-demo-runner.service` | **Yes, active** | `run_st_a2_demo.py` via `run_strategy_demo.py` shim — the only live production execution process |
| `live-dashboard.service` | **Yes, active** | `dashboard/status_server.py` |
| `d2e3.service`, `d2e3-journal-sync.{service,timer}`, `reconcile-positions.{service,timer}`, `agtrade-deployment-agent.{service,timer}` | **No — file-only** in `deploy/gcp-vm1/systemd/`, never symlinked/copied into `/etc/systemd/system/` | Legacy/unused deployment artifacts |
| `benchmark-bot.service`, `smc-bot.service` | **Removed** (Phase 3 stabilization pass, archived to `/home/aungp/archives/systemd-units/`) | N/A — targets already deleted |
| `run_portfolio.py`, `bot.py`, `adaptive/run_shadow.py` | **No unit at all** | Not deployed by any mechanism found |

## 7. Strategy loaders

| Loader | Used by | Classification |
|---|---|---|
| `strategies/adapters/__init__.py::ADAPTER_TYPES` / `build_strategy()` + `core/strategy_registry.py` | `run_st_a2_demo.py`, `run_portfolio.py` | **Production — canonical.** Config-driven (`config/strategy_portfolio.yaml`), not signed-package-verified — this is "Pipeline B" per `SYSTEM2_MASTER_PLAN.md` |
| `approval_package/package_validator.py` + `scripts/validate_strategy_identity.py` (canonical signed-package verification) | `run_portfolio.py`'s `main()` only | **Real, tested, but disconnected from what actually executes** — "Pipeline A" per `SYSTEM2_MASTER_PLAN.md`, exercised by `tests/portfolio/test_strategy_package_cli.py`/`tests/integration/test_canonical_package_handoff.py` as package-validation coverage, not a live path |
| `bot.py`'s inline ST-A2 wiring | `bot.py` only | **Deprecated/dormant** — no registry, no package validation, direct strategy-function call |

## 8. Out of scope (noted, not analyzed)

`execution_simulator/` (`VirtualBroker`, `FillEngine`, `RiskEngine`, `ReplayRunner`, etc.) is a
historical-replay/backtest simulation engine — System 1/research territory, not a competing System 2
production execution path. It happens to import `execution/metaapi_client.py` for type/data reuse,
which does not make it part of the production duplication problem. Left untouched per "do not
redesign SVOS."

## 9. Summary — real duplication vs. accurate reuse

**Genuine dead code** (zero live callers, safe to remove after test-parity confirmation): the full
"Production Platform v2" cluster — `production/engine/{orders,positions,risk}.py` +
`production/{recovery,operations,reporting,api}.py` — 411 lines total, exercised only by its own
dedicated test files (`tests/production/test_system2_platform.py`, and `test_system2_demo_readiness.py`
for `api.py` specifically, via fakes). Never imported by `run_st_a2_demo.py` or `run_portfolio.py`.

**Genuine parallel stacks** (not dead, but not canonical — dormant, no deployment, lower risk to
leave alone than to force a merge): the `bot.py` stack (`OrderManager`/`MetaAPIClient`/`RiskManager`)
and the `adaptive/run_shadow.py` stack (`mt5_executor.py`). Neither is deployed; consolidating them
into the canonical runner would mean *adding* multi-strategy/shadow capability to
`run_st_a2_demo.py` — a feature-scope decision, not a mechanical dedup, and explicitly out of this
task's "do not implement new trading strategies" / "prefer consolidation over expansion" guidance
read narrowly (there is nothing live to consolidate *from* here; they're already inert).

**Not duplication, confirmed by import-graph inspection**: `production/engine/services.py` is a
clean re-export of the canonical `execution/` modules, not a fork. `execution/demo_risk_manager.py`
is an independent, tested implementation, not a copy of `execution/risk_manager.py`.

**The one real, actionable gap**: `run_portfolio.py` lacks `execution/startup_recovery.py` wiring.
Since `run_portfolio.py` remains intentionally blocked/deprecated (Sprint 2.2), this is correctly
left unfixed rather than duplicating recovery-wiring effort into a runner that isn't deployed.
