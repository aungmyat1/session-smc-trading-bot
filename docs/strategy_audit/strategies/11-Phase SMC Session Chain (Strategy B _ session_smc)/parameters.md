# Parameters — 11-Phase SMC Session Chain (Strategy B / session_smc)

All parameters found across `session_smc/confirmation_entry.py` (DEFAULT_CONFIG),
`session_smc/liquidity_detector.py`, `session_smc/structure_detector.py`,
`session_smc/poi_detector.py`, `session_smc/swing_detector.py`,
`session_smc/daily_bias.py`, `session_smc/daily_context.py`,
`strategy/session_liquidity/config.yaml`, `scripts/backtest.py`,
`scripts/replay_6m.py`, and `scripts/replay_st_a2_d1.py`.

---

## Primary Config — DEFAULT_CONFIG in confirmation_entry.py

| Parameter | Value | File | Line | Description | Hardcoded | Configurable |
|---|---|---|---|---|---|---|
| `swing_n` | 3 | `confirmation_entry.py` | 61 | Swing confirmation window (bars each side) | No | Yes — pass in config dict |
| `choch_lookback` | 8 | `confirmation_entry.py` | 62 | Bars before sweep used for CHoCH reference level | No | Yes |
| `displacement_atr_mult` | 1.5 | `confirmation_entry.py` | 63 | Displacement candle must have range >= mult * ATR(14) | No | Yes |
| `min_session_range_pips` | 10.0 | `confirmation_entry.py` | 64 | Session range must exceed this to trade | No | Yes |
| `session_range_bars` | 8 | `confirmation_entry.py` | 65 | First N bars used to build session H/L (= 2 hours at 15M) | No | Yes |
| `sweep_start_bar` | 8 | `confirmation_entry.py` | 66 | First bar index from which sweep is checked | No | Yes |
| `min_bars_remaining` | 2 | `confirmation_entry.py` | 67 | Minimum bars left in session after retest to accept signal | No | Yes |
| `sl_range_pct` | 0.25 | `confirmation_entry.py` | 68 | SL = entry ± this fraction of session range | No | Yes |
| `sl_buffer_pips` | 3.0 | `confirmation_entry.py` | 69 | Buffer beyond sweep wick extreme for SL | No | Yes |
| `tp1_r` | 4.0 | `confirmation_entry.py` | 70 | TP1 = entry ± tp1_r * sl_pips * PIP | No | Yes |
| `tp2_r` | 5.0 | `confirmation_entry.py` | 71 | TP2 = entry ± tp2_r * sl_pips * PIP | No | Yes |
| `atr_period` | 14 | `confirmation_entry.py` | 72 | ATR lookback period (Wilder's) | No | Yes |
| `d2_structure_gate` | True | `confirmation_entry.py` | 75 | Gate A: daily structure must agree with 4H+1H bias | No | Yes |
| `d2_location_gate` | True | `confirmation_entry.py` | 78 | Gate B: session open in discount (long) or premium (short) zone | No | Yes |
| `d2_poi_gate` | True | `confirmation_entry.py` | 80 | Gate C: swept level must be within d2_poi_pips of PDL/PDH | No | Yes |
| `d2_poi_pips` | 30.0 | `confirmation_entry.py` | 81 | Gate C proximity threshold in pips | No | Yes |

---

## Module-Level Constants (hardcoded, not in config)

| Parameter | Value | File | Line | Description | Hardcoded | Configurable |
|---|---|---|---|---|---|---|
| `PIP` | 0.0001 | `confirmation_entry.py` | 33 | 1 pip for 5-digit EURUSD/GBPUSD | Yes — MAGIC NUMBER | No — requires code change for JPY/other pairs |
| `PIP` | 0.0001 | `liquidity_detector.py` | 14 | Same constant duplicated | Yes — DUPLICATE MAGIC NUMBER | No |
| `PIP` | 0.0001 | `daily_context.py` | 43 | Same constant duplicated again | Yes — DUPLICATE MAGIC NUMBER | No |
| `_UTC` | `timezone.utc` | `daily_bias.py` | 23 | UTC timezone sentinel | Yes | No |
| `_UTC` | `timezone.utc` | `daily_context.py` | 44 | Same constant duplicated | Yes — DUPLICATE | No |

---

## Swing Detector Defaults

| Parameter | Value | File | Line | Description | Hardcoded | Configurable |
|---|---|---|---|---|---|---|
| `n` (swing_highs/lows) | 3 | `swing_detector.py` | 26, 42 | Default swing confirmation window | No — function default | Yes — pass n argument |
| Strict inequality | (hardcoded in loop) | `swing_detector.py` | 34–35, 48–49 | `all(highs[i-j] < h ...)` — strictly less than, no equal | Yes — logic choice | No without code change |

---

## Structure Detector Defaults

| Parameter | Value | File | Line | Description | Hardcoded | Configurable |
|---|---|---|---|---|---|---|
| `period` (ATR) | 14 | `structure_detector.py` | 42 | Default ATR period | No — function default | Yes |
| ATR seed method | Simple mean of TR[1..period] | `structure_detector.py` | 68 | Wilder's seed; index 0 uses high-low only (no prior close) | Yes — design choice | No |
| `lookback` (CHoCH) | 8 | `structure_detector.py` | 83 | Default CHoCH lookback | No — function default | Yes |
| `atr_mult` (displacement) | 1.5 | `structure_detector.py` | 158 | Default displacement ATR multiplier | No — function default | Yes |

---

## Liquidity Detector Defaults

| Parameter | Value | File | Line | Description | Hardcoded | Configurable |
|---|---|---|---|---|---|---|
| `range_bars` | 8 | `liquidity_detector.py` | 22 | Default session range bars | No | Yes |
| `min_range_pips` | 10.0 | `liquidity_detector.py` | 23 | Default minimum session range | No | Yes |
| `atr_period` | 14 | `liquidity_detector.py` | 57 | Default ATR period for session classification | No | Yes |
| RANGE ratio threshold | 0.5 | `liquidity_detector.py` | 68 | Session range / ATR < 0.5 → RANGE | Yes — MAGIC NUMBER | No without code change |
| TREND ratio threshold | 0.7 | `liquidity_detector.py` | 70 | Session range / ATR > 0.7 → TREND | Yes — MAGIC NUMBER | No without code change |

---

## Daily Bias (daily_bias.py) Defaults

| Parameter | Value | File | Line | Description | Hardcoded | Configurable |
|---|---|---|---|---|---|---|
| `swing_n` | 3 | `daily_bias.py` | 65 | Swing confirmation for daily structure | No — function default | Yes |
| Minimum closed days | 2 | `daily_bias.py` | 95 | Minimum required closed daily bars | Yes — MAGIC NUMBER | No |

---

## Daily Context (daily_context.py) Defaults

| Parameter | Value | File | Line | Description | Hardcoded | Configurable |
|---|---|---|---|---|---|---|
| `swing_n` | 3 | `daily_context.py` | 82 | Swing confirmation for D1 structure | No — function default | Yes |
| `lookback_swings` | 3 | `daily_context.py` | 83 | Recent swing levels to retain in liquidity dict | No — function default | Yes |
| `d1_poi_filter` default | False | `daily_context.py` | 224 | Gate C is STUB — off by default | No | Yes, but triggers assertion if enabled |
| `d1_poi_pips` | 30.0 | `daily_context.py` | 202 | Gate C proximity threshold (stub/future) | No — config key | Yes |
| `d1_bias_filter` default | True | `daily_context.py` | 208 | Gate A default | No | Yes |
| `d1_location_filter` default | True | `daily_context.py` | 214 | Gate B default | No | Yes |

---

## Backtest Runner Parameters (scripts/backtest.py)

| Parameter | Value | File | Line | Description | Hardcoded | Configurable |
|---|---|---|---|---|---|---|
| `SESSION_BARS` | 20 | `backtest.py` | 52 | Max bars per session window | Yes — MAGIC NUMBER | CLI override not available |
| `EURUSD standard cost` | 1.4 pip | `backtest.py` | 34 | Spread + commission RT | Yes — MAGIC NUMBER | No without code change |
| `GBPUSD standard cost` | 1.8 pip | `backtest.py` | 35 | Spread + commission RT | Yes — MAGIC NUMBER | No without code change |
| `EURUSD stress cost` | 2.8 pip | `backtest.py` | 34 | 2× spread stress | Yes — MAGIC NUMBER | No without code change |
| `GBPUSD stress cost` | 3.6 pip | `backtest.py` | 35 | 2× spread stress | Yes — MAGIC NUMBER | No without code change |
| H4 slice count | 200 | `backtest.py` | 172 | Max H4 bars passed to signal chain | Yes — MAGIC NUMBER | No |
| H1 slice count | 200 | `backtest.py` | 176 | Max H1 bars passed (or 200 M15 proxy bars) | Yes — MAGIC NUMBER | No |
| Phase-0 gate n | 50 | `backtest.py` | 365 | Minimum trade count for PASS | Yes — MAGIC NUMBER | No |
| Phase-0 gate PF | 1.0 | `backtest.py` | 365 | Minimum PF at both spread levels | Yes — MAGIC NUMBER | No |

---

## ST-A2 Execution Config (strategy/session_liquidity/config.yaml)

Different from the session_smc chain. Listed here for cross-reference.

| Parameter | Value | File | Description | Hardcoded | Configurable |
|---|---|---|---|---|---|
| `rr` | 3.0 | `config.yaml:1` | Reward/risk ratio (ST-A2 uses 3R, not 4R) | No | Yes |
| `sl_buffer_pips` | 2.0 | `config.yaml:2` | SL buffer beyond sweep wick (ST-A2: 2pip vs ST-B: 3pip) | No | Yes |
| `displacement_mult` | 1.2 | `config.yaml:3` | Displacement ATR multiplier (ST-A2: 1.2 vs ST-B: 1.5) | No | Yes |
| `atr_period` | 14 | `config.yaml:4` | ATR lookback | No | Yes |
| `sweep_timeout_bars` | 4 | `config.yaml:5` | Bars after sweep before pending is cancelled | No | Yes |
| `min_sl_pips` | 5.0 | `config.yaml:6` | Minimum SL distance (ABSENT from session_smc DEFAULT_CONFIG) | No | Yes |
| `min_range_pips.EURUSD` | 15.0 | `config.yaml:8` | Per-pair range floor (vs 10.0 in session_smc) | No | Yes |
| `min_range_pips.GBPUSD` | 20.0 | `config.yaml:9` | Per-pair range floor | No | Yes |

---

## Parameter Conflicts and Duplicates

| Conflict | session_smc value | ST-A2 value | Impact |
|---|---|---|---|
| `sl_buffer_pips` | 3.0 (DEFAULT_CONFIG) | 2.0 (config.yaml) | Different SL placement; session_smc has wider buffer |
| `displacement_atr_mult` | 1.5 (DEFAULT_CONFIG) | 1.2 (config.yaml) | session_smc requires larger displacement candles |
| `tp1_r` | 4.0 (DEFAULT_CONFIG) | 3.0 (config.yaml rr) | Different reward targets |
| `min_session_range_pips` | 10.0 (DEFAULT_CONFIG) | 15.0/20.0 (config.yaml per pair) | session_smc accepts narrower ranges |
| `min_sl_pips` | ABSENT from DEFAULT_CONFIG | 5.0 (config.yaml) | session_smc module will emit signals with SL < 5 pip |
| `PIP` constant | Defined in 3 separate files | — | Maintenance risk; change in one file not propagated |
| `_UTC` sentinel | Defined in daily_bias.py and daily_context.py | — | Duplication |

---

## Notes on Magic Numbers

The following literals appear in code without named constants or config keys. Each poses a
maintenance risk if session hours or pair-specific values change:

- `0.0001` (PIP): three files; no abstraction for different pip-size instruments.
- `0.5` / `0.7` (session classification thresholds, `liquidity_detector.py:68,70`): no config key.
- `2` (minimum closed daily bars, `daily_bias.py:95`): no config key.
- `20` (SESSION_BARS in backtest, `backtest.py:52`): hardcoded session window.
- Cost model numbers (1.4, 1.8, 2.8, 3.6) in backtest runners: no YAML source.
- `200` (H4/H1 slice count in backtest): no config key.
