# Canonical Execution Pipeline

Date: 2026-07-04
Status: Descriptive — documents the lifecycle as it actually exists today in the one production
runner (`scripts/run_st_a2_demo.py`, deployed as `smc-demo-runner.service`). This is not a proposed
future design; per `docs/systems/system2/EXECUTION_PIPELINE_INVENTORY.md`, this runner is already
the canonical path — every stage below appears exactly once, in exactly one module.

Authority note, updated 2026-07-12: `docs/00_Project/TWO_SYSTEM_ARCHITECTURE_TRUTH.md` is the
single source of truth for the System 1/SVOS and System 2/Execution split. `SYSTEM2_MASTER_PLAN.md`
at the repo root is the current System 2 readiness implementation plan. This file describes an
existing transitional runner and must not be used to authorize strategy approval, paper/demo
execution, or live trading. No strategy currently has Production Approval.

---

## Lifecycle stages

| # | Stage | Implementing module | Notes |
|---|---|---|---|
| 1 | **Startup** | `scripts/run_st_a2_demo.py::run()` | Creates connector, executor, journal, telegram alerter, `ExecutionStateStore`, `TradeManager`, `OperationsRecorder`, `CanonicalExecutionPipeline` + `RuntimeContext`, in that order |
| 2 | **Configuration loading** | `scripts/run_st_a2_demo.py::main()` | `argparse` (`--mode`, `--strategy`, `--interval`) with env-var fallbacks (`TRADING_MODE`, `DEMO_STRATEGY`); `.env` loaded via `dotenv` at module import |
| 3 | **Strategy loading** | `core/strategy_registry.py` (`register_strategy`/`get_strategy`) + `strategies/adapters/__init__.py` (`ADAPTER_TYPES`/`build_strategy`) | Config-driven ("Pipeline B" — see inventory doc §7); one process runs exactly one strategy, selected by `--strategy` |
| 4 | **Broker initialization** | `execution/mt5_connector.py::MT5Connector.connect()` | Real MetaAPI websocket session against the Vantage demo account; `ensure_connected()` re-checked proactively at the top of every tick |
| 5 | **Market data** | `_tick()`'s "Phase 1: Gather market data" block | Per-pair M15+H4 candle fetch, spread check against `MAX_SPREAD_PIPS`, session gate (`_session_gate()`) |
| 6 | **Signal evaluation** | `_tick()`'s "Phase 2: Generate signals" block → `strategy.generate_signal(...)` | Strategy adapter is the only place signal logic runs; runner never re-implements strategy rules |
| 7 | **Risk validation** | `CircuitBreaker.record_signal()` → `StrategyExecutionGuard` (governance) → `TradingPermissionService` (permission/emergency-stop) → `PortfolioManager.any_loss_limit_hit()` → `execution.demo_risk_manager.check_limits()` | Layered, in this order; any layer can reject before an order is ever constructed. `AllowAllRiskGate` at the pipeline-submit layer (stage 8) is correct specifically because this stage already decided — see Sprint 2.1 rationale in `SYSTEM2_MASTER_PLAN.md` |
| 8 | **Order placement** | `production.engine.CanonicalExecutionPipeline.submit(ExecutionIntent(...))` → `DemoExecutionAdapter` callback → `execution/trade_manager.py::TradeManager.open_position()` | Sprint 2.1 wiring; the adapter callback is the *only* call site that reaches the broker for a new order |
| 9 | **Execution monitoring** | `execution/execution_state.py::ExecutionStateStore` (durable per-order state machine) + `execution/operations_recorder.py::OperationsRecorder.event_sink()` (Postgres `operations.*`, Sprint 2.3) | Every pipeline event (`intent_received`, `risk_decision`, `execution_result`) is durably logged in two places: JSONL (`logs/execution_pipeline_events.jsonl`) and Postgres, from the same event stream — not two separate logging paths |
| 10 | **Position management** | `TradeManager.get_positions()`, called once per tick | Read-only broker position snapshot; feeds both the dashboard state file and stage 11 |
| 11 | **Position closing** | `execution/position_close_detector.py::diff_closed_positions()` + `execution/close_reconciliation.py::process_closed_positions()` | Diffs this tick's positions against the previous tick's snapshot (`risk_state["_last_positions"]`, persisted across restarts) to detect closes |
| 12 | **Risk feedback** | `execution/close_reconciliation.py` calling `demo_risk_manager.record_result()` and `CircuitBreaker.record_trade(won=...)` | Real close outcome only — never a hardcoded value (the defect this exact pattern fixed in `run_st_a2_demo.py`, and the reason `run_portfolio.py` remains blocked per Sprint 2.2) |
| 13 | **Portfolio updates** | `core/portfolio_manager.py::PortfolioManager.record_trade()` (on open) / `.record_close()` (on close) | One-per-symbol guard and daily/weekly/monthly P&L counters; persisted every tick (`_save_portfolio_state()`) |
| 14 | **Recovery** | `execution/startup_recovery.py::reconcile_pending_executions()`, called once in `run()` before the tick loop starts | Resolves any non-terminal `ExecutionRecord` against broker truth; never resubmits (Phase 1 work). Also processes any close that happened while the process was down |
| 15 | **Shutdown** | `run()`'s `finally` block | Persists risk/portfolio state, writes final dashboard state, sends a Telegram daily summary, disconnects the broker cleanly |

## Cross-cutting concerns (apply across multiple stages, not a stage themselves)

- **Dashboard state**: `_write_state()` writes `logs/strategy_demo_state.json` after every stage
  transition worth surfacing — read by `dashboard/status_server.py`.
- **Persistence**: risk/portfolio JSON snapshots (stages 12-13) and durable order-lifecycle records
  (stage 9) are two distinct concerns, intentionally — see `SYSTEM2_MASTER_PLAN.md`'s "Sprint 2.3"
  entry for why they weren't merged into one ledger this pass.
- **Safety**: `LIVE_TRADING=false`/`DEMO_ONLY=true` are read once at startup (stage 1/2) and checked
  nowhere else — there is exactly one gate, not several redundant ones.

## What is deliberately NOT part of this pipeline

Per `EXECUTION_PIPELINE_INVENTORY.md`: `bot.py`'s stack (`OrderManager`/`MetaAPIClient`/
`RiskManager`), `adaptive/run_shadow.py`'s stack, and `production/engine/orders.py`/`positions.py`/
`risk.py` are not alternate implementations of any stage above — they are dormant, undeployed code
paths. None of them run in production; none of them need to appear in this document as competing
options.
