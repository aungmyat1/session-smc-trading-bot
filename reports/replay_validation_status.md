# Replay Validation Status Report

**Generated:** 2026-06-30
**Phase:** 5 — Historical Replay Integration Assessment
**Status:** PARTIAL — Runner implemented, dataset integration required

---

## Current State

### Replay Engine (execution_simulator/replay_engine/)

The execution simulator replay engine is **fully implemented** with the following components:

| Component | File | Status |
|-----------|------|--------|
| MarketFeed | `execution_simulator/replay_engine/market_feed.py` | READY |
| EventStream | `execution_simulator/replay_engine/event_stream.py` | READY |
| ReplayClock | `execution_simulator/replay_engine/clock.py` | READY |
| ReplayRunner | `execution_simulator/replay_engine/runner.py` | READY |
| VirtualBroker | `execution_simulator/broker/virtual_broker.py` | READY |

### SVOS Virtual Demo Integration (svos/application/virtual_demo.py)

The SVOS Virtual Demo service (`VirtualDemoIntegrationService`) **connects the replay engine** to the strategy qualification pipeline:

- Synthesizes market ticks from strategy signal dicts (entry, SL, TP)
- Executes signals through `VirtualBroker` via `asyncio.run()`
- Computes drift between expected (backtest) and virtual (simulated) P&L
- Registers PASS/FAIL evidence in the SVOS registry
- Drives lifecycle transitions: `ROBUSTNESS_VALIDATION → VIRTUAL_DEMO`

### Replay Validation Runner (replay_validation/runner.py)

A standalone validation runner has been created at `replay_validation/runner.py` that:

1. Loads a parquet or CSV historical dataset
2. Constructs a `MarketFeed` from historical rows
3. Computes net-of-fees performance metrics (standard and 2x stress spread)
4. Evaluates gates: minimum_trades, profit_factor, sharpe, max_drawdown
5. Returns a JSON summary with PASS/FAIL decision

**Configuration:** `replay_validation/config.yaml`

---

## Validation Flow

```
Historical Dataset (.parquet)
    ↓ load_dataset()
List[dict] rows (OHLCV)
    ↓ MarketFeed.from_records()
MarketFeed (tick-by-tick)
    ↓ ReplayRunner.run() [with strategy on_tick hook]
Completed Trades (journal)
    ↓ _compute_metrics()
Performance Metrics (PF, Sharpe, DD)
    ↓ evaluate_gates()
Gate Results → PASS / FAIL
    ↓ JSON summary
reports/replay_validation_result.json
```

---

## Gate Thresholds (from replay_validation/config.yaml)

| Gate | Threshold | Notes |
|------|-----------|-------|
| minimum_trades | ≥ 200 | Statistical significance floor |
| minimum_profit_factor | ≥ 1.25 | Net-of-fees, standard spread |
| minimum_sharpe | ≥ 1.2 | Annualised Sharpe ratio |
| max_drawdown_pct | ≤ 15% | Peak-to-trough drawdown |
| stress_profit_factor | ≥ 1.0 | Net PF at 2x spread stress |

---

## What Is Missing to Fully Connect

### 1. Strategy On-Tick Hook

The `ReplayRunner` accepts an `on_tick` callback. Currently the runner processes raw candles without a strategy-specific signal generator. To fully connect:

```python
# In replay_validation/runner.py or a strategy-specific adapter:
def on_tick(tick: MarketEvent, broker: VirtualBroker) -> None:
    signal = strategy.evaluate(tick)   # strategy-specific hook
    if signal:
        await broker.place_order(...)
```

**Required:** A strategy signal generator that consumes `MarketEvent` and returns trade decisions.

### 2. Trade Journal Output

The `VirtualBroker` currently tracks open positions but does not expose a completed trade journal in the format expected by `_compute_metrics()`. The adapter should:
- Listen to `on_fill` / `on_close` events from `VirtualBroker`
- Record each completed trade with `gross_pnl`, `entry_time`, `exit_time`, `symbol`

### 3. Dataset Availability

Historical datasets must be present at a known path before `runner.py` can execute:

```
data/eurusd_m15_2022_2024.parquet   # EURUSD M15 (3 years)
data/gbpusd_m15_2022_2024.parquet   # GBPUSD M15 (3 years)
```

Datasets are fetched via `scripts/fetch_data.py` (Dukascopy public feed).

---

## Running the Validation (once dataset available)

```bash
# Standard run
python replay_validation/runner.py \
    --dataset data/eurusd_m15_2022_2024.parquet \
    --strategy ST-A2 \
    --config replay_validation/config.yaml \
    --output reports/replay_validation_result.json

# Verbose
python replay_validation/runner.py \
    --dataset data/eurusd_m15_2022_2024.parquet \
    --strategy ST-A2 \
    --verbose
```

---

## Overall Readiness

| Component | Status |
|-----------|--------|
| Replay engine (execution_simulator) | READY |
| VirtualBroker | READY |
| SVOS Virtual Demo integration | READY |
| Replay validation runner | READY |
| Strategy on-tick hook | PENDING — requires strategy implementation |
| Trade journal adapter | PENDING — requires VirtualBroker output wiring |
| Historical datasets | PENDING — run `scripts/fetch_data.py` |
| End-to-end integration test | PENDING |

**Conclusion:** The infrastructure is in place. Full end-to-end execution requires a concrete strategy implementation and available historical data.
