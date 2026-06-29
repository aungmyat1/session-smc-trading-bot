# Strategy Validation Operating System

This repository is an institutional-style strategy research, validation,
execution-verification, and governance platform for quantitative trading
workflows.

It is not just a backtester and it is not just a trading bot.

It is designed to move a strategy through governed research stages, separate
research from execution risk, and prevent uncontrolled promotion into demo or
live deployment.

Repository identity note:

- repository name: `session-smc-trading-bot`
- current canonical branch: `main`
- current meaning of `main`: the branch now represents the platform stage of
  the project, not a narrow single-strategy bot snapshot

In this stage, the repository should be understood as a trading strategy
validation and execution platform with these core capabilities:

- research and strategy audit
- replay and backtesting
- robustness and validation gates
- execution simulation and demo trading
- governance before live deployment

Current scope note:

- the repository contains broader platform-oriented components
- but the current development scope is intentionally narrower
- current priority is an SVOS research-and-verification engine plus a simple
  Vantage demo/live trading bot
- governing scope: `docs/svos/STRATEGY_ENGINEERING_PLATFORM_IMPLEMENTATION_PLAN.md`
- active stabilization roadmap:
  `docs/svos/architecture-review-2026-06-29/06_UPGRADE_ROADMAP.md`
- current stabilization status: `docs/svos/STABILIZATION_STATUS.md`

## Repository Status

Architecture review update (2026-06-29): the repository is currently assessed
as **NOT READY** for further feature expansion. The review found Critical
governance-bypass, control-state persistence, and operator API security risks.
Complete stabilization Phases 0–2 before resuming bounded feature development.
See `docs/svos/architecture-review-2026-06-29/README.md`.

This repository is currently transitioning from a unified SVOS validation
pipeline to the full ISOP target architecture.

- Architecture source of truth: `docs/SYSTEM_ARCHITECTURE.md`
- Current implementation plan:
  `docs/svos/STRATEGY_ENGINEERING_PLATFORM_IMPLEMENTATION_PLAN.md`
- Strategy state source of truth: `config/strategy_catalog.yaml`
- AI workflow and prompt layering: `docs/AI_WORKFLOW_ARCHITECTURE.md`
- Repository implementation constitution: `docs/DEVELOPER_HANDBOOK.md`
- Implementation task contract template:
  `docs/templates/implementation_spec_template.md`

Current implementation:

```text
SVOS
├── Research Validation
├── Virtual Execution Validation
└── Production Approval
```

Target architecture:

```text
SVOS
  ↓
Verification Ready
  ↓
EVF
  ↓
RGM
  ↓
Governance
  ↓
SMO
```

The repository is being refactored toward this separation while maintaining
backward compatibility with the current SVOS-driven workflow.

Branch policy:

- `main` is the canonical branch for the current platform state
- branch swaps are not required to express the broader platform identity
- strategy-specific or experimental work should live on separate branches until
  intentionally promoted

Current delivery focus:

- do not expand the project unnecessarily
- prioritize the direct path to a simple strategy verification workflow and
  Vantage demo/live execution
- treat broader platform build-out as deferred unless it directly supports that
  goal

## Overview

SVOS is the research and governance operating system for strategy qualification.
EVF is the execution validation layer that checks whether a strategy can be
operated safely once research has produced verification-ready evidence.

SVOS validates whether a strategy has an edge.
EVF validates whether that edge can actually be executed safely.

The target progression is:

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

## Top-Level Architecture

```text
                    ISOP

        Intelligent Strategy Operating Platform

             Strategy Registry

                    │

        Governance Control Plane

                    │
                    │ controls transitions
                    │
 ---------------------------------------------------

 ┌───────────────────────────────────────────┐
 │                 SVOS                      │
 │        Research Qualification             │
 │ Audit → Replay → Backtest → Robustness   │
 └───────────────────────────────────────────┘

                    │
                    ▼
          Verification Ready
                    │
                    ▼
 ┌───────────────────────────────────────────┐
 │                  EVF                      │
 │      Execution Qualification              │
 │ Virtual Execution → Microstructure →      │
 │ Cost → Latency → Recovery → Evidence      │
 └───────────────────────────────────────────┘

                    │
                    ▼
           Operational Ready
                    │
                    ▼
 ┌───────────────────────────────────────────┐
 │                  RGM                      │
 │        Risk Qualification                 │
 │ Allocation → Exposure → Preservation →    │
 │ Constraints → Emergency Controls          │
 └───────────────────────────────────────────┘

                    │
                    ▼
        Deployment Lifecycle / Governance
                    │
                    ▼
               Production
                    │
                    ▼
                  SMO
      Monitoring / Drift Detection / Revalidation
```

## System Architecture

```text
                    Strategy Validation Operating System

                    Strategy Intake
                            │
                            ▼
                     Strategy Audit
                            │
                            ▼
                    AI Strategy Editor
                            │
                            ▼
                    Historical Replay
                            │
                            ▼
                 Statistical Validation
                            │
                            ▼
                  Robustness Validation
                            │
                            ▼
                    Verification Ready
                            │
                            ▼
               EVF Execution Qualification
                            │
 ┌───────────────────────────────────────────┐
 │ Virtual Execution Engine                  │
 │ Broker Simulation Engine                  │
 │ Market Microstructure Engine              │
 │ Cost Model: Spread / Commission / Swap /  │
 │            Slippage                       │
 │ Latency Model: Signal / Network / Broker  │
 │ Order Lifecycle Simulator                 │
 │ Failure Recovery Engine                   │
 │ Execution Evidence Generator              │
 └───────────────────────────────────────────┘
                            │
                            ▼
                  Execution Qualified
                            │
                            ▼
                     Operational Ready
                            │
                            ▼
                 RGM Risk Qualification
                            │
      ┌──────────────┬──────────────┬──────────────┬──────────────┐
      │              │              │              │              │
      ▼              ▼              ▼              ▼              ▼
 Risk Validation  Allocation     Exposure       Portfolio      Capital
                  Validation     Validation     Impact         Preservation
                                                 Validation    Engine
                            │
                            ▼
                     Risk Qualified
                            │
                            ▼
                      Risk Approved
                            │
                            ▼
                Live Demo Authorization
                            │
                            ▼
                      Live MT5 Demo
                            │
                            ▼
                  Production Candidate
                            │
                            ▼
                  Production Approval
                            │
                            ▼
                         Production
                            │
                            ▼
                       SMO Monitoring
```

## Architecture

### Platform Layers

```text
Platform
  │
  ├── Research Layer
  │
  ├── Execution Layer
  │
  ├── Risk Layer
  │
  └── Governance Layer
```

### Research Layer

- Strategy Intake
- Strategy Audit
- AI Strategy Editor
- Historical Replay
- Statistical Validation
- Robustness Validation
- Research Qualified
- Verification Ready

### Execution Layer

- Virtual Execution Validation
- Execution Validation Framework
- Broker Simulation
- Market Microstructure Engine
- Slippage and Latency Testing
- Order Lifecycle Simulation
- Recovery Testing

### Risk Layer

- Risk Validation
- Allocation Validation
- Exposure Validation
- Portfolio Impact Validation
- Capital Preservation Engine
- Emergency Controls

### Governance Layer

- Strategy Registry
- Stage Gate Engine
- Decision Engine
- Approval Engine
- Audit Logger
- Promotion Controller
- Live Demo Authorization
- Production Approval

The core design principle is separation of concerns:

- Research decides whether a strategy appears valid.
- Execution decides whether the strategy can be operated safely.
- Risk decides whether the strategy is safe to allocate.
- Governance decides whether promotion is allowed.

### Decision Responsibility Model

```text
Research Layer
Question:
"Does this strategy have evidence of an edge?"

Responsible:
SVOS


Execution Layer
Question:
"Can this strategy operate reliably?"

Responsible:
EVF


Risk Layer
Question:
"Can we safely allocate capital?"

Responsible:
RGM


Governance Layer
Question:
"Should this strategy move forward?"

Responsible:
Approval Engine
```

In practice the governance flow is:

```text
Metrics
  ↓
Decision Engine
  ↓
Promotion Recommendation
  ↓
Approval
```

## Workflow

### SVOS Research Pipeline

```text
                    Strategy Validation Operating System (SVOS)

        New Strategy
              │
              ▼
      Phase 0 — Strategy Intake
              │
              ▼
      Phase 1 — Strategy Audit
              │
              ▼
      Phase 2 — AI Strategy Editor
              │
              ▼
      Phase 3 — Historical Replay
              │
              ▼
      Phase 4 — Statistical Validation
              │
              ▼
      Phase 5 — Robustness Validation
              │
              ▼
      Research Qualified
              │
              ▼
      Verification Ready
```

### Execution Qualification Pipeline

```text
              Verification Ready
                      │
                      ▼
      EVF Execution Qualification
                      │
      ├── Virtual Execution Validation
      ├── Broker Simulation
      ├── Market Microstructure Engine
      ├── Cost Model
      ├── Latency Model
      ├── Order Lifecycle Simulation
      ├── Failure Recovery Engine
      └── Execution Evidence Generator
      │
      ▼
          Execution Qualified
                      │
                      ▼
              Operational Ready
                      │
                      ▼
          RGM Risk Qualification
                      │
                      ▼
              Risk Qualified
                      │
                      ▼
                Risk Approved
                      │
                      ▼
            Live Demo Authorization
                      │
                      ▼
                Live MT5 Demo
                      │
                      ▼
            Production Candidate
                      │
                      ▼
             Production Approval
                      │
                      ▼
                  Production
```

### Validation Progression

```text
Historical Replay
      │
      ▼
Backtest
      │
      ▼
Robustness
      │
      ▼
Verification Ready
      │
      ▼
EVF Execution Qualification
      │
      ├── Virtual Execution Validation
      ├── Broker Simulation
      ├── Market Microstructure Engine
      ├── Cost / Latency Models
      ├── Order Lifecycle Simulation
      └── Recovery Testing
      │
      ▼
Execution Qualified
      │
      ▼
Operational Ready
      │
      ▼
RGM Risk Qualification
      │
      ▼
Risk Qualified
      │
      ▼
Risk Approved
      │
      ▼
Live Demo Authorization
      │
      ▼
Live MT5 Demo
(real-time market observation)
      │
      ▼
Production Candidate
      │
      ▼
Production
```

This repository distinguishes between two demo concepts:

- `Historical Replay`: tests whether strategy logic works.
- `Virtual Execution Validation`: simulated execution and recovery validation
  before real-time exposure. It replays historical markets using a live-like
  broker simulation so execution behaviour can be evaluated without waiting for
  real market time. It is part of EVF execution qualification, not part of
  research.
- `Live MT5 Demo`: real broker demo observation after the strategy is already
  operationally and risk approved.

### Strategy Lifecycle

```text
Draft
  ↓
Research Candidate
  ↓
Audited
  ↓
Research Qualified
  ↓
Verification Ready
  ↓
Execution Qualified
  ↓
Operational Ready
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
Production Approved
  ↓
Production
  ↓
Monitoring
  ↓
Drift Detection
  ↓
Revalidation
  ↓
Retired
```

### Revalidation Loop

```text
Strategy Change
      │
      ▼
Version Created
      │
      ▼
Audit
      │
      ▼
Replay
      │
      ▼
Backtest
      │
      ▼
Robustness
      │
      ▼
Verification Ready
      │
      ▼
EVF Execution Qualification
      │
      ├── Virtual Execution Validation
      ├── Broker Simulation
      ├── Market Microstructure Engine
      ├── Cost / Latency Models
      ├── Order Lifecycle Simulation
      └── Recovery Testing
      │
      ▼
Execution Qualified
      │
      ▼
Operational Ready
      │
      ▼
RGM Risk Qualification
      │
      ▼
Risk Qualified
      │
      ▼
Risk Approved
      │
      ▼
Live Demo Authorization
      │
      ▼
Live MT5 Demo
      │
      ▼
Production Candidate
      │
      ▼
Production
      │
      ▼
Performance Drift
      │
      ▼
Automatic Revalidation
```

SVOS is not a one-pass pipeline. Strategies remain continuously governed and
revalidatable after deployment decisions.

## Components

### Verification Ready

`Verification Ready` is the research-to-execution handoff point.

It is the formal handoff point between research and execution.

At this point the strategy has passed:

- Strategy Audit
- Historical Replay
- Statistical Validation
- Robustness Validation

The strategy has research evidence of an edge.

`Research Qualified` means the research evidence exists.

`Verification Ready` means governance has accepted that evidence and approved
entry into EVF execution qualification.

It does not mean the strategy is:

- executable
- risk approved
- demo approved
- production approved

It has not yet been exposed to live market conditions.

### Virtual Execution Validation

`Virtual Execution Validation` belongs to execution qualification rather than
research qualification.

Within the institutional lifecycle, it is one of the core EVF execution
qualification checks.

It answers:

- Would this strategy behave correctly if executed in a live-like environment?

It focuses on:

- Order timing
- Spread expansion
- Slippage
- Partial fills
- Requotes
- Latency
- Position recovery
- Stop/limit execution
- Failure handling
- Recovery logic

### Market Microstructure Engine

`Market Microstructure Engine` is a first-class EVF module rather than a hidden
parameter inside the execution simulator.

Typical inputs:

- Tick data
- Spread history
- Liquidity model
- Volatility regime
- Session context
- News events

Typical outputs:

- Expected fill quality
- Slippage distribution
- Spread expansion risk
- Execution probability

Institutionally the sequence is:

```text
Market Environment
      │
      ▼
Market Microstructure Engine
      │
      ▼
Execution Simulator
```

### Operational Ready

`Operational Ready` means EVF has produced execution-qualified evidence and the
execution stack is ready for controlled risk review.

This distinction matters because a strategy can pass EVF and still fail RGM
limits such as drawdown, exposure concentration, or portfolio interaction
constraints.

Operational Ready typically means:

1. Execution behavior validated
2. Broker simulation passed
3. Slippage tolerance confirmed
4. Latency tolerance confirmed
5. Recovery procedures tested
6. Operational monitoring configured

### Research Principles

- No strategy skips validation stages.
- Every stage is reproducible.
- Every decision is versioned.
- Every promotion requires objective evidence.
- No manual overrides should happen without audit logging.
- Every strategy should remain continuously revalidatable.

### Architecture Principles

- Research and execution are isolated.
- Every phase is independently reproducible.
- All promotions are evidence-based.
- Every decision is auditable.
- Strategy versions are immutable.
- Revalidation is continuous.
- Configuration is preferred over hard-coded logic.
- Every report is reproducible.

### Platform Components

- `SVOS`: research governance and lifecycle control
- `EVF`: execution verification and operational readiness checks
- `RGM`: risk governance and allocation control
- `SMO`: strategy monitoring, drift detection, and revalidation operations
- `Research Data Layer`: market data normalization and feature generation
- `Strategy Registry`: version control and lifecycle state
- `Governance`: approval workflow, gating, and audit traceability

### AI Services

- Strategy Parsing
- Rule Extraction
- Rule Refinement
- Root Cause Analysis
- Audit Assistance
- Report Generation
- Revalidation Recommendations

### Governance

Every phase is controlled by explicit gates.

Possible outcomes include:

- `PASS`
- `FAIL`
- `BLOCKED`
- `REQUIRES REVIEW`
- `CONDITIONAL APPROVAL`
- `APPROVED`

Progression should happen only when mandatory criteria are satisfied and the
strategy registry permits the next lifecycle stage.

Example conditional decision:

```json
{
  "decision": "CONDITIONAL APPROVAL",
  "allowed": "LIVE_DEMO",
  "not_allowed": "PRODUCTION",
  "reason": "Execution gates passed but exposure controls require monitoring"
}
```

### Gate Output Schema

Each gate should produce machine-readable output in a shape like:

```yaml
stage:
  name: robustness_validation

status:
  PASS

confidence:
  91%

evidence:
  - robustness_report.json
  - monte_carlo_test.json

failures: []

recommendation:
  next_stage: evf_execution_qualification

approved_by:
  system
```

### Risk Governance Module

`RGM` should be thought of as:

```text
Risk Governance Module (RGM)
├── Risk Validation
├── Allocation Validation
├── Exposure Validation
├── Portfolio Impact Validation
├── Correlation Analysis
├── Stress Testing
├── Capital Preservation Engine
└── Emergency Controls
```

This separates:

- `Risk Validation`: can this strategy trade safely?
- `Allocation Validation`: how much capital should this strategy receive?
- `Capital Preservation Engine`: how do we prevent catastrophic loss?

### RGM Runtime Monitoring

After deployment, capital safety remains an RGM responsibility, but it belongs
to runtime monitoring rather than qualification:

```text
RGM Monitoring
├── Exposure Monitoring
├── Drawdown Monitoring
├── Risk Limit Monitoring
├── Capital Protection
└── Emergency Shutdown
```

### Strategy Registry

Each strategy is expected to have auditable metadata in the catalog, including:

- Strategy ID
- Version
- Status
- Current phase
- Validation history
- Rule specification
- Performance history
- Deployment status
- Approval history
- Immutable strategy fingerprint

The current catalog lives in `config/strategy_catalog.yaml`.

An immutable fingerprint should tie together:

```yaml
strategy_identity:
  strategy_hash: a81f92c77d21
  rule_hash: 88ff921abc
  data_version: dukascopy_2026_06
  feature_version: feature_db_v3
  replay_engine_version: replay_engine_v2.1
  parameter_version: params_v4
  execution_model_version: exec_model_v2
  broker_model_version: broker_model_v3
  slippage_model_version: slippage_model_v2
  latency_model_version: latency_model_v1
  risk_model_version: risk_model_v2
  governance_version: governance_v1
  environment: demo
```

In practice:

```text
Strategy =
Rules
+
Parameters
+
Data
+
Features
+
Research Engine
+
Execution Model
+
Risk Model
+
Governance Rules
+
Software Version
+
Broker Environment
```

### Quality Gates

| Stage | Question | Evidence |
|---|---|---|
| Strategy Audit | Are rules complete? | Strategy specification |
| Replay | Does logic behave correctly? | Replay report |
| Backtest | Is there statistical edge? | Performance report |
| Robustness | Does edge survive variation? | Robustness report |
| Verification Ready | Is research qualified? | Verification certificate |
| Execution Qualified | Has EVF certified execution behavior? | Execution certificate |
| Operational Ready | Is the system ready for controlled risk evaluation? | Operational approval |
| Risk Qualified | Has RGM validated capital preservation and exposure control? | Risk certificate |
| Risk Approved | Is controlled capital exposure permitted? | Risk approval |
| Live Demo Authorization | Is live demo observation authorized? | Demo authorization |
| Live Demo | Does reality match model? | Demo report |
| Production Approval | Is deployment allowed? | Approval certificate |

Project-specific thresholds are configured in validation and strategy
configuration files rather than hardcoded in the README.

### Research Artifacts

Each phase is expected to produce evidence.

```text
Strategy Specification
      │
      ▼
Replay Report
      │
      ▼
Performance Report
      │
      ▼
Robustness Report
      │
      ▼
Verification Certificate
      │
      ▼
EVF Execution Report
      │
      ▼
Operational Certificate
      │
      ▼
Risk Certificate
      │
      ▼
Live Demo Report
      │
      ▼
Production Decision
```

### Failure Classification

An AI diagnostic layer should classify failures into actionable buckets such as:

- Strategy Logic Failure
- Market Dependency Failure
- Execution Failure
- Data Failure

This shortens the loop between failed validation and the next research action.

### Research Data Layer

The research data stack is layered as follows:

```text
Raw Tick Data
      │
      ▼
OHLC Database
      │
      ▼
Feature Extraction
      │
      ▼
Research Database
      │
      ▼
Strategy Validation
```

Build the M1 research data layer with:

```bash
make research-db
```

That runs:

```bash
python3 run_pipeline.py --symbols EURUSD GBPUSD XAUUSD
```

Key outputs:

- `research_db/data/processed/candles_labeled.parquet`
- `research_db/data/processed/structure.parquet`
- `research_db/data/processed/sweeps.parquet`
- `research_db/data/processed/order_blocks.parquet`
- `research_db/data/processed/fvg.parquet`
- `research_db/feature_database.parquet`
- `research_db/feature_database.duckdb`

Focused tests:

```bash
make test-research-db
```

## Quick Start

1. Choose the strategy in `config/strategy_catalog.yaml`.
2. Build the research data layer if fresh feature data is required.
3. Run SVOS through the intended validation stage.
4. Review the generated reports and registry state.
5. Run EVF and live demo only after verification-ready evidence exists.

## Operations Guide

### Current-Strategy Revalidation

Use this when replay, backtest, and recent metrics already exist and you want a
non-promoting validation check:

```bash
python3 scripts/run_current_strategy_validation.py --sync-db \
  --replay-json path/to/replay.json \
  --backtest-json path/to/backtest.json \
  --latest-json path/to/latest_metrics.json
```

### Research-Only SVOS Run

Use this when you want the research workflow to stop at the verification-ready
handoff:

```bash
python3 scripts/run_current_strategy_svos.py \
  --stop-after verification_ready \
  --replay-json path/to/replay.json \
  --backtest-json path/to/backtest.json \
  --robustness-json path/to/robustness.json
```

### Full Qualification Run

Use this when you want the governed flow to include both the SVOS research
stages and the EVF handoff evidence.

The current CLI still uses the legacy `--virtual-demo-json` flag name for the
virtual execution evidence payload:

```bash
python3 scripts/run_current_strategy_svos.py \
  --replay-json path/to/replay.json \
  --backtest-json path/to/backtest.json \
  --robustness-json path/to/robustness.json \
  --virtual-demo-json path/to/demo.json
```

### Execution Validation Framework

Use EVF when validating execution quality rather than strategy profitability:

```bash
python3 scripts/run_evf.py \
  --payload path/to/execution_payload.json \
  --strategy ST-A2 \
  --period 2023-2026 \
  --rules execution_validation/config/validation_rules.yaml
```

Legacy entrypoint:

```bash
python3 scripts/run_execution_validation.py \
  --payload path/to/execution_payload.json \
  --strategy ST-A2 \
  --period 2023-2026 \
  --rules execution_validation/config/validation_rules.yaml
```

Replay bridge:

```bash
python3 scripts/run_replay_execution_validation.py \
  --payload path/to/candle_payload.json \
  --strategy ST-A2 \
  --period 2023-2026 \
  --symbol EURUSD \
  --report-dir execution_validation/reports
```

## Reports

At the end of a validation cycle, the desired operator view is a concise summary
like this:

```text
======================================
Strategy Validation Summary
======================================

Strategy:
ST-A2

Current Stage:
EVF Execution Qualification

Stage Result:
PASS

Rule Audit:
PASS

Historical Replay:
PASS

Backtest:
PASS

Robustness:
PASS

Virtual Execution:
PASS

Execution Validation:
PASS

Lifecycle State:
Execution Qualified

Verification Ready:
YES

Risk Qualified:
YES

Live Demo Authorization:
NO

Live Demo Required:
YES

Production Ready:
NO

Overall Confidence:
92%

Next Gate:
RGM Risk Qualification

Next Action:
Authorize MT5 Live Demo
```

The report and stage artifacts are written under `reports/`.

## Monitoring

Production is not the end of the workflow.

SMO and RGM have different jobs after deployment:

- `SMO` monitors strategy behavior, drift, and revalidation triggers.
- `RGM` monitors capital safety, drawdown integrity, and protection controls.

```text
Production
      │
      ▼
SMO Monitoring
      │
      ▼
Performance Drift Detection
      │
      ├── Revalidation Trigger
      │
      ▼
RGM Risk Monitoring
      │
      ▼
Decision Engine
      │
      ▼
Action
```

Example:

```text
Expected PF: 1.8
Observed PF over last 30 days: 0.9

System:
DRIFT DETECTED

Action:
Suspend
Revalidate
```

## Developer Documentation

More complete operator and developer guidance is documented in:

- `docs/SVOS_EVF_USER_MANUAL.md`
- `docs/SVOS_LIFECYCLE_WORKFLOW.md`
- `docs/ESTIMATED_DEVELOPMENT_ROADMAP.md`

## Repository Structure

### Repository Layers

The current repository already separates these concerns across multiple top-level
packages. The grouping below shows the intended platform view over the existing
layout.

#### Research

- `research/`
- `research_db/`
- `strategy_audit/`

#### Execution

- `execution/`
- `execution_validation/`

#### Risk and Monitoring

- `monitoring/`
- `models/`

#### Governance

- `config/`
- `reports/`
- `dashboard/`

#### Infrastructure

- `scripts/`

```text
session-smc-trading-bot/
├── adaptive/
├── config/
├── core/
├── dashboard/
├── docs/
├── execution/
├── execution_validation/
├── monitoring/
├── pipeline/
├── reports/
├── research/
├── research_db/
├── scripts/
├── src/
├── strategies/
├── strategy/
├── strategy_audit/
└── tests/
```

Practical navigation:

- `research/`: research orchestration, robustness, validation helpers
- `research/svos/`: SVOS orchestration and payload building
- `execution_validation/`: execution validation framework and examples
- `monitoring/`: runtime alerts, monitoring hooks, and operator visibility
- `strategy_audit/`: audit framework and governance logic
- `config/`: strategy catalog and validation configuration
- `scripts/`: operational entrypoints
- `tests/`: regression and validation coverage

## Future Roadmap

A useful way to think about the full target platform is:

```text
                 ISOP

                    │
 ------------------------------------------------
 |                    |             |             |
SVOS                 EVF           RGM        Governance
Research             Execution     Risk       Approval

 |                    |             |             |
Edge Discovery       Reliability   Allocation   Promotion
Validation           Validation    Control      Control

                    │
                   SMO

              Monitoring / Drift /
              Revalidation
```

A long-term architectural goal is a single operating-system-style entrypoint,
for example:

```bash
python3 svos.py validate --strategy ST-A2
```

That controller would:

```text
Load Strategy
      │
      ▼
Determine Current Phase
      │
      ▼
Execute Required Stages
      │
      ▼
Update Registry
      │
      ▼
Generate Reports
      │
      ▼
Evaluate Stage Gates
      │
      ▼
Recommend Next Action
```

This would make the platform feel like a cohesive operating system rather than
a set of related operator scripts.

Near-term priorities:

1. Strengthen the strategy registry, stage gate engine, and decision engine.
2. Formalize the risk governance layer.
3. Expand production monitoring, drift detection, and automated revalidation.
