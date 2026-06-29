# Historical Replay vs Backtest

Status: Authoritative
Version: 1.0
Updated: 2026-06-29
Owner: Platform
Authority: Level 5 — Phase Specification
Related: STAGE1_AUDIT_SPEC.md, BACKTEST_SPEC.md

Historical replay is a deterministic execution audit.
Backtest is the profitability test.

## What historical replay checks

- Did the bot follow the written rules?
- Did the signal appear on the first candle it could know?
- Did SL / TP and session rules compute correctly?
- Did state update and logging behave as expected?
- Was there any look-ahead bias?

## What historical replay does not check

- Whether the strategy makes money over time
- Profit factor, drawdown, or expectancy as the main outcome
- Which RR variant is best

## Workflow

```text
Historical Replay
    ↓
Verify candle-by-candle logic
    ↓
Fix implementation bugs
    ↓
Backtest
    ↓
Measure profitability
    ↓
Demo / Shadow Trading
    ↓
Live Trading
```

## Available runner

- `scripts/historical_replay.py`

It feeds historical candles sequentially, renders a per-day decision timeline,
and compares the replay signal path to the batch backtest for the same window.

## Notes

- The replay report is intentionally execution-focused, not performance-focused.
- Use the backtest scripts to answer profitability questions.
- For large date ranges, prefer day windows or signal-day reports to keep the audit readable.
