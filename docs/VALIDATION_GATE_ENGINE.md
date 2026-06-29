# Validation Gate Engine
# Session Trading Bot
# Date: 2026-06-26

Status: Authoritative
Version: 1.0
Updated: 2026-06-29
Owner: Platform
Authority: Level 5 — Gate Engine Specification
Related: CORE_ARCHITECTURE.md, SVOS_DESIGN_REFERENCE.md

---

## Purpose

The Validation Gate Engine decides whether a strategy may advance to the next
lifecycle stage after replay and backtest processing.

It is a governance layer, not a scheduler.

---

## Inputs

- replay results
- backtest metrics
- previous successful metrics for regression comparison
- current lifecycle stage from the strategy registry

---

## Checks

### Replay Validation

Replay must satisfy:

- completed successfully
- no uncaught exceptions
- no duplicate trade IDs
- no invalid state transitions
- no negative position sizes
- valid stop-loss / take-profit geometry
- required features available
- no missing timestamps

### Backtest Validation

Backtest must satisfy:

- minimum trade count
- positive expectancy
- maximum drawdown within limit
- profit factor within limit
- no NaN metrics
- completed successfully

### Regression Validation

The regression engine compares the latest successful run with the previous
successful run and classifies the result as:

- `PASS`
- `WARNING`
- `FAIL`

Tracked metrics:

- Profit Factor
- Win Rate
- Expectancy
- Max Drawdown
- Trade Count
- Net Return

---

## Outputs

The runner produces:

- Markdown report
- JSON report
- HTML report

It also updates the strategy registry when the overall result is `PASS`.

---

## Current Implementation

Files:

- `research/validation/engine.py`
- `research/regression/engine.py`
- `scripts/run_validation_gate.py`
- `config/validation.yaml`

---

## Promotion Rule

Only `PASS` results are promoted automatically.

`WARNING` and `FAIL` hold the strategy in its current lifecycle stage.

