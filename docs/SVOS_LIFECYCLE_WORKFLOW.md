# SVOS Lifecycle Workflow

This document sets up the standard SVOS promotion loop for a new strategy.
It matches the current implementation in `research/svos/engine.py` and the
report artifacts written under `reports/current_strategy_svos/<strategy>/`.

For the authoritative architecture and lifecycle definitions, see
`docs/SYSTEM_ARCHITECTURE.md`.

This file describes the current transitional SVOS workflow, not the full target
ISOP architecture.

## Workflow

```text
New Strategy
    │
    ▼
Strategy Intake
    │
    ▼
Strategy Audit
    │
    ├── FAIL → AI edits specification → Audit again
    ▼
Historical Replay
    │
    ├── FAIL → Refine rules → Replay again
    ▼
Backtest
    │
    ├── FAIL → Improve logic or filters → Backtest again
    ▼
Robustness Tests
    │
    ├── FAIL → Adjust parameters or simplify rules → Retest
    ▼
Verification Ready
    │
    ├── FAIL → Resolve research gaps → Retest
    ▼
Virtual Demo Trading
      │
      ├── FAIL → Analyze live drift → Return to research
      ▼
Production Approval
```

## Operational Meaning

1. Start with a strategy intake record and canonical strategy text.
1. Run the SVOS audit after intake.
1. If audit fails, revise the strategy text and rerun audit.
1. If audit passes, continue through replay, backtest, robustness, and the verification-ready handoff.
1. Use the verification-ready report as the research signoff before demo evidence starts.
1. If any later stage fails, fix the underlying issue and rerun from the failed
   stage or earlier, depending on the change.
1. Only request production approval after the virtual demo gate passes.

## Report Artifacts

Each executed SVOS step writes a stage report:

- `reports/current_strategy_svos/<strategy>/stages/00_intake.json`
- `reports/current_strategy_svos/<strategy>/stages/01_audit.json`
- `reports/current_strategy_svos/<strategy>/stages/02_enhancement.json`
- `reports/current_strategy_svos/<strategy>/stages/03_replay.json`
- `reports/current_strategy_svos/<strategy>/stages/04_backtest.json`
- `reports/current_strategy_svos/<strategy>/stages/05_robustness.json`
- `reports/current_strategy_svos/<strategy>/stages/06_verification_ready.json`
- `reports/current_strategy_svos/<strategy>/stages/07_virtual_demo.json`
- `reports/current_strategy_svos/<strategy>/stages/08_production_approval.json`

The final rollup remains in:

- `reports/current_strategy_svos/<strategy>/svos_result.json`
- `reports/current_strategy_svos/<strategy>/svos_result.md`

## Notes

- SVOS does not auto-edit strategy text. The "AI edits specification" step is a
  human or agent action outside the pipeline.
- The pipeline is deterministic for a fixed set of inputs.
- The stage report files are meant to support audit review, change tracking, and
  step-by-step promotion decisions.
- The audit stage can flag missing data dependencies and likely overfitting.
- `--stop-after verification_ready` is the intended research-only handoff mode.
- The virtual demo stage expects execution-validation evidence from the virtual
  broker process rather than a purely synthetic placeholder payload.
