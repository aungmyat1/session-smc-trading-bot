# Readiness Criteria

## Approval gate

An executable package must contain the strategy specification, backtest, replay and risk reports, a passing validation summary, approval status and expiry, and a valid signature covering every document.

## Replay gate

Replays use a fixed symbol and time window, reject duplicate candle timestamps, expose only current and past candles to strategy code, and derive the run ID from inputs and outputs. Forex/metals use their configured London/New York session model; BTCUSDT uses Crypto 24/7 or explicit UTC windows. Identical inputs must produce identical reports.

## Performance gate

Approval evidence must show net profit factor above 1.25, Sharpe above 1.2, acceptable drawdown and trade count, and passing walk-forward, Monte Carlo and regime checks. The package builder additionally requires explicit `validation=PASS` and `risk_check=PASS` fields.

## Demo gate

All ten checks must pass: approved package, broker connection, market data, dry-run order, risk firewall, mandatory stop loss, maximum daily loss, dashboard, Telegram, and restart recovery. A two-week run is the minimum observation window; four weeks is recommended. Live readiness remains blocked until that evidence exists.

## BTCUSDT research gate

BTCUSDT qualification must record data source, spot/perpetual market type, exchange type, tick size and price precision, fee model, basis-point slippage model, 24/7 trading-hours model, volatility calibration, and funding treatment. A missing assumption produces a validation warning and blocks any claim of full qualification. BTCUSDT remains excluded from execution and live readiness.
