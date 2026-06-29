# Project Objective

Date: 2026-06-28

## Objective

The project objective is to build and operate an `SVOS` research and
verification system plus a simple trading bot.

The system should work like this:

- input: a new trade idea or strategy
- process: run it through the `SVOS` engine
- output: a production-approved strategy only if it passes all stages

In this repository, `SVOS` means this practical stage-gate loop:

```text
New Strategy
      │
      ▼
Strategy Audit
      │
      ├── FAIL -> AI edits specification -> Audit again
      ▼
Historical Replay
      │
      ├── FAIL -> Refine rules -> Replay again
      ▼
Backtest
      │
      ├── FAIL -> Improve logic or filters -> Backtest again
      ▼
Robustness Tests
      │
      ├── FAIL -> Adjust parameters or simplify rules -> Retest
      ▼
Demo Trading
      │
      ├── FAIL -> Analyze live drift -> Return to research
      ▼
Production Approval
```

Each stage should answer one question before the next stage begins.

## Scope Rule

The goal is not to expand the repository into a broader institutional platform.

The goal is to keep the workflow practical, repeatable, and directly useful for
running a validated strategy through demo and live execution.

## Current State

The repo currently has:

- an SVOS-style workflow in code
- a simple execution path aimed at Vantage demo/live trading
- a strategy-validation objective rather than a single-strategy identity

## Current Fastest Path

The current live path for the active execution candidate is:

1. finish `E5` spread capture
2. run `E6` cost revalidation
3. complete `E1-E4` demo execution gate
4. continue demo only if evidence remains acceptable
5. allow controlled live promotion only after approval

## Primary Deliverable

The primary deliverable is:

`SVOS research and verification engine + simple Vantage demo/live trading bot`

## References

- `docs/CURRENT_SCOPE.md`
- `docs/IMPLEMENTATION_STATUS.md`
- `docs/PROJECT_LIVE_STATUS_TIMELINE.md`
- `config/strategy_catalog.yaml`
