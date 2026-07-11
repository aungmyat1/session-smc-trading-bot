# ST-A2 Strategy Specification

Date: 2026-07-11
Status: Review
Owner: Quant Research

## Governance Status

This package is **not approved**. The directory name preserves the requested
package location, but this document records the current governance truth:
`config/strategy_catalog.yaml` marks ST-A2 as `DEFERRED_REVALIDATION`,
`approved: false`, and `current: false`.

## Strategy

- Strategy ID: ST-A2
- Name: Session Liquidity Reversal
- Version recorded in catalog: 2.1
- Symbols in catalog: EURUSD, GBPUSD
- Timeframes: M15, H4
- Legacy premise: 4H/H1 bias, session range, liquidity sweep, 15M displacement,
  minimum stop-loss filter, fixed risk/reward management.

## Approval Boundary

Legacy ST-A2 evidence is preserved for research history only. ST-A2 must re-enter
the SVOS lifecycle from Intake and pass the current gates before it can be used
as an approved broker-demo or production strategy.
