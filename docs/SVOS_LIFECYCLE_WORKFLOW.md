# SVOS Lifecycle Workflow

Status: Authoritative
Version: 1.0
Updated: 2026-06-29
Owner: Platform Architecture
Authority: Level 6 — Lifecycle Reference
Note: Stage names in this document must be aligned with canonical lifecycle enums.
See DOC_AUTHORITY.md §Canonical Lifecycle Vocabulary.
Related: CORE_ARCHITECTURE.md, SYSTEM_ARCHITECTURE.md

Governing lifecycle: `docs/00_Project/TWO_SYSTEM_ARCHITECTURE_TRUTH.md`.
The workflow below must preserve separate Backtest and Statistical Validation
stages and must end at Production Approval.

This document sets up the standard SVOS promotion loop for a strategy entering
the current intake pipeline.
It matches the current implementation in `research/svos/engine.py` and the
report artifacts written under `reports/current_strategy_svos/<strategy>/`.

For the authoritative architecture and lifecycle definitions, see
`docs/SYSTEM_ARCHITECTURE.md`.

This file describes the current transitional SVOS workflow, not the full target
ISOP architecture.

## Workflow

```text
Strategy Idea
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
Statistical Validation
    │
    ├── FAIL → Reject evidence or refine strategy → Backtest again
    ▼
Robustness Testing
    │
    ├── FAIL → Adjust parameters or simplify rules → Retest
    ▼
Virtual Demo Trading
      │
      ├── FAIL → Analyze live drift → Return to research
      ▼
Production Approval
```

## Operational Meaning

1. Start with a strategy idea and canonical strategy text.
1. Run the SVOS audit after intake.
1. If audit fails, revise the strategy text and rerun audit.
1. If audit passes, continue through historical replay and Backtest.
1. Evaluate Backtest output in the separate Statistical Validation gate.
1. Continue through Robustness Testing and Virtual Demo Trading only after
   Statistical Validation passes.
1. If any later stage fails, fix the underlying issue and rerun from the failed
   stage or earlier, depending on the change.
1. Only request production approval after the virtual demo gate passes.

## Report Artifacts

Each executed SVOS step writes a stage report:

- `reports/current_strategy_svos/<strategy>/stages/00_intake.json` (transitional Strategy Idea/intake representation)
- `reports/current_strategy_svos/<strategy>/stages/01_audit.json`
- `reports/current_strategy_svos/<strategy>/stages/02_enhancement.json` (transitional audit-remediation artifact, not a product lifecycle stage)
- `reports/current_strategy_svos/<strategy>/stages/03_replay.json`
- `reports/current_strategy_svos/<strategy>/stages/04_backtest.json`
- `reports/current_strategy_svos/<strategy>/stages/05_robustness.json` (current combined numbering; separate Statistical Validation artifact migration pending)
- `reports/current_strategy_svos/<strategy>/stages/06_verification_ready.json` (transitional handoff artifact, not a product lifecycle stage)
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
- Enhancement is audit remediation, not an additional product lifecycle stage.
- `verification_ready` is a transitional implementation handoff, not an
  additional product lifecycle stage.
- The virtual demo stage expects execution-validation evidence from the virtual
  broker process rather than a purely synthetic placeholder payload.
