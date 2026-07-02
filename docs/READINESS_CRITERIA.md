# Readiness Criteria

## Approval gate

An executable package must contain the strategy specification, backtest, replay and risk reports, a passing validation summary, approval status and expiry, and a valid signature covering every document.

## Replay gate

Replays use a fixed pair and time window, reject duplicate candle timestamps, expose only current and past candles to strategy code, label London/New York sessions, and derive the run ID from inputs and outputs. Identical inputs must produce identical reports.

## Performance gate

Approval evidence must show net profit factor above 1.25, Sharpe above 1.2, acceptable drawdown and trade count, and passing walk-forward, Monte Carlo and regime checks. The package builder additionally requires explicit `validation=PASS` and `risk_check=PASS` fields.

## Demo gate

All ten checks must pass: approved package, broker connection, market data, dry-run order, risk firewall, mandatory stop loss, maximum daily loss, dashboard, Telegram, and restart recovery. A two-week run is the minimum observation window; four weeks is recommended. Live readiness remains blocked until that evidence exists.
