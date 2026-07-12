# ST-B1 Validation Report

Generated: 2026-07-12T15:31:15.291787+00:00
Run ID: `ST-B1-20260712T153115-49638d`
Data source: `parquet`
Symbols: `EURUSD, GBPUSD`

## Verdict: FAIL

| Metric | Standard cost | 2x stress | Gate |
|---|---:|---:|---:|
| Trades | 2319 | 2319 | >= 200 |
| Profit Factor | 0.834 | 0.675 | > 1.25 |
| Sharpe | -0.088 | -0.196 | > 1.20 |
| Win Rate | 34.5% | 34.4% | - |
| Expectancy (R) | -0.125 | -0.277 | - |
| Max Drawdown | 76.31% | 164.36% | < 15% |

## Walk-Forward

- Windows completed: 6
- Windows passed: 0
- Training/testing: 24 months / 6 months, rolling monthly.

| Test Window | Trades | PF Std | Sharpe Std | MaxDD Std | Passed |
|---|---:|---:|---:|---:|---|
| 2025-07-01 to 2026-01-01 | 384 | 0.832 | -0.090 | 13.63% | false |
| 2025-08-01 to 2026-02-01 | 392 | 0.753 | -0.139 | 20.09% | false |
| 2025-09-01 to 2026-03-01 | 387 | 0.731 | -0.153 | 21.24% | false |
| 2025-10-01 to 2026-04-01 | 393 | 0.728 | -0.155 | 23.69% | false |
| 2025-11-01 to 2026-05-01 | 393 | 0.708 | -0.169 | 24.56% | false |
| 2025-12-01 to 2026-06-01 | 378 | 0.697 | -0.177 | 24.94% | false |

## Symbol Breakdown

| Symbol | Trades | PF Std | Sharpe Std | MaxDD Std | Expectancy | Win Rate |
|---|---:|---:|---:|---:|---:|---:|
| EURUSD | 1155 | 0.846 | -0.081 | 36.67% | -0.115R | 34.6% |
| GBPUSD | 1164 | 0.823 | -0.095 | 42.20% | -0.134R | 34.3% |

## Failure Analysis

ST-B1 remains contained. No demo deployment or freeze was performed.
- Profit Factor does not clear the standard and 2x stress gate.
- Sharpe does not clear the standard and 2x stress gate.
- Max drawdown breaches the gate.
