# Quant Platform Architecture
# Session Trading Bot
# Date: 2026-06-26

---

## Purpose

This project should be treated as a quantitative research platform that can also
execute approved strategies. The key design choice is to separate research from
execution so strategy development, replay, validation, and backtesting do not
share the same operational path as live or demo order management.

That separation matches the current codebase direction:

- research code produces signals, metrics, and verdicts
- execution code places and manages orders
- strategy promotion happens only after replay, validation, and holdout gates pass

---

## Target Flow

```text
Market Data Collector
        │
        ▼
Data Lake / Processed Bars
        │
        ▼
Feature Engine
        │
        ▼
Strategy SDK
        │
        ├──────────────┐
        ▼              ▼
Replay Engine      Backtest Engine
        │              │
        └──────┬───────┘
               ▼
Validation Engine
               │
               ▼
Strategy Registry
               │
               ▼
Execution Platform
               │
               ▼
Shadow / Demo / Live
```

This is not a "single bot that does everything". It is a research factory with
a narrow execution surface.

---

## Layer Responsibilities

### Research Layer

The research layer owns:

- market data ingestion
- processed bars and feature generation
- historical replay
- backtesting
- validation
- strategy scoring and verdict logging
- research database ingestion

Relevant current modules:

- `simulator/historical_replay.py`
- `scripts/historical_replay.py`
- `scripts/bootstrap_quant_db.py`
- `scripts/d2e3_journal_to_db.py`
- `scripts/replay_parquet.py`
- `scripts/replay_db.py`
- `research/`
- `db/`

### Execution Layer

The execution layer owns:

- broker connectivity
- reconnect logic
- order placement and cancellation
- position tracking
- risk checks
- trade journal writes
- demo / shadow / live routing

Relevant current modules:

- `execution/`
- `bot.py`
- `scripts/run_d2_e3_demo.py`
- `scripts/run_st_a2_demo.py`
- `scripts/run_portfolio.py`

---

## Current Strategy Split

### ST-A2

ST-A2 is the primary production candidate. It remains the validated execution
path while spread capture, cost revalidation, and live-readiness checks continue.

### D2 E3

D2 E3 is a separate research branch. It belongs on a research node with a local
database and a persistent journaling path. It should stay demo-safe by default
and must not be promoted unless it clears the same holdout and execution gates
used for any production candidate.

### Strategy Registry

The registry is the control center for lifecycle state and deployment metadata.
The canonical source of truth lives in [`config/strategy_catalog.yaml`](/home/aungp/session-smc-trading-bot/config/strategy_catalog.yaml).

Lifecycle states are modeled as:

`draft -> research -> replay -> backtest -> walk_forward -> shadow -> demo -> live -> retired`

The catalog tracks:

- version
- owner
- supported symbols
- supported timeframes
- deployment target
- approval flag
- validation requirements

The execution layer should refuse to promote or trade any strategy that is not
explicitly approved for the target environment.

### Validation Gate Engine

The validation gate engine sits between replay/backtest and lifecycle promotion.
It evaluates:

- replay completion and replay correctness
- backtest quality thresholds
- regression drift against the previous successful run
- promotion eligibility

If the gate fails, the strategy is held in place and no lifecycle promotion is
written back to the registry.

### Isolation Rules

- one strategy identity per branch
- one magic number set per strategy
- no shared position tracking across strategies
- no overlap between production and research execution paths
- no live-trading enablement from the research service

---

## Platform Mapping

### Production VPS

Used for ST-A2 execution and operational stability.

### `gcp-vm1`

Used for D2 E3 research, PostgreSQL-backed analysis, replay ingestion, and
long-running demo-safe experimentation.

### Data and Storage

- Parquet is the default storage for historical bars and derived research data
- PostgreSQL stores strategy metadata, replay runs, trades, features, and metrics
- JSONL journals remain useful as an append-only event source for ingestion

---

## Processing Rules

1. Historical replay validates execution logic and state transitions.
2. Backtesting measures strategy profitability.
3. Validation blocks promotion if the strategy violates no-lookahead, duplicate
   trade, session, or risk rules.
4. Approved strategies move into shadow trading before demo trading.
5. Demo trading must remain idempotent and recoverable.
6. Live trading is only allowed after the relevant gates pass.

---

## Existing Implementation Footprint

This architecture is already partially implemented in the repo:

- strategy registry abstraction in `core/strategy_registry.py`
- strategy interface in `core/base_strategy.py`
- execution-specific order and trade handling in `execution/`
- historical replay tooling in `simulator/` and `scripts/historical_replay.py`
- research database schema in `db/schema_v2.sql`
- D2 E3 research runner and ingest path in `scripts/run_d2_e3_demo.py` and
  `scripts/d2e3_journal_to_db.py`
- research node deployment assets in `deploy/gcp-vm1/`

The main remaining work is to keep extending the research layer without folding
it back into execution logic.

---

## Recommended Operating Model

- Develop new ideas in research first.
- Promote only the strategies that pass replay, validation, backtest, and holdout.
- Keep execution code boring and stable.
- Keep research code versioned, queryable, and reproducible.
