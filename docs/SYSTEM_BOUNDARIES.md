# System Boundaries

## System 1 — Strategy Engineering Platform

Owns strategy intake, backtesting, historical replay, risk and performance validation, evidence reports, and approval-package creation. This is the only system allowed to validate or approve a strategy.

## System 2 — Trading Bot

Owns package verification, broker/demo connectivity, risk enforcement, order execution or simulation, reconciliation, recovery, and activity reporting.

The bot must not invent, optimize, backtest, validate, or approve strategies. Startup is fail-closed: a missing, incomplete, failed, expired, or incorrectly signed package is rejected before broker or notification connections are opened.

No component in this milestone enables live trading or weakens the existing risk firewall.
