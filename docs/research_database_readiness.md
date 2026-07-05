# Research Database Readiness

The readiness gate protects System 1 replay and backtesting from incomplete canonical
market data. It does not approve strategies and has no broker or execution access.

## Required dataset

The current required window is 2023-07-01 through 2026-06-30. EURUSD, GBPUSD, and
XAUUSD require one readable, non-empty raw tick Parquet per calendar month under
`data/raw/dukascopy/{SYMBOL}/{YYYY}/{MM}/ticks.parquet` and a canonical M1 candle file
at `data/processed/{SYMBOL}/M1.parquet` covering every month. Raw files are immutable.

A symbol is `READY` only when raw and processed monthly coverage is complete, schemas
match, OHLC geometry is valid, timestamps are sorted, and timestamps are unique.
Missing processed symbol-month coverage is blocking. Acquisition-hour gaps, abnormal
spreads, and intraday gaps are warnings. Sunday UTC bars from 20:00 onward are reported
separately as the normal Forex reopen; other weekend Forex/metal bars are warnings.

Spread warnings use price-unit defaults and can be overridden for research:

```bash
python3 scripts/check_research_db_readiness.py \
  --symbols EURUSD GBPUSD XAUUSD \
  --start 2023-07-01 --end 2026-06-30 \
  --spread-limit XAUUSD=0.8
```

Backtest adapters can use `research_db.readiness.apply_spread_filter`; `None` preserves
all rows, while an explicit price-unit ceiling removes rows above that observed spread.
The selected value is a trial input and must be frozen and recorded before a run.

Machine-readable output is available with `--json`. Canonical replay refuses a
`NOT_READY` database. `--allow-incomplete-data` is an explicit research-only replay
override and does not authorize broker activity.

## Repair

Rebuild EURUSD M1 atomically from immutable raw ticks:

```bash
python3 scripts/build_timeframes.py --symbols EURUSD --timeframes M1 \
  --start 2023-07 --end 2026-06
```

## BTCUSDT

BTCUSDT is registered as a crypto research symbol and remains disabled for execution.
Its calendar is 24/7 with `Asia`, `London`, `NewYork`, `Overlap`, `Weekend`, and `24_7`
labels; Forex closure assumptions do not apply. The same raw schema and M1 builder are
supported at `data/raw/dukascopy/BTCUSDT/...` as a temporary layout convention, but no
source is configured and no BTC data is currently present. Readiness therefore becomes
blocking if BTCUSDT is requested until an owner-approved vendor is selected and the full
requested window is ingested. Fee, funding, tick-size, and slippage models also remain
unset and must be defined before BTC backtests can produce qualifying evidence.

BTCUSD is separately registered for Dukascopy CFD research data. It uses Dukascopy's
`BTCUSD` feed and a quote divisor of 10. It remains excluded from every execution scope.
Its vendor instrument is not interchangeable with exchange BTCUSDT spot or perpetual
data, so evidence and cost models must identify the instrument explicitly.
