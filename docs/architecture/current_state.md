# Current State Architecture Audit

Date: 2026-07-01
Scope: read-only architecture analysis of the current repository state
Method: repository structure review, import-path inspection, deployment script review, and prior function inventory reuse

## Executive Summary

Governing target truth is
`docs/00_Project/TWO_SYSTEM_ARCHITECTURE_TRUTH.md`. This audit describes legacy
and transitional reality; it does not authorize a broader Production system or
collapse Backtest with Statistical Validation.

`session-smc-trading-bot` is currently a transitional mixed-boundary platform.

It contains:

- live/demo trading runtime components
- SVOS strategy validation and governance components
- execution validation and simulation components
- research pipelines and historical replay code
- dashboard and operator surfaces
- multiple generations of legacy and compatibility paths

The repository is not yet separated into clean Production, SVOS, and Shared layers.

The strongest current boundary is conceptual, not structural:

- `svos/` is the clearest research/governance core
- `execution/`, `core/`, `strategies/`, and demo runner scripts form the live/demo runtime core
- `dashboard/` mixes production runtime views, operator control functions, and SVOS-facing control/reporting views
- `research/`, `strategy/`, `session_smc/`, `adaptive/`, and `src/` contain overlapping research and strategy logic

The repository therefore behaves as a governed validation-and-execution platform with incomplete separation, not yet as two independently deployable systems.

## Repository Structure

### Primary top-level directories

| Path | Role | Current architectural meaning |
| --- | --- | --- |
| `agtrade/` | canonical CLI entry package | shared application control surface |
| `core/` | strategy registry, portfolio, signal routing, journal | mixed shared/runtime domain layer |
| `execution/` | broker, execution state, order/risk/trade services | production runtime core |
| `strategies/` | runtime strategy adapters | production/runtime integration layer |
| `strategy/` | strategy implementations used in replay/backtest | research strategy layer |
| `svos/` | lifecycle, registry, governance, reports, orchestration | SVOS platform core |
| `research/` | validation, robustness, research queue, SVOS bridge | SVOS and research support layer |
| `strategy_validation/` | strategy-spec validation pipeline | SVOS support layer |
| `strategy_audit/` | audit engine and reports | SVOS support layer |
| `execution_validation/` | EVF-style validation rules and bridge logic | pre-production execution qualification layer |
| `execution_simulator/` | replay broker/fill/risk simulator | SVOS / EVF simulation layer |
| `virtual_broker/` | standalone virtual broker primitives | shared-simulation candidate |
| `dashboard/` | Flask/FastAPI dashboards and operator APIs | mixed production + SVOS presentation layer |
| `db/` | control-plane persistence, migrations, models | shared infrastructure, currently cross-boundary |
| `scripts/` | operational entry points | mixed orchestration surface |
| `pipeline/`, `src/` | feature/replay/research engine stack | legacy research pipeline |
| `adaptive/` | older adaptive execution/research stack | legacy mixed-boundary subsystem |
| `session_smc/` | legacy strategy and replay components | legacy research/runtime subsystem |
| `research_db/` | local research DB helpers and datasets | research infrastructure |
| `deploy/` | deployment scripts, systemd, docker, VM docs | environment and runtime deployment |
| `config/` | strategy catalog, runtime, risk, validation config | global shared configuration |
| `tests/` | current automated tests | validation and architecture enforcement |
| `archive/` | historical snapshots | not part of target active architecture |

### Public entry points

Current user-facing or deployment-facing entry points are:

- `agtrade` console entry point via `pyproject.toml`
- `dashboard/app.py`
- `dashboard/live_app.py`
- `dashboard/status_server.py`
- demo and runtime scripts in `scripts/`
- `run_pipeline.py`
- `bot.py`

### Runtime dependencies

Current declared runtime stack includes:

- FastAPI / Uvicorn
- Flask / Flask-CORS
- SQLAlchemy / Alembic / psycopg2-binary
- Pydantic / JSONSchema / PyYAML
- aiohttp / requests / aiofiles
- pandas / polars / pyarrow / duckdb
- MetaAPI SDK

Current dependency reality:

- the repo supports both synchronous Flask and asynchronous FastAPI surfaces
- the repo supports both file-backed and PostgreSQL-backed control/data flows
- the repo supports both local JSONL state and relational persistence

## Runtime Flow

### Intended live/demo runtime path

```text
market data
  -> execution.metaapi_client / execution.mt5_connector
  -> strategy runtime via strategies.adapters + core.strategy_registry
  -> signal routing via core.signal_router
  -> risk checks via execution.demo_risk_manager / execution.risk_manager / core.portfolio_manager
  -> execution via execution.trade_manager / execution.order_manager / execution.vantage_demo_executor
  -> broker via MetaAPI / MT5 connector
  -> persistence via logs/, core.trade_journal_db, db/, execution state files
  -> dashboard via dashboard/live_app.py and dashboard/status_server.py
```

### Actual observed runtime implementations

Current live/demo execution is split across multiple stacks:

- `scripts/run_st_a2_demo.py`
- `scripts/run_d2_e3_demo.py`
- `scripts/run_strategy_demo.py`
- `bot.py`
- `dashboard/live_dashboard_service.py`

These share many common runtime primitives but do not yet converge on one production engine package.

### SVOS runtime flow

```text
strategy spec
  -> Strategy Audit
  -> svos.application.replay
  -> svos.application.backtest
  -> Statistical Validation gate
  -> svos.application.robustness
  -> svos.application.virtual_demo
  -> svos.registry + governance + reports
  -> dashboard/app.py and report surfaces
```

There are two active orchestration styles:

- `svos/application/*` and `svos/orchestration/service.py`
- `research/svos/engine.py` and `scripts/run_current_strategy_svos.py`

This is one of the main current duplication seams.

## Production Components

The following components are production-oriented or live/demo runtime oriented:

- `execution/`
- `core/`
- `strategies/`
- `monitoring/`
- `dashboard/live_app.py`
- `dashboard/live_dashboard_service.py`
- `dashboard/status_server.py`
- `scripts/run_st_a2_demo.py`
- `scripts/run_d2_e3_demo.py`
- `scripts/run_strategy_demo.py`
- `scripts/reconcile_positions.py`
- `bot.py`

These components are responsible for:

- broker connectivity
- market polling
- signal routing
- portfolio/risk checks
- order placement
- trade journaling
- runtime monitoring
- operator status visibility

## SVOS Components

The following components are clearly SVOS or research/governance oriented:

- `svos/`
- `strategy_validation/`
- `strategy_audit/`
- `research/validation/`
- `research/robustness.py`
- `research/research_queue.py`
- `research/svos/`
- `execution_validation/`
- `execution_simulator/`
- `virtual_broker/`
- `scripts/run_current_strategy_svos.py`
- `scripts/run_svos_pipeline.py`
- `scripts/run_execution_validation.py`
- `scripts/run_replay_execution_validation.py`

These components are responsible for:

- intake and audit
- replay and backtest
- robustness validation
- evidence generation
- governance and lifecycle transitions
- simulation and execution qualification
- report generation

## Shared Components

The following components are effectively shared today, even though they are not yet isolated into a clean shared package:

- `core/base_strategy.py`
- `core/signal.py`
- `core/broker_interface.py`
- `core/strategy_registry.py`
- `core/portfolio_manager.py`
- `db/models.py`
- `schemas/`
- `config/`
- selected `strategies/adapters/`
- selected `research/lineage.py`
- selected data validation and serialization helpers

These are shared because both runtime and SVOS paths depend on them.

## Duplicated Logic

Major duplication areas:

1. Strategy execution and research representations
   - `strategy/`
   - `session_smc/`
   - `adaptive/strategies/`
   - `src/signals/`
   - `strategies/adapters/`

2. Pipeline orchestration
   - `svos/application/pipeline.py`
   - `research/svos/engine.py`
   - multiple wrapper scripts

3. Dashboard backend surfaces
   - `dashboard/app.py` Flask control panel
   - `dashboard/live_app.py` Flask live dashboard
   - `dashboard/status_server.py` FastAPI status server

4. Persistence and state handling
   - JSON and JSONL state in `logs/` and `data/svos/`
   - SQLite journal usage
   - PostgreSQL control-plane models and repositories in `db/`

5. Research/replay engines
   - `pipeline/`
   - `src/`
   - `research/`
   - `execution_simulator/replay_engine/`

## Circular Dependencies

No repository-wide hard import cycle was required to use the system, but the current architecture shows strong cycle risk through cross-layer imports and orchestration coupling.

Observed cycle-prone patterns:

- dashboards importing scripts directly
- scripts importing both runtime and SVOS internals
- shared registry/config functions used as lifecycle mutation compatibility shims
- services relying on global filesystem layout rather than explicit ports

Examples:

- `dashboard/app.py` imports `scripts.health_check`, dashboard services, and `svos.api.service`
- `dashboard/live_dashboard_service.py` imports execution runtime components directly
- `agtrade/strategy.py` currently bridges both research and SVOS orchestration paths

The dominant problem is not a classic Python import loop. The dominant problem is hidden orchestration coupling.

## Hidden Coupling

Key hidden-coupling mechanisms:

- `config/strategy_catalog.yaml` as a global projection and compatibility control point
- filesystem state in `logs/`, `reports/`, and `data/svos/`
- scripts mutating or relying on shared path conventions
- dashboard endpoints reading local artifacts instead of remote service contracts
- deployment scripts assuming mixed SVOS + runtime co-location
- direct `sys.path` mutation in older scripts

This means system boundaries are often enforced by convention, not code.

## Migration Risks

### High risk

- Breaking current SVOS pipeline compatibility while extracting production runtime
- Moving strategy contracts without preserving existing adapter expectations
- Separating dashboards without replacing local-file assumptions
- Detaching persistence without a migration path for JSON/JSONL and SQLite state

### Medium risk

- Divergent strategy representations across `strategy/`, `session_smc/`, and `strategies/`
- Multiple demo/live runners with overlapping runtime responsibilities
- Cross-cutting use of `core.strategy_registry`

### Low risk

- Extracting pure models, schemas, serialization, and risk math helpers into a shared layer
- Introducing application services under the `agtrade` CLI while preserving wrappers

## Current Boundary Verdict

Current repo state by boundary:

- Production boundary: incomplete
- SVOS boundary: partially present
- Shared boundary: conceptual only
- Dashboard boundary: mixed and not clean
- Artifact boundary: incomplete
- Deployment boundary: mixed research and execution assumptions

The next migration should therefore begin with structural ownership documentation and compatibility-preserving extraction, not a rewrite.
