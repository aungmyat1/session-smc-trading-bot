# Project Timeline

Date: 2026-06-28

## Purpose

This is the live timeline for the current project plan.

It shows:

- the workflow being implemented
- the current project position
- the next task to execute
- the target of each stage

## Project Workflow

```text
Strategy Intake
      │
      ▼
Strategy Audit
      │
      ├── FAIL -> AI edits specification -> Audit again
      ▼
Strategy Enhancement
      │
      ├── FAIL -> Resolve unresolved rule questions -> Enhance again
      ▼
Historical Replay
      │
      ├── FAIL -> Refine rules -> Replay again
      ▼
Backtest
      │
      ├── FAIL -> Improve logic or filters -> Backtest again
      ▼
Robustness
      │
      ├── FAIL -> Adjust parameters or simplify rules -> Retest
      ▼
Verification Ready
      │
      ├── FAIL -> Resolve research-stage gaps -> Return to research
      ▼
Virtual Demo Trading
      │
      ├── FAIL -> Analyze live drift -> Return to research
      ▼
Production Approval
```

## Current Snapshot

- canonical branch: `main`
- current scope: `SVOS research and verification engine + simple Vantage trading bot`
- system role: `input strategy -> verify -> approve or reject`
- current active operational gate: `E5 spread capture`
- current next operational gate: `E6 cost revalidation`
- current target after that: `E1-E4` execution gate

## Timeline By Stage

| Stage | Status | Current understanding | Target |
|---|---|---|---|
| Strategy Intake | Implemented | raw strategy text/spec enters the SVOS runner | normalize the strategy into a tracked validation run |
| Strategy Audit | Implemented | strategy validation exists | clear, codable rules |
| Strategy Enhancement | Implemented | audit findings turn into structured clarifications and rewrite guidance | produce a replay-ready rulebook |
| Historical Replay | Implemented | replay capability exists | confirm signal behavior |
| Backtest | Implemented | backtest tooling exists | test profitability after clear rules |
| Robustness | Implemented | robustness stage exists | reject fragile behavior |
| Verification Ready | Implemented | research evidence is consolidated into a pre-demo gate | confirm the strategy can move into controlled broker-connected validation |
| Virtual Demo Trading | Partially active | execution layer exists; gates still active | safe broker-connected validation on Vantage without production capital |
| Production Approval | Not ready for live promotion | approval remains evidence-gated | controlled live promotion only after acceptable Virtual Demo Trading evidence |

## Current Operational Position

For the current execution candidate, the project is here:

```text
Backtest PASS
  ↓
Robustness sufficient for current promotion path
  ↓
Verification-ready handoff
  ↓
E5 spread capture running
  ↓
E6 cost revalidation blocked on E5
  ↓
E1-E4 execution gate blocked on E6
```

## What Is Running Now

### E5 Spread Capture

Status:
`RUNNING`

Current state:

- started: `2026-06-24 06:01 UTC`
- process: `tmux spreads`
- monitor: `python3 scripts/spread_status.py`

Target:

- 5 London sessions
- 5 New York sessions
- 7,000+ rows
- output: `research/spread_samples.csv`

Projected target:

- around `2026-06-30`

### E6 Cost Revalidation

Status:
`READY BUT BLOCKED ON E5`

Command:

```bash
python3 scripts/check_phase2_completion.py
bash scripts/run_e6_revalidation.sh
```

Target:

- measured Vantage costs
- rerun the current execution candidate under real costs
- confirm `PF_2x >= 1.00`

### E1-E4 Execution Gate

Status:
`BLOCKED ON E5 AND E6`

Target:

- 7-day runtime
- signal lifecycle validation
- order lifecycle validation
- restart safety validation

### Production Approval / Controlled Live

Status:
`NOT READY YET`

Target:

- approve only after Virtual Demo Trading evidence remains acceptable

## Next Task To Execute

The next task is:

`Finish E5 spread capture.`

Immediately after E5 passes:

```bash
python3 scripts/check_phase2_completion.py
bash scripts/run_e6_revalidation.sh
```

## Timeline Targets

### Now

- keep spread capture running
- keep the bot stable
- avoid unnecessary expansion

### Next

- run cost revalidation
- decide whether the current approved strategy still passes under measured costs

### Near-Term

- complete the demo execution gate

### After That

- continue demo if valid
- promote to controlled live only after evidence supports it

## Scope Reminder

This timeline is for:

- a simple SVOS loop
- a simple bot
- Vantage demo/live readiness

It is not a roadmap for a larger platform build-out.

## References

- `docs/CURRENT_SCOPE.md`
- `docs/PROJECT_OBJECTIVE_FASTEST_PATH.md`
- `docs/IMPLEMENTATION_STATUS.md`
- `config/strategy_catalog.yaml`
