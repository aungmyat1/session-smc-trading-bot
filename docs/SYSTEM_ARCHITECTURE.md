# System Architecture

Date: 2026-06-28

This document is the authoritative architecture and lifecycle reference for the
repository.

If the lifecycle changes, update these in order:

1. `config/strategy_catalog.yaml`
2. `docs/SYSTEM_ARCHITECTURE.md`
3. generated or status-facing project documents

## Architecture Status

- Architecture target: `ISOP v2`
- Current implementation: `SVOS transitional v1.7`
- Authoritative strategy state: `config/strategy_catalog.yaml`

The repository is currently transitioning from a unified SVOS-driven validation
pipeline into the full target separation of:

`SVOS -> EVF -> RGM -> Governance -> SMO`

## Current Implementation

The code currently implements a transitional lifecycle centered on SVOS:

```text
Strategy Intake
  ↓
Strategy Audit
  ↓
Historical Replay
  ↓
Backtest
  ↓
Robustness
  ↓
Verification Ready
  ↓
Virtual Demo Trading
  ↓
Production Approval
```

The current implementation is reflected in:

- `research/svos/engine.py`
- `scripts/run_current_strategy_svos.py`
- `scripts/run_svos_pipeline.py`

In the current codebase, `virtual_demo` and `production_approval` remain SVOS
pipeline stages for backward compatibility.

## Target Architecture

The target architecture is the institutional operating model the repository is
moving toward:

```text
Strategy Idea
  ↓
SVOS Research Qualification
  ↓
Research Qualified
  ↓
Verification Ready
  ↓
EVF Execution Qualification
  ↓
Execution Qualified
  ↓
Operational Ready
  ↓
RGM Risk Qualification
  ↓
Risk Qualified
  ↓
Risk Approved
  ↓
Live Demo Authorization
  ↓
Live MT5 Demo
  ↓
Production Candidate
  ↓
Production Approval
  ↓
Production
  ↓
SMO Monitoring
  ↓
Drift Detection
  ↓
Revalidation
```

## Responsibilities

### SVOS

Question:
"Does the strategy have evidence of an edge?"

Owns:

- strategy intake
- strategy audit
- historical replay
- statistical validation
- robustness validation
- research qualification evidence

### EVF

Question:
"Can the strategy execute correctly and safely?"

Owns:

- virtual execution validation
- broker simulation
- market microstructure simulation
- cost and latency modelling
- order lifecycle simulation
- recovery validation
- execution evidence generation

### RGM

Question:
"Can capital be allocated safely?"

Owns:

- risk qualification
- allocation validation
- exposure validation
- portfolio impact validation
- capital preservation controls
- emergency controls

Runtime responsibility after deployment:

- risk monitoring
- drawdown monitoring
- risk limit monitoring
- capital protection

### Governance

Question:
"Should the strategy move forward?"

Owns:

- strategy registry
- stage gate decisions
- approval workflow
- promotion control
- live demo authorization
- production approval

### SMO

Question:
"Is live behavior still within acceptable bounds?"

Owns:

- production monitoring
- drift detection
- revalidation triggers
- operator monitoring workflows

## Lifecycle Terms

### Research Qualified

Research evidence exists and the strategy has passed its research gates.

Responsible:
`SVOS`

### Verification Ready

Governance has accepted the research evidence and approved entry into execution
qualification.

Responsible:
`Governance`

### Execution Qualified

Execution evidence shows the strategy can operate correctly in the modeled
execution environment.

Responsible:
`EVF`

### Operational Ready

The operating environment is ready for controlled risk evaluation.

Responsible:
`EVF`, with governance-controlled transition into `RGM`

### Risk Qualified

Risk evidence shows the strategy can be evaluated for controlled capital
allocation.

Responsible:
`RGM`

### Risk Approved

Controlled capital exposure is permitted.

Responsible:
`RGM`

### Live Demo Authorization

Governance has authorized real broker demo observation.

Responsible:
`Governance`

### Production Approval

Governance has authorized production release.

Responsible:
`Governance`

## Registry

`config/strategy_catalog.yaml` is the authoritative source for:

- current strategy
- strategy status
- approval state
- deployment target
- latest recorded SVOS metadata

If a prose document disagrees with the registry, the registry wins.

## Documentation Policy

Other docs should not redefine the lifecycle independently.

They should either:

- reference this document directly, or
- explicitly state they describe the `current implementation` rather than the
  `target architecture`
