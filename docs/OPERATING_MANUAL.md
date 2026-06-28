# Operating Manual

This manual is for the project owner or operator. It explains how to run,
monitor, pause, recover, and review the platform without changing trading
logic.

## Project Overview

This repository is an institutional-style trading platform built around five
control layers:

- Research and validation
- Execution and broker integration
- Risk controls and firewalls
- Governance and promotion gates
- Monitoring, reporting, and recovery

The platform is designed to stop unsafe promotion, keep research evidence
separate from execution evidence, and give the owner a clear operating process.

## System Architecture

Current lifecycle source of truth:

- `docs/SYSTEM_ARCHITECTURE.md`
- `config/strategy_catalog.yaml`

Current practical flow:

1. Research builds evidence.
2. Validation qualifies or rejects the strategy.
3. Execution components simulate or demo-run the strategy.
4. Risk controls decide whether exposure is allowed.
5. Governance decides whether a strategy can move forward.
6. Monitoring and reports decide whether the system remains safe.

Core operator-facing components:

- Research engine: `research/`, `src/`, `pipeline/`
- Strategy logic: `strategy/`, `strategies/`, `adaptive/`
- Execution layer: `execution/`
- Risk and portfolio layer: `execution/demo_risk_manager.py`, `core/portfolio_manager.py`
- Validation layer: `research/svos/`, `research/validation/`, `execution_validation/`
- Monitoring and status tools: `scripts/health_check.py`, `scripts/demo_status.py`, `scripts/generate_reports.py`

## Research Pipeline

Purpose:
Turn raw historical or replay data into strategy evidence.

Typical flow:

1. Acquire or normalize market data.
2. Build features.
3. Run replay, backtest, robustness, and validation workflows.
4. Save reports, metrics, and verdicts.

Important files:

- `scripts/build_research_db.py`
- `scripts/run_research_queue.py`
- `scripts/run_research_sweep.py`
- `research/`
- `src/`

Operator objective:
Confirm that strategy evidence exists before any demo or live decision.

## Data Pipeline

Purpose:
Maintain usable market data, derived features, and analytics storage.

Main storage patterns in this repo:

- Local file-based analytics such as DuckDB
- SQLite journals for runtime trade history
- Optional PostgreSQL-style runtime health checks depending on configuration

Checkpoints:

- `config/research_engine.yaml`
- `data/trade_journal.db`
- `research/e6_dataset_snapshot/`
- `db/`

Operator checks:

- Data files exist and are fresh.
- No missing daily inputs for the active strategy.
- Database health report is not failing.

## Strategy Pipeline

Purpose:
Move a strategy from idea to governed deployment.

High-level lifecycle:

1. Strategy audit
2. Replay
3. Backtest
4. Robustness
5. Verification-ready decision
6. Demo or execution validation
7. Production approval only after governance sign-off

Current strategy state is authoritative in:

- `config/strategy_catalog.yaml`

Operator rule:
If a document conflicts with the strategy catalog, the catalog wins.

## Validation Pipeline

Purpose:
Decide whether a strategy should advance.

Main validation families:

- SVOS research validation
- Execution validation and replay bridge
- Regression checks
- Strategy registry promotion control

Important files:

- `research/svos/engine.py`
- `research/validation/engine.py`
- `execution_validation/`
- `config/validation.yaml`
- `scripts/run_current_strategy_validation.py`
- `scripts/run_svos_pipeline.py`

Operator meaning:

- `PASS` means evidence supports forward movement.
- `FAIL` means do not promote.
- `verification_ready` is not live approval. It only means research evidence is acceptable for the next controlled stage.

## Risk Management Pipeline

Purpose:
Prevent capital damage from bad strategy behavior, infrastructure problems, or
operator mistakes.

Primary controls in the current implementation:

- Per-trade risk limits
- Max open positions
- Daily loss guard
- Consecutive loss guard
- Portfolio loss limits
- Emergency halt state

Important files:

- `execution/demo_risk_manager.py`
- `execution/risk_manager.py`
- `config/risk.yaml`
- `docs/RISK_SPEC.md`

Operator meaning:

- If risk state is halted, do not resume trading until the cause is understood.
- A pass on research does not override a risk halt.

## Execution Pipeline

Purpose:
Convert approved signals into controlled broker interactions.

Main execution components:

- Broker connectivity: `execution/mt5_connector.py`, `execution/metaapi_client.py`
- Demo execution: `execution/vantage_demo_executor.py`
- Position and order coordination: `execution/order_manager.py`, `execution/trade_manager.py`
- Journaling and logs: `execution/trade_logger.py`, `execution/trade_journal.py`

Operator rule:
Report generation is read-only. It must not place orders.

## Monitoring Pipeline

Purpose:
Tell the owner whether the system is healthy enough to keep operating.

Main tools:

- `python scripts/health_check.py`
- `python scripts/demo_status.py`
- `python scripts/generate_reports.py --type ...`
- `docs/PROJECT_STATUS.md`

Monitoring artifacts:

- `logs/`
- `reports/`
- `docs/PROJECT_STATUS.md`

## Incident Response Process

1. Stop new exposure.
2. Confirm whether any position is still open.
3. Run offline-safe checks first.
4. Review recent logs and the latest incident/system-health reports.
5. Restore only after the failure mode is understood.
6. Record the event in `reports/incidents/`.

Recommended first commands:

```bash
python scripts/health_check.py --no-broker
python scripts/generate_reports.py --type incident
python scripts/generate_reports.py --type system-health
```

## Daily Operating Checklist

1. Confirm current strategy and registry state in `config/strategy_catalog.yaml`.
2. Run `python scripts/health_check.py --no-broker`.
3. Review latest `reports/daily/` report.
4. Confirm risk status is not halted.
5. Confirm database or journal inputs exist.
6. Review recent errors in `logs/`.
7. If running demo, verify the mode is still demo and not live.

## Weekly Review Checklist

1. Generate weekly, strategy, risk, and system-health reports.
2. Compare performance with the current lifecycle stage.
3. Review rejected signals and incident trends.
4. Check whether any strategy should be paused or demoted.
5. Review recovery readiness and restart evidence.

## Monthly Strategy Review Checklist

1. Generate monthly and live-readiness reports.
2. Compare current results with historical validation expectations.
3. Review drawdown, expectancy, and robustness trend.
4. Review governance status before any promotion.
5. Freeze or retire strategies that fail the owner’s acceptance criteria.

## Demo Trading Workflow

1. Confirm the strategy is allowed to run in demo.
2. Confirm `LIVE_TRADING=false`.
3. Confirm the health check is clean enough for demo.
4. Confirm risk guards and recovery state are healthy.
5. Run the demo process approved for that strategy.
6. Review daily, execution, and risk reports after the session.

## Live Trading Readiness Checklist

Before live exposure, confirm all of the following:

- Strategy registry and validation evidence support promotion.
- Cost validation has been completed for the current broker profile.
- Risk firewall is passing.
- Recovery and restart behavior are proven.
- Incident count is acceptable.
- Latest live-readiness report verdict is appropriate.
- Owner has explicitly approved the transition.

If any item is unclear, do not trade live.

## Emergency Stop Procedure

1. Stop the runner or demo process.
2. Do not restart immediately.
3. Confirm open positions at the broker level before any further action.
4. Generate incident and system-health reports.
5. Preserve logs and journals.
6. Resume only after root-cause review.

Use this when:

- Risk halt is engaged
- Broker/API instability is recurring
- Data is stale or missing
- Unexpected orders or repeated rejects appear

## Database Recovery Procedure

1. Determine the active backend from config and runtime environment.
2. Confirm whether the failure is reachability, corruption, or missing file.
3. Run `python scripts/health_check.py --no-broker`.
4. If SQLite or DuckDB is used, confirm the file exists and is readable.
5. If PostgreSQL is used, confirm host, port, and service reachability.
6. Rebuild only after preserving the current artifact.

Operator note:
Do not delete existing journals or reports during recovery.

## Broker/API Failure Procedure

1. Treat broker failure as an operational risk event.
2. Run offline-safe health and incident reports first.
3. Inspect recent logs for timeout, disconnect, and reconnect messages.
4. Confirm whether any open positions remain unmanaged.
5. Keep the system paused until connectivity is stable again.

Useful commands:

```bash
python scripts/health_check.py --no-broker
python scripts/generate_reports.py --type incident
python scripts/generate_reports.py --type live-readiness
```

## How To Read Logs

Primary log locations:

- `logs/bot.log`
- `logs/st_a2_runner.log`
- `logs/portfolio_demo.log`
- `logs/trades.jsonl`
- strategy-specific demo journals in `logs/*.jsonl`

What to look for:

- `ERROR`, `CRITICAL`, `FATAL`
- `DISCONNECTED`, `RPC timeout`, `reconnect`
- `SIGNAL_CREATED`, `ORDER_SUBMITTED`, `ORDER_FILLED`, `ORDER_REJECTED`, `POSITION_CLOSED`

Interpretation rule:
One isolated error is not always an incident. Repeated errors or any mismatch between risk state and execution state should be treated as an incident.

## How To Restart Services Safely

1. Generate a system-health report first.
2. Confirm no unmanaged open position exists.
3. Confirm the current mode is still correct.
4. Restart only the approved runner for the current strategy.
5. Confirm a healthy heartbeat or runner activity after restart.
6. Generate a fresh daily or incident report after restart.

## How To Know Whether System Is Safe To Trade

The system is safe to trade only when all of these are true:

- Current mode is intentional and not accidentally live.
- Risk report shows no breach requiring pause.
- System-health report does not show a blocking failure.
- Database/journal inputs are available.
- Latest incident review does not indicate unresolved instability.
- Live-readiness verdict is appropriate for the intended mode.

Practical rule:
If you cannot clearly answer "what strategy is active, what mode is active, what risk state is active, and what the latest verdict is," then the system is not safe to trade.
