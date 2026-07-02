# System Architecture

---
Owner: Platform Architecture
Status: Authoritative
Version: 2.0
Last Reviewed: 2026-06-29
Next Review: TODO
Related Documents: DOC_AUTHORITY.md, CORE_ARCHITECTURE.md, IMPLEMENTATION_PLAN.md
---

Governing product truth:
`docs/00_Project/TWO_SYSTEM_ARCHITECTURE_TRUTH.md`. SVOS is the Strategy
Research and Validating System; Production is the simple execution engine.

This document is the authoritative architecture and lifecycle reference for the
repository.

Branching note:

- `main` is the canonical branch for the current platform stage of this
  repository
- the repository name remains `session-smc-trading-bot`, but the system has
  grown into a broader strategy validation and execution platform

If the lifecycle changes, update these in order:

1. `config/strategy_catalog.yaml`
2. `docs/SYSTEM_ARCHITECTURE.md`
3. generated or status-facing project documents

Related workflow governance documents:

- `docs/AI_WORKFLOW_ARCHITECTURE.md`
- `docs/DEVELOPER_HANDBOOK.md`
- `docs/templates/implementation_spec_template.md`

## Architecture Status

- Architecture target: `ISOP v2`
- Current implementation: `SVOS transitional v1.7`
- Transitional strategy projection: `config/strategy_catalog.yaml`
- Target authoritative strategy state: PostgreSQL control-plane repositories

The repository is currently transitioning from a unified SVOS-driven validation
pipeline into the full target separation of:

`SVOS -> EVF -> RGM -> Governance -> SMO`

In other words, the current `main` branch should be interpreted as the
platform's canonical state rather than as a narrow session-bot-only branch.

## Lifecycle Vocabulary Reference

Current implemented lifecycle names come from `svos/lifecycle/manager.py`.
Target ISOP lifecycle names remain useful for roadmap discussions, but they are
not yet the active runtime vocabulary unless the code implements them.

| Current Implemented Stage | Summary |
|---|---|
| `DRAFT` | Created, not submitted |
| `INTAKE` | Intake review |
| `AUDIT` | Rule quality gate |
| `REFINEMENT` | Specification improvement |
| `HISTORICAL_REPLAY` | Logic verification |
| `STATISTICAL_VALIDATION` | Transitional combined identifier; target architecture separates Backtest execution from Statistical Validation decision |
| `ROBUSTNESS_VALIDATION` | Walk-forward, MC, parameter stability |
| `VIRTUAL_DEMO` | **Offline** replay via bot interfaces — no broker |
| `PRODUCTION_APPROVAL` | Record-only approval stage during current construction scope |
| `REVALIDATION` | Drift-triggered re-entry |
| `RETIRED` | Permanently removed |

## Current Implementation

The code currently implements a transitional lifecycle centered on SVOS:

```text
Strategy Intake
  ↓
Strategy Audit
  ↓
Strategy Enhancement
  ↓
Historical Replay
  ↓
Backtest
  ↓
Statistical Validation
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

In the current codebase, Backtest and Statistical Validation share transitional
implementation paths. They remain distinct architectural responsibilities.
`virtual_demo` and `production_approval` remain SVOS
pipeline stages for backward compatibility.

In practical terms, the repository is designed as a research gate rather than a
"backtest first" tool. The intended operational behavior is:

- strategy logic is normalized before replay
- ambiguous or contradictory rules are blocked before backtest
- enhancement exists to clarify and harden the rulebook before evidence stages
- statistical testing only happens after the specification is sufficiently
  objective and machine-readable

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
- strategy enhancement
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

During stabilization, `config/strategy_catalog.yaml` is a compatibility input
and read-only projection for legacy readers. PostgreSQL becomes authoritative
only after migration, restore, concurrency, and fail-closed acceptance tests
pass. Until that cutover, no component may treat a YAML write as a fallback
for a failed database mutation.

The compatibility projection exposes:

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
