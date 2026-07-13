---
Date: 2026-07-02
Status: Authoritative
Version: 1.2
Updated: 2026-07-12
Owner: Lead Architect
Authority: Level 1 — Product Architecture Truth
Supersedes: Conflicting descriptions of SVOS and Production scope
Related: DOC_AUTHORITY.md, ../SYSTEM_ARCHITECTURE.md, ../architecture/target_architecture.md
---

# Two-System Architecture — Original Truth

This document records the original architectural truth supplied by the project
owner. Every implementation plan, migration, dashboard, deployment workflow,
and future architecture document must preserve this separation.

## Current Single Source of Truth — 2026-07-12

This document is the highest project authority for the split between System 1
and System 2, the readiness order, and the strategy handoff contract.

Current project truth:

1. **System 2 is implemented first to readiness, not to trading.** It may be
   hardened through controlled disabled rehearsals, package loading tests,
   shadow-only signal paths, broker read-only/demo telemetry, recovery drills,
   journaling, dashboard status, and rollback evidence.
2. **System 2 does not need an approved strategy to become package-ready.** It
   may use signed synthetic or fixture packages to prove that the execution
   machine can safely import, verify, stage, observe, and refuse activation.
   Those fixtures are never approval evidence.
3. **System 2 must not paper trade, demo trade, or live trade any strategy
   without a valid SVOS-approved package and the separate execution gate.**
4. **System 1/SVOS is the only place where strategies are searched, created,
   optimized, validated, failed, frozen, or approved.**
5. **No strategy currently has Production Approval.** Failed, blocked, deferred
   or synthetic-only strategy work, including ST-B1's Dukascopy-403 blocked
   validation and ST-A2 legacy/deferred evidence, remains research history only.
6. **`LIVE_TRADING=false` and `DEMO_ONLY=true` remain mandatory platform
   invariants.** Changing them is outside normal implementation work and
   requires the explicit owner authorization defined by repository policy.

`SYSTEM2_MASTER_PLAN.md` is the current implementation plan for making System 2
package-ready under these constraints. It is subordinate to this document.

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

## How an Approved Strategy Is Created

Approved strategies are created only through SVOS. The execution engine cannot
search for, tune, or approve a strategy.

The strategy creation/search loop is:

1. Define a candidate strategy with explicit symbols, sessions, timeframes,
   signal rules, stop logic, take-profit logic, risk model, and trade limits.
2. Pre-register the trial in `docs/VERDICT_LOG.md` before running validation.
   Every parameter change creates a new trial ID; no mid-trial tuning.
3. Run SVOS intake and audit. Ambiguous, contradictory, or lookahead-prone specs
   must return FIX or FAIL before replay.
4. Run historical replay with chronological candle access only.
5. Run statistical validation net of spread and commission.
6. Run robustness validation, including walk-forward validation and 2x spread
   stress.
7. Run offline virtual demo through the intended order, risk, and position
   interfaces without broker writes.
8. Freeze and package the strategy only if all gates pass.

The current statistical gate is:

```text
trades > 200
net Profit Factor > 1.25 at standard spread
net Profit Factor > 1.25 at 2x spread stress
Sharpe > 1.20
Max Drawdown < 15%
```

Walk-forward validation uses 24-month training and 6-month testing windows, with
four or more rolling windows when enough history exists. Parameter sets that
materially degrade out of sample are rejected.

If a candidate fails, SVOS produces a failure analysis report and keeps the
strategy contained. A failed candidate must not be promoted, frozen, imported as
an approved package, or used to justify System 2 paper/demo execution.

## Non-Negotiable Rules

1. SVOS is the sole strategy research and validation authority.
2. Production is a simple execution machine.
3. Production executes only approved strategy packages.
4. Research code never becomes a Production runtime dependency.
5. Production does not independently approve or modify strategy logic.
6. Any implementation that broadens Production beyond the stated execution
   chain requires an explicit amendment by the project owner.
