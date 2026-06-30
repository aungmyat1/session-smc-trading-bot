# Replay Validation

**Document:** Phase 2 & 5 — Historical Replay and Virtual Demo
**Last updated:** 2026-06-30

---

## Overview

Replay validation is the process of running strategy rules chronologically through historical data without any access to future prices, then comparing simulated execution outcomes against backtest expectations.

There are two distinct replay phases:

| Phase | Name | Mode | Gate |
|-------|------|------|------|
| Phase 2 | Historical Replay | Research — candle-by-candle | Signals match spec; no lookahead |
| Phase 5 | Offline Virtual Demo | Execution — VirtualBroker + MarketFeed | PnL drift < 10% vs backtest |

---

## Phase 2: Historical Replay

### Purpose

Verify that the implemented strategy rules produce the correct signals when applied candle-by-candle. Every signal must be inspectable: entry trigger, state transitions, feature availability at signal time.

### Anti-Lookahead Requirements

The replay engine enforces chronological access:
- At candle T, only data from timestamps ≤ T is available
- Session highs/lows are computed up to (but not including) the current candle
- HTF H4 candle data is only available after H4 candle close

### Signal Journal

Each signal generated during replay is recorded with:
- `timestamp`: candle open time when signal triggered
- `entry_price`: price at signal time (no future information)
- `stop_loss`: computed SL at signal time
- `take_profit`: computed TP at signal time
- `side`: long or short
- `state_transitions`: all state machine changes leading to this signal
- `features`: all indicator values at signal time

### PASS Gate

Replay PASS requires:
- Zero lookahead violations detected
- Signal count ≥ 10 (for inspectability; backtest does the statistics)
- Replay accuracy ≥ 95% (valid signals / total signals attempted)

---

## Phase 5: Offline Virtual Demo

### Purpose

Validate that the execution layer (order placement, SL/TP fills, position sizing) behaves consistently with backtest expectations. Detects implementation drift before any live or demo deployment.

### Architecture

```
strategy.signals (from Phase 3 backtest)
    ↓ VirtualDemoIntegrationService.run()
    ↓ _build_ticks() — synthesizes entry + exit tick per signal
    ↓ asyncio.run(_async_simulate())
    ↓ VirtualBroker — fills orders, tracks positions
    ↓ _compute_drift() — compares virtual PnL vs expected PnL
    ↓ evidence registered in SVOS registry
```

### Drift Checks

| Check | Threshold | Gate |
|-------|-----------|------|
| PF drift | ≤ 10% deviation from expected PF | FAIL if exceeded |
| Fill rate | ≥ 80% of signals result in fills | FAIL if below |
| Signal count | ≥ 5 signals (minimum statistical floor) | FAIL if below |

### How to Run Virtual Demo

```python
from svos.application.virtual_demo import VirtualDemoIntegrationService
from svos.orchestration.service import SVOSPlatform

platform = SVOSPlatform(root=Path("."))
svc = VirtualDemoIntegrationService(platform)

result = svc.run(
    strategy="ST-A2",
    signals=backtest_signals,           # list of signal dicts
    expected_pf=1.45,                   # PF from Phase 3 backtest
    symbol="EURUSD",
    point_size=0.0001,
    lot_size=0.01,
    initial_balance=10_000.0,
    actor="svos-virtual-demo",
)
print(result.status)  # PASS or FAIL
```

---

## Standalone Replay Validation Runner

For pipeline integration and CI, `replay_validation/runner.py` provides a standalone validator:

```bash
python replay_validation/runner.py \
    --dataset data/eurusd_m15_2022_2024.parquet \
    --strategy ST-A2 \
    --config replay_validation/config.yaml \
    --output reports/replay_validation_result.json
```

### Output Format

```json
{
  "strategy": "ST-A2",
  "status": "PASS",
  "standard_metrics": {
    "trade_count": 215,
    "profit_factor": 1.38,
    "sharpe": 1.45,
    "max_drawdown_pct": 8.2
  },
  "stress_metrics": {
    "profit_factor": 1.12,
    "max_drawdown_pct": 11.5
  },
  "gate_results": [
    {"gate": "minimum_trades", "actual": 215, "threshold": 200, "passed": true},
    {"gate": "minimum_profit_factor", "actual": 1.38, "threshold": 1.25, "passed": true},
    {"gate": "minimum_sharpe", "actual": 1.45, "threshold": 1.2, "passed": true},
    {"gate": "max_drawdown", "actual": 8.2, "threshold": 15.0, "passed": true},
    {"gate": "stress_profit_factor", "actual": 1.12, "threshold": 1.0, "passed": true}
  ]
}
```

---

## Evidence Chain

Phase 2 and Phase 5 evidence is registered in the SVOS registry and linked to the strategy version. A stage transition from `HISTORICAL_REPLAY` to `STATISTICAL_VALIDATION` requires a PASS evidence record for the correct version. The governance service blocks promotion without it.
