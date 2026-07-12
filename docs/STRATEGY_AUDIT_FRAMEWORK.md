# Strategy Audit Framework

Status: Authoritative
Version: 1.0
Updated: 2026-06-29
Owner: Quant Research
Authority: Level 5 — Phase Specification
Note: This document and STAGE1_AUDIT_SPEC.md are complementary.
STRATEGY_AUDIT_FRAMEWORK covers the overall audit design;
STAGE1_AUDIT_SPEC defines the 10-validator interface contract.
Related: STAGE1_AUDIT_SPEC.md, SVOS_DESIGN_REFERENCE.md

This repository now includes an institutional-style audit layer above the
research pipeline.

## Purpose

The framework answers one question before allowing a strategy to progress:

Can this strategy be trusted enough to move to the next deployment stage?

It is not a backtester. It is a qualification and quality-assurance layer that
audits:

- strategy logic
- market data quality
- statistical edge
- robustness
- execution realism
- risk limits
- live drift

## Architecture

```text
Research Data
     │
Historical Replay / Live Replay
     │
Strategy Audit Engine
     │
├── Rule Audit
├── Data Audit
├── Statistical Audit
├── Regime Audit
├── Robustness Audit
├── Execution Audit
├── Risk Audit
└── Monitoring Audit
     │
Deployment Gate
```

## Core Package

The implementation lives in `strategy_audit/` and uses the existing research
and execution-validation primitives as upstream dependencies.

Primary entrypoints:

- `python3 scripts/audit_strategy.py`
- `python3 scripts/audit_strategy.py --strategy ST-A2`
- `python3 scripts/audit_strategy.py --payload path/to/payload.json`

## Report Outputs

The framework writes:

- JSON
- Markdown
- HTML
- PDF

to `reports/strategy_audit/<strategy>/`.

## Dependency Graph

```text
strategy_audit.cli
  └── strategy_audit.audit_runner
        └── strategy_audit.audit_engine
              ├── research.svos.engine
              ├── research.robustness
              ├── research.validation.engine
              └── execution_validation.engine
```

## Institutional Notes

- Mandatory modules can block deployment.
- Optional modules improve confidence and readiness score.
- Missing evidence is reported as `NOT_VERIFIED` rather than assumed.
- The deployment gate is configurable through `strategy_audit/config/`.

