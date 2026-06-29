# Current Scope

Date: 2026-06-28

> **Superseded 2026-06-29.** This document records the former narrow
> Vantage-first scope. The governing product plan is
> `docs/svos/STRATEGY_ENGINEERING_PLATFORM_IMPLEMENTATION_PLAN.md`; the active
> stabilization sequence is
> `docs/svos/architecture-review-2026-06-29/06_UPGRADE_ROADMAP.md`.
> No broker or feature work resumes until stabilization Phases 0-2 pass.

This document defines the current development scope for the repository.

## Current Goal

The current goal is not to expand the project into a larger institutional
platform.

The current goal is to finish and operate:

- the SVOS-following research and validation workflow
- a simple trading bot
- Vantage demo execution
- Vantage live execution after the required gates pass

## In Scope Now

- maintain a simple strategy audit -> replay -> backtest -> robustness ->
  execution path
- keep the research and validation flow objective and machine-checkable
- complete spread capture and cost revalidation
- complete the execution gate for demo readiness
- run the current approved strategy safely on Vantage demo
- promote to controlled Vantage live trading only after the gates pass
- keep the runtime bot simple, stable, and observable

## Out Of Scope For Now

These may exist in the repo, but they are not the current build priority:

- expanding the repo into a broader multi-strategy platform
- building full EVF, RGM, Governance, and SMO separation
- growing the dashboard into a full control plane
- broad architecture expansion not required for the current trading path
- unrelated research branches that do not help the Vantage demo/live path

## Practical Interpretation

For current decisions, prefer:

- simple over comprehensive
- direct execution readiness over architecture expansion
- SVOS-following strategy validation over ad hoc experimentation
- demo/live bot reliability over new framework work

## Priority Order

1. Finish `E5`
2. Run `E6`
3. Complete `E1-E4`
4. Run Vantage demo safely
5. Promote to controlled Vantage live only if the gates pass

## Branch Meaning

The `main` branch should represent this current scoped objective:

`SVOS-following validation workflow + simple Vantage demo/live trading bot`

It should not be treated as a mandate to expand the repository further unless
the project owner explicitly changes scope.
