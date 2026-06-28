# Implementation Status

Date: 2026-06-28

This document summarizes the current repository transition toward the target
ISOP architecture described in `docs/SYSTEM_ARCHITECTURE.md`.

## Current State

- Target architecture: `ISOP v2`
- Current implementation: `SVOS transitional v1.7`
- Strategy state authority: `config/strategy_catalog.yaml`

## Transition Progress

### Research Layer

- Status: largely implemented
- Evidence:
  - `research/svos/`
  - `strategy_audit/`
  - replay/backtest/robustness stages

### Execution Layer

- Status: partially migrated
- Evidence:
  - `execution_validation/`
  - execution evidence integrated into SVOS virtual-demo stage
- Remaining gap:
  - execution qualification is still invoked through the SVOS pipeline rather
    than fully separated as a first-class EVF workflow

### Risk Layer

- Status: design ahead of implementation
- Evidence:
  - risk concepts documented in README and architecture docs
  - some runtime risk controls exist in execution code
- Remaining gap:
  - no fully separated RGM qualification pipeline yet

### Governance

- Status: partially implemented
- Evidence:
  - strategy registry exists
  - promotion and approval logic exists in current SVOS/registry flow
- Remaining gap:
  - governance is not yet a fully independent control plane in code

### Monitoring

- Status: basic implementation present
- Evidence:
  - operational monitoring scripts
  - analytics and health-check tooling
- Remaining gap:
  - SMO and RGM runtime monitoring are not yet fully separated in implementation

## Source-of-Truth Rule

- Architecture source of truth: `docs/SYSTEM_ARCHITECTURE.md`
- Strategy state source of truth: `config/strategy_catalog.yaml`
- Transitional workflow implementation: `research/svos/engine.py`

If these disagree:

1. registry state wins for strategy status
2. `SYSTEM_ARCHITECTURE.md` wins for intended lifecycle semantics
3. code wins for what the repository can actually execute today
