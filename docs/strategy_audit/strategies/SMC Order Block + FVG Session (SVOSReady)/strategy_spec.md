# SMC Order Block + FVG Session (SVOSReady)

- **Strategy ID:** `SMCOrderBlockFVGSession`
- **Adapter:** `strategies/adapters/smc_ob_fvg_session_adapter.py`
- **Lifecycle status:** `INTAKE`
- **Primary sessions:** London kill zone `07:00-11:00 UTC`, New York kill zone `12:00-16:00 UTC`
- **Recommended timeframes:** `M5`, `M15`; `M30` optional
- **Target instruments:** major FX pairs and gold

## Overview

This strategy is an intraday Smart Money Concepts setup that looks for price to
break structure with displacement, leave behind an order block and fair value
gap, then retrace into that confluence during the London or New York kill zone.
The default implementation is configured for a fixed minimum `1:3` reward:risk
profile with strict stop placement beyond the order-block boundary plus a pip
buffer.

## Entry Model

1. Build context from M15 candles with UTC timestamps.
2. Reject bars outside the London and New York kill zones.
3. Detect a recent bullish or bearish break of structure from recent price
   action.
4. Identify the last opposite candle before that break as the candidate order
   block.
5. Detect a same-direction fair value gap formed after the break.
6. Require the latest price to retrace into the order-block / FVG zone.
7. Require ATR-based displacement on the BOS candle.
8. Emit a market-order signal with fixed-`RR` targeting.

## Risk Model

- **Default risk per trade:** `1.0%`
- **Default RR target:** `3.0`
- **Stop loss:** order-block boundary plus `5` pip buffer
- **Daily trade cap:** `2`
- **Equity bagging flag:** enabled in metadata for downstream execution controls
- **Daily loss / news filters:** expected to be enforced by the execution and
  governance layers, not by the adapter alone

## Parameters

| Parameter | Default | Purpose |
|---|---:|---|
| `risk_per_trade` | `0.01` | Fraction of account equity risked per trade |
| `rr_ratio` | `3.0` | Fixed reward:risk multiple |
| `atr_period` | `14` | ATR lookback for displacement and stop geometry |
| `ob_lookback` | `50` | Maximum bar span used to search for recent setup context |
| `bos_lookback` | `20` | Rolling range used for BOS detection |
| `signal_lookback_bars` | `12` | Reserved short-term validity horizon for setup proximity |
| `fvg_threshold` | `0.0` | Minimum gap size |
| `min_atr_displacement` | `1.0` | BOS candle body must exceed ATR multiple |
| `stop_buffer_pips` | `5.0` | Extra stop padding beyond zone edge |
| `max_spread_pips` | `3.0` | Optional spread filter when spread data is supplied |
| `london_start` / `london_end` | `07:00` / `11:00` | UTC session gate |
| `ny_start` / `ny_end` | `12:00` / `16:00` | UTC session gate |
| `max_daily_trades` | `2` | Metadata for execution guardrails |
| `use_equity_bagging` | `true` | Metadata for downstream daily stop logic |

## Data Dependencies

- OHLCV candles on `M15` minimum
- Optional spread input via `data["spread_pips"]`
- No direct news feed dependency in the adapter

## Current Implementation Notes

- The intake implementation is self-contained and reuses repository feature
  components from `src.features.fvg` and `src.features.order_blocks`.
- BOS is implemented as a recent rolling-range break proxy suitable for intake
  and demo wiring; it is not yet a fully audited institutional CHOCH/BOS engine.
- Trade journaling, lifecycle evidence, and deployment gating remain handled by
  the surrounding SVOS and execution layers.
