# ST-A2 Approval Record

Date: 2026-07-11
Status: Review
Owner: Platform Governance

## Decision

**DENIED / BLOCKED**

ST-A2 is not approved for automated trading deployment.

## Basis

- `config/strategy_catalog.yaml` marks ST-A2 as `DEFERRED_REVALIDATION`.
- `approved` is `false`.
- `current` is `false`.
- `deployment_target` is `null`.
- Legacy ST-A2 evidence does not satisfy the current 2026-07-01 gate.

## Operational Consequence

Startup must fail for ST-A2 in broker-connected demo or validation modes until
the catalog records a valid governed approval.

## Required Approval Path

ST-A2 must re-enter SVOS at Intake and pass the current replay, statistical
validation, robustness, and virtual-demo gates with qualifying current evidence.
