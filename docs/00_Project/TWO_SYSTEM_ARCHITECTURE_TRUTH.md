---
Date: 2026-07-02
Status: Authoritative
Version: 1.1
Updated: 2026-07-03
Owner: Lead Architect
Authority: Level 1 — Product Architecture Truth
Supersedes: Conflicting descriptions of SVOS and Production scope
Related: DOC_AUTHORITY.md, ../SYSTEM_ARCHITECTURE.md, ../architecture/target_architecture.md
---

# Two-System Architecture — Original Truth

This document records the original architectural truth supplied by the project
owner. Every implementation plan, migration, dashboard, deployment workflow,
and future architecture document must preserve this separation.

## Delivery Priority — System 2 First

The owner-directed implementation order is:

1. finish and stabilize **System 2** through controlled demo/paper readiness;
2. resume and complete **System 1** strategy development, replay, backtest,
   optimization, robustness, and approval capabilities;
3. allow System 1 to hand an approved, signed package to System 2 for execution.

System 2 stabilization may use signed synthetic fixtures and paper/demo adapters
to prove package loading, runtime ownership, execution ordering, risk, journaling,
dashboard status, and recovery. It must not absorb System 1 replay, backtest,
optimization, or approval logic. System 1 work continues after the System 2
demo-readiness acceptance gate is stable.

This priority does not authorize real-capital trading. Live trading remains
disabled until all qualification and execution gates pass and the owner provides
the explicit authorization required by repository policy.

## System 1 — SVOS

SVOS means **Strategy Research and Validating System**.

SVOS owns the complete strategy qualification lifecycle:

```text
Strategy Idea
    │
    ▼
Strategy Audit
    │
    ▼
Historical Replay
    │
    ▼
Backtest
    │
    ▼
Statistical Validation
    │
    ▼
Robustness Testing
    │
    ▼
Virtual Demo Trading
    │
    ▼
Production Approval
```

SVOS researches, tests, validates, and approves strategies. It must not place
live broker orders. Its final output is an approved, versioned strategy package
for System 2.

`Backtest` and `Statistical Validation` are distinct lifecycle responsibilities.
They must not be silently collapsed in architecture descriptions, even where a
transitional implementation currently combines their code or state.

## System 2 — Production Execution Engine

System 2 is the execution engine: a **simple trading bot** and clean execution
machine.

Its complete responsibility chain is:

```text
Trading Engine
    │
    ▼
Strategy Package Loader
    │
    ▼
Risk Manager
    │
    ▼
Execution Manager
    │
    ▼
Broker API
    │
    ▼
Position Management
```

Production must contain only the functionality required to load an approved
strategy package, evaluate it in the trading engine, enforce risk, execute via
the broker, and manage resulting positions.

Production must not contain research, replay, backtesting, statistical
validation, robustness testing, optimization, AI strategy editing, or strategy
approval workflows. Monitoring and operational controls may observe and protect
the execution chain, but must not turn Production into a second research system.

## Handoff Contract

The only strategy handoff between the systems is an approved, versioned,
verifiable strategy package:

```text
SVOS Production Approval
          │
          ▼
Approved Strategy Package
          │
          ▼
Production Strategy Package Loader
```

Production consumes the package. It does not import SVOS research internals or
reproduce SVOS validation work.

## Non-Negotiable Rules

1. SVOS is the sole strategy research and validation authority.
2. Production is a simple execution machine.
3. Production executes only approved strategy packages.
4. Research code never becomes a Production runtime dependency.
5. Production does not independently approve or modify strategy logic.
6. Any implementation that broadens Production beyond the stated execution
   chain requires an explicit amendment by the project owner.
