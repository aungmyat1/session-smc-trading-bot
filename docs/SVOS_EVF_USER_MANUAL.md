# SVOS and EVF User Manual

Date: 2026-06-27

This manual covers the two validation layers in this repo:

- SVOS, the Strategy Validation Operating System
- EVF, the Execution Validation Framework

It describes what each system validates, how to run it, what its practical
capacity is, and the minimum time needed to validate.

## 1. SVOS

SVOS is the strategy-level gate. It checks whether a strategy is defined clearly
enough to move through replay, backtest, robustness, demo, and production
approval.

### What SVOS validates

SVOS requires a strategy spec with these fields:

- `market`
- `session`
- `bias`
- `entry_trigger`
- `confirmation`
- `invalidation`
- `stop_loss`
- `take_profit`
- `risk`
- `filters`
- `exit_rules`

SVOS then runs these stages:

1. Strategy audit
1. Enhancement
1. Replay validation
1. Backtest validation
1. Robustness validation
1. Demo validation
1. Production approval

### How to run SVOS

For the current catalog strategy:

```bash
python3 scripts/run_current_strategy_svos.py --strategy ST-A2
```

Runnable sample files:

- `docs/examples/svos_sample_strategy.txt`
- `docs/examples/svos_sample_replay.json`
- `docs/examples/svos_sample_backtest.json`
- `docs/examples/svos_sample_robustness.json`
- `docs/examples/svos_sample_demo.json`

For a fully specified manual run:

```bash
python3 scripts/run_current_strategy_svos.py \
  --strategy ST-A2 \
  --strategy-text "$(cat docs/examples/svos_sample_strategy.txt)" \
  --replay-json docs/examples/svos_sample_replay.json \
  --backtest-json docs/examples/svos_sample_backtest.json \
  --robustness-json docs/examples/svos_sample_robustness.json \
  --demo-json docs/examples/svos_sample_demo.json
```

### SVOS capacity

SVOS is designed to validate one strategy at a time. In practice, it can:

- audit a raw strategy description
- normalize incomplete input into a structured spec
- detect missing fields
- detect ambiguous or contradictory wording
- gate progress based on replay, backtest, robustness, and demo evidence
- write a stage-by-stage report for later review

SVOS is good for strategy definition and lifecycle control, not execution
microstructure testing.

### Minimum time to validate SVOS

There are two useful timings:

- Audit-only validation: seconds, because it only needs the strategy text.
- Full SVOS-to-live validation: at least 14 demo days, because the demo stage
  requires `min_demo_days=14` by default.

If replay, backtest, and robustness evidence already exist, the software run is
fast. The long part is the live/demo observation window.

### SVOS outputs

SVOS writes reports to:

- `reports/current_strategy_svos/<strategy>/svos_result.json`
- `reports/current_strategy_svos/<strategy>/svos_result.md`

### SVOS pass condition

SVOS returns `PASS` only when all required stages succeed and the strategy is
approved in the registry for the target lifecycle stage.

### Common SVOS failures

- Missing strategy fields
- Ambiguous wording such as `maybe`, `optional`, `depends`, or `or/and`
- Contradictory direction language
- Missing replay or backtest evidence
- Robustness checks not completed
- Demo monitoring shorter than 14 days
- Demo metrics drifting too far from research metrics

## 2. EVF

EVF is the execution-layer gate. It checks whether a strategy can execute
correctly, safely, and consistently in the broker/execution stack.

### What EVF validates

EVF checks:

- signal integrity
- order execution
- risk engine behavior
- duplicate order protection
- spread handling
- slippage handling
- exit management
- recovery behavior
- broker simulation behavior
- strategy version control

### How to run EVF

Use the default runner:

```bash
python3 scripts/run_evf.py \
  --payload docs/examples/evf_sample_payload.json \
  --strategy ST-A2 \
  --period 2023-2026 \
  --rules execution_validation/config/validation_rules.yaml
```

The legacy entrypoint still works:

```bash
python3 scripts/run_execution_validation.py \
  --payload path/to/execution_payload.json \
  --strategy ST-A2 \
  --period 2023-2026 \
  --rules execution_validation/config/validation_rules.yaml
```

You can also use the replay bridge:

```bash
python3 scripts/run_replay_execution_validation.py \
  --payload path/to/candle_payload.json \
  --strategy ST-A2 \
  --period 2023-2026 \
  --symbol EURUSD \
  --report-dir execution_validation/reports
```

### EVF capacity

EVF is designed to validate execution behavior for one strategy/version payload
at a time. In practice, it can:

- validate one or many execution samples in a single JSON payload
- compare expected versus observed signal/order behavior
- evaluate risk and broker-rule samples
- confirm recovery and restart behavior
- produce a single readiness report for demo approval

EVF is good for execution correctness and safety, not for strategy discovery or
profitability research.

### Minimum time to validate EVF

EVF can run as soon as you have a payload. The minimum validation time is usually
seconds to a few minutes, depending on how quickly you can assemble the payload.

There is no mandatory multi-day observation window inside EVF itself.

### EVF outputs

EVF writes its report to:

- `execution_validation/reports/validation_report.json`

### EVF pass condition

EVF returns `READY FOR DEMO` when the execution checks pass.

Runnable sample file:

- `docs/examples/evf_sample_payload.json`

### Common EVF failures

- Missing or malformed signal/order/fill data
- Mismatched strategy metadata
- Duplicate IDs
- Risk samples that fail broker rules
- Recovery snapshot mismatch
- Excessive spread or slippage
- Execution payloads that do not exercise the tested paths

## 3. Verified Recheck

Revalidated on 2026-06-27 in this workspace:

- SVOS test suite: `5 passed`
- SVOS entrypoint: `PASS` on `ST-A2`
- EVF example payload: `READY FOR DEMO`, `final_score=100`

Observed EVF metrics on the example payload:

- `signal_accuracy=1.0`
- `order_accuracy=1.0`
- `risk_accuracy=1.0`
- `slippage_average_pip=0.3`
- `execution_delay_ms_average=150.0`

## 4. Quick Decision Guide

Use SVOS when you need to answer:

- Is the strategy spec complete?
- Is the rulebook unambiguous?
- Did replay, backtest, robustness, and demo checks all pass?
- Is the strategy ready for lifecycle promotion?

Use EVF when you need to answer:

- Can the strategy execute correctly in the broker stack?
- Are order, risk, spread, slippage, recovery, and version-control behaviors safe?
- Is the execution layer ready for demo operation?

## 5. Recommended Order

1. Run SVOS first to validate the strategy definition and research evidence.
1. Run EVF after SVOS to validate execution behavior.
1. Review the report output before promoting the strategy further.
