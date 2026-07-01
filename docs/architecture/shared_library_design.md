# Shared Library Design

Date: 2026-07-01
Status: proposed target for incremental extraction

## Purpose

`shared/` should contain reusable business contracts and pure logic used by both Production and SVOS.

It must not contain:

- broker execution
- live order routing
- position management
- replay engines
- optimizers
- research experiments

## Proposed Layout

```text
shared/
  models/
  strategy_api/
  market_data/
  indicators/
  risk_models/
  schemas/
  serialization/
  configuration/
```

## Candidate Source Material

### `shared/models/`

Source candidates:

- `models/`
- pure dataclasses from `svos/shared/models.py`
- strategy-neutral execution-independent data structures

### `shared/strategy_api/`

Source candidates:

- `core/base_strategy.py`
- `core/signal.py`
- stable strategy input/output contracts

### `shared/market_data/`

Source candidates:

- common candle/tick/session contracts from research and runtime flows
- selected utilities from `src/data/` and `research_db/`

### `shared/indicators/`

Source candidates:

- pure indicator logic from `src/features/`
- selected pure helpers from strategy research code

### `shared/risk_models/`

Source candidates:

- position sizing math
- pure stop/take-profit/risk-budget helpers
- execution-independent portfolio/risk calculations

### `shared/schemas/`

Source candidates:

- `schemas/`
- JSON schema definitions for strategy specs, tasks, artifacts, and API payloads

### `shared/serialization/`

Source candidates:

- JSON/YAML manifest handling
- checksum utilities
- report and artifact serialization helpers

### `shared/configuration/`

Source candidates:

- typed config parsing for strategy, runtime, validation, and deployment settings

## Dependency Rule

`shared/` may depend only on:

- Python stdlib
- typed utility libraries already approved for all runtimes

`shared/` must not depend on:

- `execution/`
- `svos/`
- `dashboard/`
- broker SDKs
- Flask or FastAPI

## Immediate Design Recommendation

Do not move large files blindly.

Instead:

1. create destination contracts
2. copy or extract pure types and helpers
3. add compatibility imports
4. migrate callers incrementally
