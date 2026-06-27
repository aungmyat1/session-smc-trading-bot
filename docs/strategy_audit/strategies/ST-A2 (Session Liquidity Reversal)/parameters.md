# Parameters: ST-A2 (Session Liquidity Reversal)

## Parameter Table

| Parameter | Value | File | Line | Description | Hardcoded | Configurable |
|---|---|---|---|---|---|---|
| rr | 3.0 | strategy/session_liquidity/config.yaml | 1 | Risk-reward ratio for TP calculation: TP = entry ± risk × rr | No | Yes |
| rr | 3.0 | strategy/session_liquidity/session_strategy.py (DEFAULT_CONFIG) | 27 | Same param; YAML value takes precedence only if explicitly loaded; DEFAULT_CONFIG is the runtime default | No | Yes |
| sl_buffer_pips | 2.0 | strategy/session_liquidity/config.yaml | 2 | Buffer added beyond sweep wick for SL placement (in pips, × 0.0001) | No | Yes |
| sl_buffer_pips | 2.0 | strategy/session_liquidity/session_strategy.py (DEFAULT_CONFIG) | 28 | Duplicate of YAML value | No | Yes |
| displacement_mult | 1.2 | strategy/session_liquidity/config.yaml | 3 | ATR multiplier for displacement body gate: body > mult × ATR(14) | No | Yes |
| displacement_mult | 1.2 | strategy/session_liquidity/session_strategy.py (DEFAULT_CONFIG) | 29 | Duplicate of YAML value | No | Yes |
| atr_period | 14 | strategy/session_liquidity/config.yaml | 4 | Wilder ATR lookback period (standard ATR(14) for M15) | No | Yes |
| atr_period | 14 | strategy/session_liquidity/session_strategy.py (DEFAULT_CONFIG) | 30 | Duplicate of YAML value | No | Yes |
| sweep_timeout_bars | 4 | strategy/session_liquidity/config.yaml | 5 | Maximum killzone bars after sweep to find displacement before cancelling | No | Yes |
| sweep_timeout_bars | 4 | strategy/session_liquidity/session_strategy.py (DEFAULT_CONFIG) | 31 | Duplicate of YAML value | No | Yes |
| min_sl_pips | 5.0 | strategy/session_liquidity/config.yaml | 6 | ST-A2 defining gate: minimum sweep wick size in pips; signals below this are rejected | No | Yes |
| min_sl_pips | 5.0 | strategy/session_liquidity/session_strategy.py (DEFAULT_CONFIG) | 32 | Duplicate of YAML value | No | Yes |
| min_range_pips.EURUSD | 15.0 | strategy/session_liquidity/config.yaml | 9 | Minimum Asian range in pips for EURUSD; days below threshold are skipped | No | Yes |
| min_range_pips.EURUSD | 15.0 | strategy/session_liquidity/session_strategy.py (DEFAULT_CONFIG) | 34 | Duplicate of YAML value | No | Yes |
| min_range_pips.GBPUSD | 20.0 | strategy/session_liquidity/config.yaml | 10 | Minimum Asian range in pips for GBPUSD | No | Yes |
| min_range_pips.GBPUSD | 20.0 | strategy/session_liquidity/session_strategy.py (DEFAULT_CONFIG) | 35 | Duplicate of YAML value | No | Yes |
| swing_n (bias) | 2 | strategy/session_liquidity/bias_filter.py | 78 | Default number of bars each side required for a swing pivot in 4H bias filter | No | Yes (htf_bias arg) |
| _PIP | 0.0001 | strategy/session_liquidity/entry_engine.py | 20 | Pip size constant: 1 pip = 0.0001 (5-decimal EURUSD/GBPUSD). MAGIC NUMBER — no comment in code. | Yes | No |
| _VALID_SESSIONS | frozenset({'london','new_york'}) | strategy/session_liquidity/entry_engine.py | 21 | Hardcoded valid session names; must match output of classify_session() | Yes | No |
| close_position threshold (long) | 0.75 | strategy/session_liquidity/displacement_detector.py | 179 | Quartile gate for bullish displacement: close must be in upper 25% of candle range | Yes | No |
| close_position threshold (short) | 0.25 | strategy/session_liquidity/displacement_detector.py | 191 | Quartile gate for bearish displacement: close must be in lower 25% of candle range | Yes | No |
| Asian min bars | 4 | strategy/session_liquidity/session_builder.py | 79 | Minimum Asian bars required to build a valid range; fewer = skip day | Yes | No |
| Asian window (EST prev day) | hour >= 18 | strategy/session_liquidity/session_builder.py | 73 | Asian session start on prior EST day (18:00 EST) | Yes | No |
| Asian window (EST curr day) | hour < 2 | strategy/session_liquidity/session_builder.py | 74 | Asian session end on current EST day (02:00 EST = London open, excluded) | Yes | No |
| London killzone | 2 <= h < 5 (EST) | strategy/session_liquidity/session_builder.py | 97 | London killzone hours in EST: 02:00–04:59 | Yes | No |
| New York killzone | 7 <= h < 10 (EST) | strategy/session_liquidity/session_builder.py | 99 | New York killzone hours in EST: 07:00–09:59 | Yes | No |
| 4H bar close offset | timedelta(hours=4) | strategy/session_liquidity/bias_filter.py | 100 | Used to compute close time of 4H bars: close = open + 4h (lookahead prevention) | Yes | No |
| min 4H bars for swing | 2 * swing_n + 1 | strategy/session_liquidity/bias_filter.py | 104 | Minimum bars needed to find any swing pivot with n bars each side | Yes (formula) | Implicit |
| risk_percent | 0.25 | strategies/adapters/st_a2_adapter.py | 69 | Risk percentage passed in core.Signal from adapter. MAGIC NUMBER — 0.25% not documented; different from 1% in RISK_SPEC.md. | Yes | No |
| confidence | 1.0 | strategies/adapters/st_a2_adapter.py | 70 | Fixed confidence value; always 1.0 | Yes | No |
| ttl_seconds | 300 | core/signal.py | 29 | Signal expiry in seconds (5 minutes); set by Signal dataclass default | Yes (default) | Configurable field |
| m15 minimum length | 50 | strategies/adapters/st_a2_adapter.py | 50 | Minimum number of M15 candles required before calling run_strategy | Yes | No |

---

## Notes on Duplicates

The config.yaml and DEFAULT_CONFIG in session_strategy.py are mirrors of each other for all
6 configurable parameters (rr, sl_buffer_pips, displacement_mult, atr_period,
sweep_timeout_bars, min_sl_pips, min_range_pips). The config.yaml is not loaded automatically
by session_strategy.py; it is a documentation artifact and may diverge from DEFAULT_CONFIG
if one is updated and the other is not. There is no code that reads config.yaml at runtime
in the session_liquidity package.

The YAML rr value is 3.0. The ST-A2 operating RR confirmed in backtest and documented in
ST_A2_CONFIRMATION.md is 5.0. Both DEFAULT_CONFIG and config.yaml show rr=3.0, which does
NOT match the operating configuration. The adapter passes whatever config is supplied to
run_strategy(); if DEFAULT_CONFIG is used, rr=3.0 not rr=5.0.

---

## Magic Numbers Flagged

| Value | Location | Issue |
|---|---|---|
| 0.0001 (_PIP) | entry_engine.py:20 | Named constant but not parameterizable; assumes 5-decimal FX pairs only. Will silently produce wrong pip counts for non-FX or 2-decimal instruments. |
| 0.75 / 0.25 | displacement_detector.py:179,191 | Quartile thresholds for close position. No symbol in code, just inline literals. Documented in module docstring but not in config. |
| 4 (Asian min bars) | session_builder.py:79 | Not configurable. Hardcoded holiday/gap threshold. |
| 0.25 (risk_percent) | st_a2_adapter.py:69 | 0.25% per trade. RISK_SPEC.md specifies 1% per trade. Discrepancy is unexplained in code comments. |
| 50 (m15 min length) | st_a2_adapter.py:50 | Minimum M15 candle count before calling strategy. No relationship to atr_period or any documented threshold. |
# ST-A2 Parameters

## Engine Defaults

Source: `strategy/session_liquidity/session_strategy.py`

| Parameter | Default | Meaning |
| --- | --- | --- |
| `rr` | `3.0` | Reward/risk target used when building the signal. |
| `sl_buffer_pips` | `2.0` | Stop buffer beyond the sweep wick. |
| `displacement_mult` | `1.2` | ATR multiplier for the displacement body filter. |
| `atr_period` | `14` | Wilder ATR lookback. |
| `sweep_timeout_bars` | `4` | Number of M15 bars allowed between sweep and displacement. |
| `min_sl_pips` | `5.0` | Minimum accepted stop size. |
| `min_range_pips.EURUSD` | `15.0` | Minimum Asian range for EURUSD. |
| `min_range_pips.GBPUSD` | `20.0` | Minimum Asian range for GBPUSD. |
| `min_range_pips.XAUUSD` | `30.0` | Present in code defaults, but the adapter target is EURUSD/GBPUSD. |

## Portfolio And Signal Parameters

| Source | Value |
| --- | --- |
| `config/strategy_portfolio.yaml` risk | `0.30` |
| Adapter `core.Signal.risk_percent` | `0.25` |
| Adapter confidence | `1.0` |
| Signal TTL | `300` seconds from `core.Signal` |
