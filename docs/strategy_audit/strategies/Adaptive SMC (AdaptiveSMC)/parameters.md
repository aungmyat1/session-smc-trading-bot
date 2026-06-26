# Parameters: Adaptive SMC (AdaptiveSMC)

## Table of All Parameters

| Parameter | Value | File | Line | Description | Hardcoded | Configurable |
|---|---|---|---|---|---|---|
| **Core Strategy (SA-07) — strategy/session_liquidity/** | | | | | | |
| `rr` | 3.0 | `session_strategy.py` DEFAULT_CONFIG | 27 | Risk-reward ratio for TP calculation | No | Yes — via config override |
| `rr` | 3.0 | `config.yaml` | 1 | Same parameter in YAML config file | No | Yes |
| `sl_buffer_pips` | 2.0 | `session_strategy.py` DEFAULT_CONFIG | 28 | Buffer beyond sweep wick for SL (pips) | No | Yes |
| `sl_buffer_pips` | 2.0 | `config.yaml` | 2 | Same parameter in YAML config file | No | Yes |
| `displacement_mult` | 1.2 | `session_strategy.py` DEFAULT_CONFIG | 29 | ATR multiplier for displacement body gate | No | Yes |
| `displacement_mult` | 1.2 | `config.yaml` | 3 | Same parameter in YAML config file | No | Yes |
| `atr_period` | 14 | `session_strategy.py` DEFAULT_CONFIG | 30 | Wilder ATR period for displacement | No | Yes |
| `atr_period` | 14 | `config.yaml` | 4 | Same parameter in YAML config file | No | Yes |
| `sweep_timeout_bars` | 4 | `session_strategy.py` DEFAULT_CONFIG | 31 | Max M15 bars after sweep to find displacement | No | Yes |
| `sweep_timeout_bars` | 4 | `config.yaml` | 5 | Same parameter in YAML config file | No | Yes |
| `min_sl_pips` | 5.0 | `session_strategy.py` DEFAULT_CONFIG | 32 | Minimum SL distance in pips; signal discarded below | No | Yes |
| `min_sl_pips` | 5.0 | `config.yaml` | 6 | Same parameter in YAML config file | No | Yes |
| `min_range_pips.EURUSD` | 15.0 | `session_strategy.py` DEFAULT_CONFIG | 34 | Minimum Asian range for EURUSD to trade day | No | Yes |
| `min_range_pips.EURUSD` | 15.0 | `config.yaml` | 9 | Same parameter in YAML config file | No | Yes |
| `min_range_pips.GBPUSD` | 20.0 | `session_strategy.py` DEFAULT_CONFIG | 35 | Minimum Asian range for GBPUSD to trade day | No | Yes |
| `min_range_pips.GBPUSD` | 20.0 | `config.yaml` | 10 | Same parameter in YAML config file | No | Yes |
| `_PIP` | 0.0001 | `entry_engine.py` | 21 | Pip size — hardcoded for all pairs | YES — magic number | No |
| `displacement_quartile_long` | 0.75 | `displacement_detector.py` | 179 | Close must be above 75% of candle range (long) | YES — magic number | No |
| `displacement_quartile_short` | 0.25 | `displacement_detector.py` | 192 | Close must be below 25% of candle range (short) | YES — magic number | No |
| `min_asian_bars` | 4 | `session_builder.py` | 79 | Min candles required to build Asian range | YES — magic number | No |
| `asian_session_start_est` | 18 (hour) | `session_builder.py` | 73 | Asian session start: prev-day 18:00 EST | YES — magic number | No |
| `asian_session_end_est` | 2 (hour) | `session_builder.py` | 74 | Asian session end: trade-date 02:00 EST (exclusive) | YES — magic number | No |
| `london_start_est` | 2 | `session_builder.py` | 98 | London killzone start EST hour (inclusive) | YES — magic number | No |
| `london_end_est` | 5 | `session_builder.py` | 98 | London killzone end EST hour (exclusive) | YES — magic number | No |
| `ny_start_est` | 7 | `session_builder.py` | 99 | New York killzone start EST hour (inclusive) | YES — magic number | No |
| `ny_end_est` | 10 | `session_builder.py` | 99 | New York killzone end EST hour (exclusive) | YES — magic number | No |
| `swing_n` | 2 | `bias_filter.py` | 81 | Number of bars each side required for swing pivot | No (default arg) | Yes — via kwarg |
| `htf_bar_offset` | 4h | `bias_filter.py` | 100 | 4H bar close offset for lookahead prevention | YES — magic number | No |
| `range_pips_divisor` | 0.0001 | `session_builder.py` | 27 | Pip size used in range_pips property | YES — magic number | No |
| **Adaptive Engine — adaptive/config/adaptive_engine.yaml** | | | | | | |
| `mode` | demo | `adaptive_engine.yaml` | 4 | Engine mode: demo or live | No | Yes |
| `pairs` | [EURUSD, GBPUSD, USDJPY] | `adaptive_engine.yaml` | 7-9 | Active trading pairs | No | Yes |
| `risk.per_trade` | 0.005 (0.5%) | `adaptive_engine.yaml` | 12 | Risk per trade as fraction of account | No | Yes |
| `risk.daily_loss_limit` | 0.015 (1.5%) | `adaptive_engine.yaml` | 13 | Daily loss cap — halt on breach | No | Yes |
| `risk.max_trades_per_day` | 6 | `adaptive_engine.yaml` | 14 | Max trades per day across all strategies | No | Yes |
| `risk.max_consecutive_losses` | 3 | `adaptive_engine.yaml` | 15 | Halt after N consecutive losses | No | Yes |
| `filters.min_score` | 7 | `adaptive_engine.yaml` | 18 | Minimum signal score (0–10) to approve | No | Yes |
| `filters.max_spread_pips.EURUSD` | 1.5 | `adaptive_engine.yaml` | 20 | Max spread for EURUSD in pips | No | Yes |
| `filters.max_spread_pips.GBPUSD` | 2.0 | `adaptive_engine.yaml` | 21 | Max spread for GBPUSD in pips | No | Yes |
| `filters.max_spread_pips.USDJPY` | 2.0 | `adaptive_engine.yaml` | 22 | Max spread for USDJPY in pips | No | Yes |
| `filters.blocked_regimes` | [UNSAFE] | `adaptive_engine.yaml` | 23-24 | Regime labels that block trading | No | Yes |
| `filters.max_atr_pct` | 0.008 (0.8%) | `adaptive_engine.yaml` | 25 | Upper ATR% ceiling for volatility filter | No | Yes |
| `filters.min_atr_pct` | 0.001 (0.1%) | `adaptive_engine.yaml` | 26 | Lower ATR% floor for volatility filter | No | Yes |
| `sessions.london.start` | "06:00" UTC | `adaptive_engine.yaml` | 29-30 | London session start (UTC) for engine context | No | Yes |
| `sessions.london.end` | "09:00" UTC | `adaptive_engine.yaml` | 31 | London session end (UTC) for engine context | No | Yes |
| `sessions.new_york.start` | "11:00" UTC | `adaptive_engine.yaml` | 33 | New York session start (UTC) for engine context | No | Yes |
| `sessions.new_york.end` | "15:00" UTC | `adaptive_engine.yaml` | 34 | New York session end (UTC) for engine context | No | Yes |
| `smc_session.rr` | 3.0 | `adaptive_engine.yaml` | 49 | RR for SMC session (mirrors DEFAULT_CONFIG) | No | Yes |
| `smc_session.sl_buffer_pips` | 2.0 | `adaptive_engine.yaml` | 50 | SL buffer pips (mirrors DEFAULT_CONFIG) | No | Yes |
| `smc_session.displacement_mult` | 1.2 | `adaptive_engine.yaml` | 51 | Displacement multiplier (mirrors DEFAULT_CONFIG) | No | Yes |
| `smc_session.atr_period` | 14 | `adaptive_engine.yaml` | 52 | ATR period (mirrors DEFAULT_CONFIG) | No | Yes |
| **Adaptive Engine Python defaults** | | | | | | |
| `ATR_PERIOD` | 14 | `regime_detector.py` | 16 | ATR period for regime classification | No (module const) | Yes — via arg |
| `ADX_PERIOD` | 14 | `regime_detector.py` | 17 | ADX period for regime classification | No (module const) | Yes — via arg |
| `ADX_TRENDING` | 25.0 | `regime_detector.py` | 19 | ADX threshold for TRENDING regime | YES — magic number | No |
| `ADX_RANGING` | 20.0 | `regime_detector.py` | 20 | ADX threshold for RANGING regime | YES — magic number | No |
| `ATR_PCT_HIGH` | 0.005 (0.5%) | `regime_detector.py` | 21 | ATR% threshold for high volatility | YES — magic number | No |
| `ATR_PCT_LOW` | 0.002 (0.2%) | `regime_detector.py` | 22 | ATR% threshold for low volatility | YES — magic number | No |
| `MAX_SPREAD_PIPS` | 3.0 | `regime_detector.py` | 23 | Spread above which regime is UNSAFE | YES — magic number | No |
| `atr_expanding_lookback` | 3 | `regime_detector.py` | 113 | Bars ATR must be rising for "expanding" flag | YES — magic number | No |
| `MIN_SCORE` | 7 | `signal_scorer.py` | 15 | Minimum score for signal approval | No (module const) | No (not loaded from config) |
| `_MAX_SPREAD.EURUSD` | 1.5 | `signal_scorer.py` | 19 | Spread ceiling for EURUSD | No (module const) | No (hardcoded dict) |
| `_MAX_SPREAD.GBPUSD` | 2.0 | `signal_scorer.py` | 20 | Spread ceiling for GBPUSD | No (module const) | No (hardcoded dict) |
| `_MAX_SPREAD.USDJPY` | 2.0 | `signal_scorer.py` | 21 | Spread ceiling for USDJPY | No (module const) | No (hardcoded dict) |
| `_MAX_ATR_PCT` | 0.008 | `signal_scorer.py` | 25 | ATR% upper bound for scorer | No (module const) | No |
| `_MIN_ATR_PCT` | 0.001 | `signal_scorer.py` | 26 | ATR% lower bound for scorer | No (module const) | No |
| `_SESSION_WINDOWS.london` | (6, 9) | `signal_scorer.py` | 30 | London UTC hour range for scorer | YES — magic number | No |
| `_SESSION_WINDOWS.new_york` | (11, 15) | `signal_scorer.py` | 31 | NY UTC hour range for scorer | YES — magic number | No |
| `DEFAULT_CONFIG.risk_per_trade` | 0.005 | `risk_manager.py` | 24 | Default risk per trade fraction | No (module const) | Yes — via config |
| `DEFAULT_CONFIG.daily_loss_limit` | 0.015 | `risk_manager.py` | 25 | Default daily loss limit fraction | No (module const) | Yes — via config |
| `DEFAULT_CONFIG.max_trades_per_day` | 6 | `risk_manager.py` | 26 | Default max trades per day | No (module const) | Yes — via config |
| `DEFAULT_CONFIG.max_consecutive_losses` | 3 | `risk_manager.py` | 27 | Default consecutive loss limit | No (module const) | Yes — via config |
| `correlated_pairs` | [("EURUSD","GBPUSD")] | `risk_manager.py` | 29-31 | Pairs that cannot both be LONG simultaneously | No (module const) | Yes — via config |
| `_SAME_DIRECTION_BLOCKED` | {"LONG"} | `risk_manager.py` | 35 | Only LONG-LONG correlation is blocked (SHORT-SHORT allowed) | YES — magic number | No |
| `PAIRS` (shadow runner) | ["EURUSD","GBPUSD"] | `run_shadow.py` | 58 | Default pairs for shadow runner | No (module const) | Yes — via CLI arg |
| `DEFAULT_INTERVAL` | 60 (seconds) | `run_shadow.py` | 59 | Default polling interval for shadow runner | No (module const) | Yes — via CLI arg |
| `htf_bias_threshold` | 0.001 (0.1%) | `run_shadow.py` | 230-231 | Threshold for simplified HTF bias in shadow runner | YES — magic number | No |
| `htf_bias_bars` | 20 | `run_shadow.py` | 227 | Number of H4 bars for simplified bias in shadow runner | YES — magic number | No |
| `m15_min_bars` (shadow runner) | 30 | `run_shadow.py` | 155 | Min M15 bars before processing symbol | YES — magic number | No |
| **Adapter layer** | | | | | | |
| `_PIP.EURUSD` | 0.0001 | `adaptive_smc_adapter.py` | 14 | Pip size for adapter SL/TP calculation | No (module const) | No |
| `_PIP.GBPUSD` | 0.0001 | `adaptive_smc_adapter.py` | 14 | Pip size for adapter SL/TP calculation | No (module const) | No |
| `_PIP.USDJPY` | 0.01 | `adaptive_smc_adapter.py` | 14 | Pip size for USDJPY | No (module const) | No |
| `_PIP.XAUUSD` | 0.1 | `adaptive_smc_adapter.py` | 14 | Pip size for gold (not in active pairs) | No (module const) | No |
| `_PIP` | 0.0001 | `smc_session_strategy.py` | 29 | Pip size hardcoded in inner adapter for EUR/GBP pairs | YES — magic number | No |
| `risk_percent` | 0.25 | `adaptive_smc_adapter.py` | 73 | Risk percent on core Signal object (0.25% of account) | YES — magic number | No |
| `m15_min_bars` (adapter) | 50 | `adaptive_smc_adapter.py` | 38 | Min M15 bars for adapter to proceed | YES — magic number | No |
| `confidence_base` | 0.6 | `adaptive_smc_adapter.py` | 58 | Base confidence score | YES — magic number | No |
| `confidence_liquidity_bonus` | 0.2 | `adaptive_smc_adapter.py` | 60 | Confidence added if liquidity_swept=True | YES — magic number | No |
| `confidence_structure_bonus` | 0.2 | `adaptive_smc_adapter.py` | 62 | Confidence added if structure_confirmed=True | YES — magic number | No |
| `signal_ttl_seconds` | 300 | `core/signal.py` | 29 | Signal expiry time (default from Signal dataclass) | No (dataclass default) | Yes |
| `wait_synchronized_timeout` | 60 (seconds) | `run_shadow.py` | 104 | MetaAPI sync timeout | YES — magic number | No |

---

## Duplicate Parameters (flagged)

| Parameter | Locations | Issue |
|---|---|---|
| `rr=3.0` | `session_strategy.py` DEFAULT_CONFIG, `config.yaml`, `adaptive_engine.yaml` smc_session block | Defined in 3 places; `adaptive_engine.yaml` values are NOT loaded by the inner strategy (it uses DEFAULT_CONFIG directly). The YAML smc_session block is not wired to session_strategy. |
| `sl_buffer_pips=2.0` | Same three locations as `rr` | Same issue — YAML not wired to inner strategy |
| `displacement_mult=1.2` | Same three locations | Same issue |
| `atr_period=14` | Same three locations | Same issue |
| `MAX_SPREAD_PIPS=3.0` (regime_detector) vs `max_spread_pips` in yaml/scorer | `regime_detector.py` (3.0), scorer (1.5/2.0), yaml (1.5/2.0) | Different thresholds at different layers; regime uses a looser 3.0 pip limit |
| `MIN_SCORE=7` | `signal_scorer.py` line 15 AND `adaptive_engine.yaml` line 18 | Duplicated; only `signal_scorer.py` constant is used; yaml value is not loaded into scorer |
| `max_trades_per_day=6` | `risk_manager.py` DEFAULT_CONFIG, `adaptive_engine.yaml` | YAML not passed to risk_manager in shadow runner — DEFAULT_CONFIG used instead |
| `max_consecutive_losses=3` | `risk_manager.py` DEFAULT_CONFIG, `adaptive_engine.yaml` | Same — YAML not wired to risk_manager call |
| `daily_loss_limit=0.015` | `risk_manager.py` DEFAULT_CONFIG, `adaptive_engine.yaml` | Same — YAML not wired |
| `risk_per_trade=0.005` | `risk_manager.py` DEFAULT_CONFIG, `adaptive_engine.yaml` | Same — YAML not wired; also conflicts with `risk_percent=0.25` (0.25%) on Signal object |
| `_PIP=0.0001` | `entry_engine.py`, `smc_session_strategy.py` | Same value, two definitions; no USDJPY support in inner layer |
| `htf_bias_bars=20` | `run_shadow.py` (simplified) vs 4H swing logic in `bias_filter.py` | Two different HTF bias algorithms; shadow runner uses a simpler one for context vs the proper one inside the strategy |

---

## Magic Numbers (unexplained literals)

| Value | Location | Line | Context | Risk |
|---|---|---|---|---|
| `0.75` | `displacement_detector.py` | 179 | Long displacement quartile (upper 25%) | LOW — documented in module docstring |
| `0.25` | `displacement_detector.py` | 192 | Short displacement quartile (lower 25%) | LOW — documented |
| `4` | `session_builder.py` | 79 | Min Asian bars required | LOW — implicit: 4×15min = 1 hour |
| `18, 2, 5, 7, 10` | `session_builder.py` | 73-74, 98-99 | EST session boundary hours | MEDIUM — no named constants |
| `0.001` | `run_shadow.py` | 230-231 | HTF bias threshold in shadow runner | HIGH — unexplained 0.1% threshold for simplified bias, inconsistent with real bias filter |
| `20` | `run_shadow.py` | 227 | H4 bar lookback for simplified bias | MEDIUM — no explanation for 20 bars |
| `30` | `run_shadow.py` | 155 | Min M15 bars before processing | MEDIUM — different from adapter's 50 minimum |
| `0.6, 0.2, 0.2` | `adaptive_smc_adapter.py` | 58, 60, 62 | Confidence scoring breakdown | MEDIUM — no documented rationale |
| `0.25` (risk_percent) | `adaptive_smc_adapter.py` | 73 | 0.25% risk on Signal (vs 0.5% in risk_manager config) | HIGH — inconsistency with risk.per_trade |
| `50` | `adaptive_smc_adapter.py` | 38 | Min M15 bars for adapter | MEDIUM — different from shadow runner's 30 |
| `300` | `core/signal.py` | 29 | Signal TTL 5 minutes | LOW — standard |
| `60` | `run_shadow.py` | 104 | MetaAPI sync timeout seconds | LOW — standard |
| `0.0001` | Multiple files | Various | Pip size — all EUR/GBP pairs | LOW — documented |
