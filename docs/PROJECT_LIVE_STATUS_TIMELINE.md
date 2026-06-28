# Project Live Status Timeline

Date: 2026-06-28

This document is the operator-facing timeline for understanding:

- where the project stands now
- what is already complete
- what is currently running
- what task executes next
- what target each timeline step is trying to reach

Use this as the single high-level status view.

If this document disagrees with the strategy registry, the registry wins:

- `config/strategy_catalog.yaml`
- `docs/SYSTEM_ARCHITECTURE.md`

## Current Snapshot

- Current production-path strategy: `ST-A2`
- Current strategy registry status: `walk_forward`
- Registry approval flag: `approved: true`
- Current implementation mode: `SVOS transitional v1.7`
- Current practical phase: `Phase-1 demo validation`
- Current live-trading mode: `LIVE_TRADING=false`
- Current active gate: `E5 spread capture`
- Current blocker before execution gate: `E6 cost revalidation`
- Current target milestone: `E1-E4 7-day execution gate`
- Current end target: `controlled micro-live on Vantage`

## What Is Already Done

### Strategy Qualification

- ST-A2 passed Phase-0 backtest
- Backtest result: `n=169`, `PF_std=1.151`, `PF_2x=1.025`
- Locked passing run: `20260621T100458-183aaa`
- Strategy is verification-ready in the current workflow

### Execution Readiness

- execution layer deployed
- demo bot connected and running
- forward-test simulator complete
- runtime safety fixes complete
- spread capture tooling complete
- E6 revalidation package complete

### Research / Platform Foundation

- strategy registry implemented
- canonical SVOS audit engine integrated
- enhancement-stage plan generation implemented
- stage reports rendered on the dashboard
- dataset coverage and validation completed for current research window

## Timeline Overview

| Stage | Status | What it means | Target |
|---|---|---|---|
| Strategy Audit | Complete | Strategy can be checked for ambiguity and completeness | machine-readable rulebook |
| Strategy Enhancement | Complete, but not interactive | Clarification plan exists | fully persisted answer-capture loop later |
| Historical Replay | Complete for production path | ST-A2 cleared replay path | replay-safe signal logic |
| Backtest | Complete for ST-A2 | Phase-0 profitability gate passed | retain PF > 1.0 under real-cost revalidation |
| Robustness | Complete for current promotion path | ST-A2 advanced to verification-ready | maintain evidence quality |
| Verification Ready | Complete | Research path cleared | eligible for execution qualification |
| E5 Spread Capture | Running | collecting real Vantage spread data | 5 London + 5 NY sessions + 7,000 rows |
| E6 Cost Revalidation | Ready, blocked on E5 | rerun ST-A2 at measured costs | `PF_2x >= 1.00` |
| E1-E4 Execution Gate | Not started, blocked on E6 | verify runtime and order lifecycle in demo conditions | 7-day clean execution window |
| Micro-Live | Not started | owner-controlled first live capital stage | $1,000 account, 0.25% risk |

## Live Go-To-Market Timeline

### Stage 1. E5 Spread Capture

Status:
`RUNNING`

Current state:

- process started: `2026-06-24 06:01 UTC`
- capture process: `tmux spreads`
- monitor command: `python3 scripts/spread_status.py`

Target:

- at least 5 London sessions
- at least 5 New York sessions
- at least 7,000 rows
- output file: `research/spread_samples.csv`

Projected target date:

- around `2026-06-30`

Why it matters:

- this converts placeholder spread assumptions into measured broker costs

### Stage 2. E6 Cost Revalidation

Status:
`READY BUT BLOCKED ON E5`

Execution command:

```bash
bash scripts/run_e6_revalidation.sh
```

Precondition:

```bash
python3 scripts/check_phase2_completion.py
```

Target:

- fill measured Vantage costs
- rerun ST-A2 under real broker costs
- confirm `PF_2x >= 1.00`

Decision targets:

- `PF_2x > 1.05` -> continue toward micro-live path
- `PF_2x 1.00-1.05` -> demo-only caution zone
- `PF_2x < 1.00` -> stop production path and prepare recovery strategy

### Stage 3. E1-E4 Execution Gate

Status:
`BLOCKED ON E5 AND E6`

This is the next execution milestone after E6.

Target window:

- one 7-day demo execution window with `LIVE_TRADING=true`

Success targets:

- E1: 7 days, 0 crashes, heartbeat gaps under 600 seconds
- E2: at least 1 signal lifecycle event recorded correctly
- E3: at least 1 complete order lifecycle or valid rejection
- E4: manual restart test passes with state intact

### Stage 4. Micro-Live

Status:
`NOT STARTED`

Target configuration:

- broker: Vantage live
- account size: `$1,000`
- risk per trade: `0.25%`
- max open position: `1`
- daily loss limit: `3R`
- drawdown kill switch: `10%`
- first `20 trades` treated as validation-only

## Next Executable Task

The next real task to execute is:

`Finish E5 spread capture and wait for gate completion.`

When E5 completes, the immediate next command is:

```bash
python3 scripts/check_phase2_completion.py
bash scripts/run_e6_revalidation.sh
```

That is the most important next action in the entire project timeline.

## Current Blockers

### Blocker 1. E5 not complete yet

Effect:

- E6 cannot run
- E1-E4 cannot start
- micro-live cannot be evaluated

### Blocker 2. E6 outcome unknown until E5 completes

Effect:

- production viability at real broker costs is not yet confirmed

### Blocker 3. Execution gate depends on cost gate

Effect:

- demo execution validation remains intentionally blocked

## Platform Build Timeline

The production path is close to execution, but the full platform architecture
is still incomplete.

### Already Implemented

- SVOS audit workflow
- strategy registry and catalog-linked validation
- stage report dashboard
- execution validation package
- execution simulator and virtual broker support
- monitoring scripts and execution analytics

### Still Pending To Finish The Master Platform

- `SVOS-04` interactive enhancement session
- `SVOS-05` multi-format intake
- `SVOS-06` audit summary counters
- first-class EVF separation from the transitional SVOS path
- distinct RGM qualification pipeline
- more independent governance control plane
- more explicit SMO runtime service separation

These are important for finishing the institutional platform, but they are not
the immediate blockers for ST-A2 go-live.

## Timeline Targets By Horizon

### Now

- keep E5 running
- monitor spread capture health
- preserve bot stability

### Next

- execute E6 immediately after E5 passes
- decide whether ST-A2 remains deployable at measured costs

### Near-Term

- run E1-E4 7-day execution gate
- validate signal, order, restart, and runtime behavior

### Go-Live Target

- controlled micro-live deployment for ST-A2

### Longer-Term Platform Target

- complete EVF, RGM, Governance, and SMO separation
- finish the pending SVOS workflow enhancements

## Source References

- `config/strategy_catalog.yaml`
- `docs/PROJECT_STATUS.md`
- `docs/PROJECT_OBJECTIVE_FASTEST_PATH.md`
- `docs/IMPLEMENTATION_STATUS.md`
- `docs/OPS02_REVISED_GATE.md`
- `docs/SYSTEM_ARCHITECTURE.md`
