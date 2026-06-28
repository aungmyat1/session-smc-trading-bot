# AI Workflow Architecture

Date: 2026-06-28

This document defines how AI-assisted work should be structured in this
repository so architecture quality stays high while implementation cost stays
controlled.

It complements:

- `docs/SYSTEM_ARCHITECTURE.md`
- `docs/IMPLEMENTATION_STATUS.md`
- `docs/AGENT_RULES.md`
- `CLAUDE.md`

If these documents disagree, apply them in this order for AI workflow:

1. repository safety and trading constraints in `docs/AGENT_RULES.md`
2. lifecycle and architecture semantics in `docs/SYSTEM_ARCHITECTURE.md`
3. implementation reality in `docs/IMPLEMENTATION_STATUS.md`
4. this document for task orchestration and prompt layering

## Purpose

Separate high-value design work from repetitive implementation work.

The expensive part of AI development is architecture, boundary definition,
acceptance criteria, and review discipline. Repetitive implementation should
follow a frozen specification instead of reinventing the design on every task.

## Operating Model

```text
Owner / Operator
        │
        ▼
Architecture Layer
        │
        ├─ system design
        ├─ module boundaries
        ├─ public APIs
        ├─ acceptance criteria
        └─ test plan
        ▼
Frozen Implementation Spec
        │
        ▼
Execution Layer
        │
        ├─ implement one module or task
        ├─ add tests
        ├─ refactor within spec boundaries
        └─ avoid redesign
        ▼
Review Layer
        │
        ├─ compare output to spec
        ├─ check edge cases and regressions
        ├─ verify architecture compliance
        └─ approve or reject
        ▼
Repository
```

## Three-Layer Prompt Strategy

### 1. Architecture Layer

Use a stronger reasoning pass for:

- architecture decisions
- lifecycle changes
- folder and module boundaries
- public API design
- schema and config design
- acceptance criteria
- test planning

Outputs should be durable and low-churn:

- architecture docs
- ADRs
- implementation specs
- task contracts

### 2. Execution Layer

Use a lower-cost implementation pass for:

- writing one class or module
- adding one endpoint or CLI command
- writing or updating tests
- refactoring internals without changing the contract
- documentation updates scoped to the change

Execution tasks must not redesign architecture unless the task explicitly says
the spec is being reopened.

### 3. Review Layer

Use a stronger review pass for:

- spec compliance
- missing edge cases
- correctness
- maintainability
- performance-sensitive paths
- security and safety
- readiness to merge

Only reviewed work should be treated as complete.

## Required Workflow

### Step 1. Design before implementation

Before multi-file work, produce or confirm:

- responsibilities
- inputs and outputs
- public API
- invariants
- failure behavior
- acceptance criteria
- tests to add or update

For this repository, design must respect:

- no lookahead bias
- UTC-first time handling
- separation of research, execution, risk, and governance concerns
- stage-gated promotion semantics

### Step 2. Freeze the spec

Implementation should begin only after the task contract is stable enough to
execute without reinterpreting the architecture.

Use the template in `docs/templates/implementation_spec_template.md`.

### Step 3. Execute narrowly

Implementation prompts should be shaped like:

- implement `X` according to the spec
- do not change the public API
- keep changes within listed files unless tests require expansion
- add tests for each acceptance criterion

Avoid prompts like:

- build the whole trading platform
- redesign this subsystem while fixing the bug

### Step 4. Review against the frozen spec

Every substantial change should be checked for:

- contract compliance
- regression risk
- missing tests
- lifecycle alignment
- safety rule violations

## Definition of Ready

A task is ready for execution when all of the following are known:

- scope
- target files or module area
- public API or operator contract
- acceptance criteria
- test expectations
- non-goals

If any of these are missing, the task belongs back in the architecture layer.

## Definition of Done

A task is done when:

- implementation matches the frozen spec
- tests covering the change pass
- no repository hard rule is violated
- docs are updated if user-visible behavior or lifecycle meaning changed
- review finds no blocking gaps

## Spec Freeze Rules

The execution layer may clarify implementation details, but it must not change:

- module ownership
- public API shape
- lifecycle stage meanings
- risk or execution safety constraints
- strategy semantics

If one of those must change, stop execution and reopen architecture review.

## Repository-Specific Guidance

### Prefer specs over chats

For trading logic, stage gates, and validation semantics, the repo should rely
on committed specifications instead of relying on conversational memory.

### Keep architecture docs authoritative

If a lifecycle change is approved, update:

1. `config/strategy_catalog.yaml`
2. `docs/SYSTEM_ARCHITECTURE.md`
3. implementation/status docs
4. code

### Keep implementation tasks small

Good execution tasks in this repo look like:

- implement one validator in `strategy_validation/validators/`
- add one report field and tests
- add one replay metric
- refactor one service behind an unchanged API

Bad execution tasks look like:

- rebuild SVOS and EVF end to end
- redesign research and execution together

## Suggested Artifacts

To make this workflow concrete, prefer these committed artifacts:

- architecture docs in `docs/`
- implementation specs in `docs/specs/` or task-local docs
- ADRs for non-trivial architecture decisions
- reusable templates in `docs/templates/`

## Example Task Contract

```text
Module:
Strategy Audit Engine

Inputs:
- strategy.yaml
- market_config.yaml

Outputs:
- audit_report.json

Responsibilities:
- detect ambiguity
- detect contradictions
- validate completeness
- generate recommendations

Acceptance Criteria:
- deterministic results
- no side effects
- all targeted tests pass

Public API:
audit_strategy(strategy_path) -> AuditReport
```

## Decision Rule

When choosing between "implement now" and "design first":

- choose design first for new subsystems, new contracts, or lifecycle changes
- choose implement now for scoped work inside a frozen contract

That separation is the main cost and quality control mechanism.
