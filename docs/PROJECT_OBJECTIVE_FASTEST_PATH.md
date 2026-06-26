# Project Objective And Fastest Path To Live Trading

## Objective

Deploy ST-A2 (Session Liquidity Sweep Reversal) as a live automated forex
trading bot on EURUSD and GBPUSD via Vantage MT5, generating consistent
risk-adjusted returns at 0.25% to 1.0% risk per trade with automated circuit
breakers, Telegram alerts, and a two-VPS architecture separating execution from
research.

Current phase: Phase-1 demo validation. ST-A2 has passed Phase-0 backtest
(`n=169`, `PF_2x=1.025`). Code is deployed. Awaiting spread capture to unlock
execution.

## Fastest Path

### 1. Gate E5: Spread Capture

- VPS: 1
- Target: measure real Vantage MT5 spreads during London and New York killzones
- Pass condition: at least 5 London sessions and 5 New York sessions captured
- Output: `research/spread_samples.csv`

### 2. Gate E6: Cost Revalidation

- VPS: 2
- Target: update the measured cost profile and rerun the Phase-0 backtest
- Pass condition: `PF_2x >= 1.00` at real costs

### 3. Gates E1 to E4: 7-Day Demo Run

- VPS: 1
- Target: validate execution, logging, restart behavior, and signal lifecycle
- Pass condition: 7 days, 0 crashes, signal and order lifecycle verified

### 4. Micro-Live

- Owner decision only
- Parameters in the source text:
  - $1,000 Vantage live account
  - 0.25% risk per trade
  - 1 max open position
  - 3R daily loss limit
  - 10% account drawdown kill switch

## VPS Split

- VPS 1: execution, demo/live bot, spread capture
- VPS 2: backtesting, holdout evaluation, research queue, validation gate

## Notes

- Historical replay validates execution logic and signal timing.
- Backtest validates profitability and cost sensitivity.
- Live trading remains owner-controlled.

