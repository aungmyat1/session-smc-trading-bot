# ST-B1 Failure Analysis

Run ID: `ST-B1-20260712T153115-49638d`

ST-B1 failed historical validation on the available EURUSD and GBPUSD parquet history from 2023-07-02 to 2026-06-26.

## Gate Result

| Metric | Standard cost | 2x stress | Gate |
|---|---:|---:|---:|
| Trades | 2319 | 2319 | >= 200 |
| Profit Factor | 0.834 | 0.675 | > 1.25 |
| Sharpe | -0.088 | -0.196 | > 1.20 |
| Max Drawdown | 76.31% | 164.36% | < 15% |

## Diagnosis

- The strategy has enough sample size, so this is not a low-n blocker.
- The edge is negative on both EURUSD and GBPUSD after costs.
- Cost stress worsens an already failing baseline, which confirms the signal is not robust enough for demo deployment.
- All six 24-month/6-month rolling walk-forward windows failed.

## Decision

Stop optimization for `ST-B1_v1`. Keep ST-B1 contained as research-only. Do not freeze as `ST-B1_v1_FROZEN` and do not deploy to demo.
