# Parameters: London Breakout

All parameters found across config YAMLs, Python DEFAULT_CONFIG dicts, and hardcoded
constants. Duplicates and magic numbers are flagged.

## Parameter Table

| Parameter | Value | File | Line | Description | Hardcoded | Configurable |
|-----------|-------|------|------|-------------|-----------|--------------|
| `ASIAN_START_HOUR` | 0 | london_breakout_strategy.py | 31 | Asian session start (UTC hour, inclusive) | YES | NO |
| `ASIAN_END_HOUR` | 6 | london_breakout_strategy.py | 32 | Asian session end (UTC hour, exclusive) | YES | NO |
| `LONDON_START_HOUR` | 6 | london_breakout_strategy.py | 33 | London session start (UTC hour, inclusive) | YES | NO |
| `LONDON_END_HOUR` | 9 | london_breakout_strategy.py | 34 | London session end (UTC hour, inclusive) | YES | NO |
| `MIN_RANGE_PIPS` | 15.0 | london_breakout_strategy.py | 36 | Minimum Asian range width to allow signal | YES | PARTIAL |
| `MAX_RANGE_PIPS` | 50.0 | london_breakout_strategy.py | 37 | Maximum Asian range width to allow signal | YES | PARTIAL |
| `TP_RR` | 1.5 | london_breakout_strategy.py | 39 | Risk-reward ratio for take profit | YES | PARTIAL |
| `RETEST_TOLERANCE` | 0.3 | london_breakout_strategy.py | 40 | Fraction of pip for retest upper boundary | YES | NO |
| `retest_zone_top (LONG)` | ah + 0.3*pip | london_breakout_strategy.py | 123 | Upper bound of LONG retest zone | YES (derived) | NO |
| `retest_zone_bot (LONG)` | ah - 2*pip | london_breakout_strategy.py | 124 | Lower bound of LONG retest zone | YES (magic 2) | NO |
| `retest_zone_top (SHORT)` | al + 2*pip | london_breakout_strategy.py | 154 | Upper bound of SHORT retest zone | YES (magic 2) | NO |
| `retest_zone_bot (SHORT)` | al - 0.3*pip | london_breakout_strategy.py | 155 | Lower bound of SHORT retest zone | YES (derived) | NO |
| `sl (LONG)` | al - 1*pip | london_breakout_strategy.py | 127 | Stop loss for LONG: 1 pip below Asian Low | YES (magic 1) | NO |
| `sl (SHORT)` | ah + 1*pip | london_breakout_strategy.py | 158 | Stop loss for SHORT: 1 pip above Asian High | YES (magic 1) | NO |
| `_PIP_SIZE["EURUSD"]` | 0.0001 | london_breakout_strategy.py | 26 | Pip value for EURUSD | YES | NO |
| `_PIP_SIZE["GBPUSD"]` | 0.0001 | london_breakout_strategy.py | 27 | Pip value for GBPUSD | YES | NO |
| `_PIP_SIZE["USDJPY"]` | 0.01 | london_breakout_strategy.py | 28 | Pip value for USDJPY | YES | NO |
| `liquidity_swept` | False | london_breakout_strategy.py | 147, 178 | Always False — no liquidity sweep detection | YES (hardcoded) | NO |
| `structure_confirmed` | True | london_breakout_strategy.py | 148, 179 | Always True — no dynamic confirmation | YES (hardcoded) | NO |
| `risk_percent` | 0.25 | london_breakout_adapter.py | 60 | Risk % applied in Signal object (0.25%) | YES | NO |
| `_PIP["EURUSD"]` (adapter) | 0.0001 | london_breakout_adapter.py | 14 | Pip for adapter confidence calc (duplicate) | YES | NO |
| `_PIP["GBPUSD"]` (adapter) | 0.0001 | london_breakout_adapter.py | 14 | Pip for adapter confidence calc (duplicate) | YES | NO |
| `_PIP["USDJPY"]` (adapter) | 0.01 | london_breakout_adapter.py | 14 | Pip for adapter confidence calc (duplicate) | YES | NO |
| `_PIP["XAUUSD"]` (adapter) | 0.1 | london_breakout_adapter.py | 14 | Pip for XAUUSD — NOT in strategy pip dict | YES | NO |
| `min_m15_bars` (adapter) | 30 | london_breakout_adapter.py | 36 | Min bars before strategy is called | YES | NO |
| `min_m15_bars` (runner) | 50 | run_portfolio.py | 195 | Min bars before feed data is used | YES | NO |
| `london_breakout.min_range_pips` (yaml) | 15 | adaptive_engine.yaml | 40 | Duplicate of hardcoded MIN_RANGE_PIPS | NO | YES |
| `london_breakout.max_range_pips` (yaml) | 50 | adaptive_engine.yaml | 41 | Duplicate of hardcoded MAX_RANGE_PIPS | NO | YES |
| `london_breakout.tp_rr` (yaml) | 1.5 | adaptive_engine.yaml | 42 | Duplicate of hardcoded TP_RR | NO | YES |
| `sessions.asian.start` | "00:00" | adaptive_engine.yaml | 29 | Duplicate of ASIAN_START_HOUR | NO | YES |
| `sessions.asian.end` | "06:00" | adaptive_engine.yaml | 30 | Duplicate of ASIAN_END_HOUR | NO | YES |
| `sessions.london.start` | "06:00" | adaptive_engine.yaml | 32 | Duplicate of LONDON_START_HOUR | NO | YES |
| `sessions.london.end` | "09:00" | adaptive_engine.yaml | 33 | Duplicate of LONDON_END_HOUR | NO | YES |
| `risk.per_trade` (adaptive) | 0.005 | adaptive_engine.yaml | 12 | 0.5% risk per trade (adaptive engine path) | NO | YES |
| `risk.daily_loss_limit` | 0.015 | adaptive_engine.yaml | 13 | 1.5% daily loss cap | NO | YES |
| `risk.max_trades_per_day` | 6 | adaptive_engine.yaml | 14 | Max trades per day (adaptive engine) | NO | YES |
| `risk.max_consecutive_losses` | 3 | adaptive_engine.yaml | 15 | Consecutive loss halt trigger | NO | YES |
| `filters.min_score` | 7 | adaptive_engine.yaml | 18 | Min signal score (0-10) to approve | NO | YES |
| `filters.max_spread_pips.EURUSD` | 1.5 | adaptive_engine.yaml | 20 | Duplicate of signal_scorer _MAX_SPREAD | NO | YES |
| `filters.max_spread_pips.GBPUSD` | 2.0 | adaptive_engine.yaml | 21 | Duplicate of signal_scorer _MAX_SPREAD | NO | YES |
| `filters.max_spread_pips.USDJPY` | 2.0 | adaptive_engine.yaml | 22 | Duplicate of signal_scorer _MAX_SPREAD | NO | YES |
| `filters.max_atr_pct` | 0.008 | adaptive_engine.yaml | 25 | 0.8% ATR ceiling (duplicate of scorer) | NO | YES |
| `filters.min_atr_pct` | 0.001 | adaptive_engine.yaml | 26 | 0.1% ATR floor (duplicate of scorer) | NO | YES |
| `LondonBreakout.risk` (portfolio) | 0.20 | strategy_portfolio.yaml | 30 | 0.20% risk per trade (portfolio path) | NO | YES |
| `LondonBreakout.min_confidence` | 0.60 | strategy_portfolio.yaml | 33 | Minimum confidence for PortfolioManager | NO | YES |
| `LondonBreakout.pairs` | [EURUSD, GBPUSD, USDJPY] | strategy_portfolio.yaml | 32 | Active pairs | NO | YES |
| `MIN_SCORE` (scorer) | 7 | signal_scorer.py | 15 | Duplicate of filters.min_score yaml | YES | NO |
| `_MAX_SPREAD.EURUSD` (scorer) | 1.5 | signal_scorer.py | 19 | Duplicate of adaptive_engine.yaml filters | YES | NO |
| `_MAX_SPREAD.GBPUSD` (scorer) | 2.0 | signal_scorer.py | 20 | Duplicate of adaptive_engine.yaml filters | YES | NO |
| `_MAX_SPREAD.USDJPY` (scorer) | 2.0 | signal_scorer.py | 21 | Duplicate of adaptive_engine.yaml filters | YES | NO |
| `_MAX_ATR_PCT` (scorer) | 0.008 | signal_scorer.py | 25 | Duplicate of adaptive_engine.yaml | YES | NO |
| `_MIN_ATR_PCT` (scorer) | 0.001 | signal_scorer.py | 26 | Duplicate of adaptive_engine.yaml | YES | NO |
| `_SESSION_WINDOWS.london` | (6, 9) | signal_scorer.py | 30 | Duplicate of LONDON_START/END_HOUR | YES | NO |
| `ATR_PERIOD` (regime) | 14 | regime_detector.py | 15 | ATR smoothing period | YES | NO |
| `ADX_PERIOD` (regime) | 14 | regime_detector.py | 16 | ADX smoothing period | YES | NO |
| `ADX_TRENDING` | 25.0 | regime_detector.py | 18 | ADX above = TRENDING | YES | NO |
| `ADX_RANGING` | 20.0 | regime_detector.py | 19 | ADX below = RANGING | YES | NO |
| `ATR_PCT_HIGH` | 0.005 | regime_detector.py | 20 | ATR% above = potential BREAKOUT/TRENDING | YES | NO |
| `ATR_PCT_LOW` | 0.002 | regime_detector.py | 21 | ATR% below = too quiet | YES | NO |
| `MAX_SPREAD_PIPS` (regime) | 3.0 | regime_detector.py | 22 | Spread above = UNSAFE regime | YES | NO |
| `DEFAULT_CONFIG.risk_per_trade` | 0.005 | risk_manager.py | 24 | 0.5% default (adaptive path) | YES | NO |
| `DEFAULT_CONFIG.daily_loss_limit` | 0.015 | risk_manager.py | 25 | 1.5% default (adaptive path) | YES | NO |
| `DEFAULT_CONFIG.max_trades_per_day` | 6 | risk_manager.py | 26 | Duplicate of yaml | YES | NO |
| `DEFAULT_CONFIG.max_consecutive_losses` | 3 | risk_manager.py | 27 | Duplicate of yaml | YES | NO |
| `_BLOCKED_REGIMES` | {"UNSAFE"} | trade_router.py | 31 | Hard-blocked regime set | YES | NO |
| `_STRATEGY_REGIME_MAP.london_breakout` | {"BREAKOUT","RANGING"} | trade_router.py | 37 | Allowed regimes for this strategy | YES | NO |
| `_MAX_SPREAD.USDJPY` (runner) | 1.5 | run_portfolio.py | 125 | Different from scorer (scorer has 2.0) | YES | NO |
| `INTERVAL` | 60 | run_portfolio.py | 142 | Tick interval in seconds | YES | NO |
| `_MAX_FETCH_FAIL` | 3 | run_portfolio.py | 127 | Consecutive fetch failures before reconnect | YES | NO |
| `signal.ttl_seconds` | 300 | core/signal.py | 29 | Signal expiry default (5 min) | YES | NO |
| `signal.risk_percent` (Signal) | 0.25 | core/signal.py | 27 | Default in Signal dataclass (overridden by adapter) | YES | NO |

## Duplicate Parameters (misalignment risk)

| Parameter | Value in Code | Value in YAML | Files |
|-----------|--------------|---------------|-------|
| `min_range_pips` | 15.0 (hardcoded) | 15 (yaml) | strategy.py:36 vs adaptive_engine.yaml:40 — YAML is NOT read by strategy |
| `max_range_pips` | 50.0 (hardcoded) | 50 (yaml) | strategy.py:37 vs adaptive_engine.yaml:41 — YAML is NOT read by strategy |
| `tp_rr` | 1.5 (hardcoded) | 1.5 (yaml) | strategy.py:39 vs adaptive_engine.yaml:42 — YAML is NOT read by strategy |
| `max_spread EURUSD` | 1.5 | 1.5 | signal_scorer.py:19 vs adaptive_engine.yaml:20 — scorer ignores yaml |
| `max_spread GBPUSD` | 2.0 | 2.0 | signal_scorer.py:20 vs adaptive_engine.yaml:21 |
| `max_spread USDJPY` | 2.0 (scorer) / 1.5 (runner) | 2.0 | signal_scorer.py:21 vs run_portfolio.py:125 — INCONSISTENT |
| `max_atr_pct` | 0.008 | 0.008 | signal_scorer.py:25 vs adaptive_engine.yaml:25 |
| `min_score` | 7 (hardcoded) | 7 (yaml) | signal_scorer.py:15 vs adaptive_engine.yaml:18 — scorer ignores yaml |
| `Asian session hours` | 0/6 (hardcoded) | "00:00"/"06:00" (yaml) | strategy.py:31-32 vs adaptive_engine.yaml:29-30 |
| `London session hours` | 6/9 (hardcoded) | "06:00"/"09:00" (yaml) | strategy.py:33-34 vs adaptive_engine.yaml:32-33 |

## Magic Numbers (unexplained literals)

| Location | Line | Value | Context | Issue |
|----------|------|-------|---------|-------|
| london_breakout_strategy.py | 124 | `2 * pip` | LONG retest lower bound: `ah - 2*pip` | Why 2 pips? No documentation |
| london_breakout_strategy.py | 154 | `2 * pip` | SHORT retest upper bound: `al + 2*pip` | Same — no documentation |
| london_breakout_strategy.py | 127 | `1 * pip` | SL buffer: `al - pip` | Why 1 pip beyond Asian Low? |
| london_breakout_strategy.py | 158 | `1 * pip` | SL buffer: `ah + pip` | Same — no documentation |
| london_breakout_adapter.py | 61 | `/ 2.0` | `confidence = min(1.0, rr / 2.0)` | "1.5R → 0.75, 2R → 1.0" is commented but the divisor 2.0 is not from any config |
| run_shadow.py | 228 | `* 1.001` | HTF bias bullish threshold | 0.1% above mean = BULLISH — undocumented |
| run_shadow.py | 229 | `* 0.999` | HTF bias bearish threshold | 0.1% below mean = BEARISH — undocumented |
| run_shadow.py | 58 | `PAIRS = ["EURUSD", "GBPUSD"]` | Shadow runner default excludes USDJPY | Inconsistent with strategy_portfolio.yaml |
