# PHASE 3 — ST-A2 Configuration Audit
Documented: 2026-06-25T11:40:33Z

Source: `strategy/session_liquidity/session_strategy.py` DEFAULT_CONFIG

## Core ST-A2 Parameters

| Parameter | Value | Notes |
|---|---|---|
| rr | 3.0 | Risk:Reward ratio (replay uses 3.0 primary) |
| sl_buffer_pips | 2.0 | SL beyond sweep wick (pips) |
| displacement_mult | 1.2 | Body must be ≥ 1.2× ATR(14) |
| atr_period | 14 | ATR lookback for displacement gate |
| sweep_timeout_bars | 4 | Bars from sweep to displacement |
| min_sl_pips | 5.0 | Minimum SL distance (ST-A2 filter) |

## Session Definition

| Session | Window (UTC) | Range Source |
|---|---|---|
| London killzone | 06:00–09:00 UTC | Asian range: 00:00–06:00 UTC |
| New York killzone | 11:00–14:00 UTC (EDT) | Asian range: same |

## Signal Chain (11 phases)

| Phase | Description |
|---|---|
| 1 | Session definition (London 07-10 UTC / NY 13-16 UTC) |
| 2 | HTF bias: 4H+1H swing (HH+HL bullish / LL+LH bearish, swing_n=3) |
| 3 | Session range build (Asian H/L/Mid as reference) |
| 4 | Session classification (range vs trend) |
| 5 | Liquidity sweep detection (session H/L breach + close back inside) |
| 6–8 | (NOT in ST-A2 fast-entry path — CHoCH/BOS/FVG chain) |
| Disp | 15M displacement candle: body ≥ 1.2×ATR(14) in bias direction |
| Entry | Entry at displacement candle close |
| SL | Sweep wick extreme ± 2pip buffer; min 5pip |
| TP | Entry + risk × RR |
| Mgmt | Session close rule: close remainder at session end |

## Cost Model Applied in Replay

| Cost Item | Value | Source |
|---|---|---|
| EURUSD spread std | 1.4 pip RT | VT Markets Standard (VERDICT_LOG ST-A2) |
| EURUSD spread 2× | 2.8 pip RT | Stress test |

## What Was NOT Changed

- No parameter modifications for this replay
- No lookahead bias (H4 history used as-is; signals generated forward)
- No cherry-picked periods
- No manual trade filtering

## Prior Phase-0 Baseline (VERDICT_LOG ST-A2 entry)

| Metric | Value |
|---|---|
| Period | 2021-06-21 → 2026-06-19 (5yr) |
| n | 169 (EURUSD + GBPUSD combined) |
| PF std | 1.151 |
| PF 2× | 1.025 |
| WR | 32.0% |
| MaxDD | 18.72R |
| Run ID | 20260621T100458-183aaa |