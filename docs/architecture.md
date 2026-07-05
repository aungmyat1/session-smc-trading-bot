# System Architecture

**Platform:** Strategy Engineering Platform (SEP) for systematic Forex trading
**Version:** v2.0 | Last updated: 2026-06-30

---

## Overview

The platform follows a seven-phase qualification pipeline. Every strategy must pass all phases in sequence before deployment. No live trading occurs until a Production Approval Package is issued.

```
Strategy Input
  → Phase 0: Strategy Audit
  → Phase 1: Enhancement
  → Phase 2: Historical Replay
  → Phase 3: Backtesting & Statistical Validation
  → Phase 4: Robustness Tests
  → Phase 5: Offline Virtual Demo
  → Phase 6: Production Approval [out of scope]
  → Vantage Forex Bot (execution only)
```

---

## Component Architecture

### Research Layer (`svos/application/`)

| Module | Role |
|--------|------|
| `intake.py` | Format validation, data availability check |
| `audit.py` | Logic review, completeness, lookahead detection |
| `replay.py` | Chronological candle replay without future access |
| `backtest.py` | Statistical validation with net-of-fees metrics |
| `robustness.py` | Walk-forward, Monte Carlo, parameter stability |
| `virtual_demo.py` | Offline execution simulation — no broker connection |

### SVOS Governance Layer (`svos/`)

| Module | Role |
|--------|------|
| `lifecycle/manager.py` | Stage transition authority — the only valid mutation path |
| `registry/service.py` | Append-only strategy history (JSONL-backed) |
| `governance/service.py` | Evidence-driven gate decisions |
| `orchestration/service.py` | Unified API: JSONL path + PostgreSQL path |
| `reports/stage_package.py` | Standardised SVOS report packages |

### Execution Layer (`execution_simulator/`)

| Module | Role |
|--------|------|
| `broker/virtual_broker.py` | Simulated broker: fills, SL/TP, position management |
| `replay_engine/runner.py` | Drives MarketFeed → VirtualBroker tick by tick |
| `replay_engine/market_feed.py` | Tick stream from historical OHLCV data |

### Agent Layer (`agents/`)

| Module | Role |
|--------|------|
| `testing/` | Unit + integration test runner; produces `testing_report.json` |
| `quality/` | Ruff, mypy, bandit, architecture checks; produces `quality_report.json` |
| `approval/` | Consumes testing + quality reports; outputs APPROVED/REJECTED |

---

## Data Flow

```
Dukascopy (public) → scripts/fetch_data.py → data/*.parquet
                                                   ↓
                                          execution_simulator/
                                          replay_engine/MarketFeed
                                                   ↓
                              svos/application/virtual_demo.py
                                                   ↓
                              svos/registry/service.py (evidence)
                                                   ↓
                              svos/governance/service.py (gate)
                                                   ↓
                              svos/reports/stage_package.py (report)
```

---

## Storage

| Store | Path | Format |
|-------|------|--------|
| Strategy catalog | `config/strategy_catalog.yaml` | YAML |
| Registry state | `data/svos/registry/{strategy}/` | JSONL |
| Governance decisions | `data/svos/governance/{strategy}/` | JSONL |
| Report artifacts | `data/svos/artifacts/` | Content-addressed |
| Historical data | `data/*.parquet` | Parquet |

---

## Security Boundaries

- Broker credentials (`VANTAGE_DEMO_METAAPI_ID`, `VANTAGE_LIVE_METAAPI_ID`) are loaded from `.env` only.
- Research, reporting, and dashboard processes have no access to broker credentials.
- Live trading requires `LIVE_TRADING=true` AND `DEMO_ONLY=false` — both must be set manually by the owner.
- Magic numbers isolate order attribution: EURUSD → 21001, GBPUSD → 21002.
