# ST-A2 Validation Report

Date: 2026-07-11
Status: Review
Owner: Quant Research

## Verdict

**BLOCKED / NOT APPROVED**

ST-A2 does not satisfy the current governance gate. The legacy 2026-06-21 result
recorded `n=169`, `PF_std=1.151`, and `PF_2x=1.025`, but the effective gate from
2026-07-01 requires:

- `n > 200`
- net PF > 1.25 at standard spread
- net PF > 1.25 at 2x spread stress
- Sharpe > 1.2
- MaxDD < 15%

The available ST-A2 evidence is below the current sample-size and profit-factor
requirements and is explicitly deferred in the strategy catalog.

## Current Catalog State

- `status: DEFERRED_REVALIDATION`
- `approved: false`
- `current: false`
- `deployment_target: null`

## Required Remediation

Run ST-A2 as a new governed strategy version from Intake through the full current
SVOS pipeline. No parameter changes may be made mid-trial.
