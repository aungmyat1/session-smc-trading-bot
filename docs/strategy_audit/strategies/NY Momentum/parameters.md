# Parameters: NY Momentum

Table columns: Parameter | Value | File | Line | Description | Hardcoded | Configurable

---

## Strategy Core Parameters

| Parameter | Value | File | Line | Description | Hardcoded | Configurable |
|---|---|---|---|---|---|---|
| `LONDON_START` | `6` | `adaptive/strategies/ny_momentum_strategy.py` | 31 | Start UTC hour (inclusive) of London session for level build | YES — magic number | NO |
| `LONDON_END` | `9` | `adaptive/strategies/ny_momentum_strategy.py` | 32 | End UTC hour (inclusive) of London session for level build | YES — magic number | NO |
| `NY_START` | `11` | `adaptive/strategies/ny_momentum_strategy.py` | 33 | Start UTC hour (inclusive) of NY session for trade scanning | YES — magic number | NO |
| `NY_END` | `15` | `adaptive/strategies/ny_momentum_strategy.py` | 34 | End UTC hour (inclusive) of NY session for trade scanning | YES — magic number | NO |
| `TP_RR` | `2.0` | `adaptive/strategies/ny_momentum_strategy.py` | 36 | Take-profit risk:reward ratio | YES | PARTIAL (mirrored in config) |
| `SWEEP_BUFFER` | `1` | `adaptive/strategies/ny_momentum_strategy.py` | 37 | Pips beyond the level required to count as a sweep | YES — magic number | PARTIAL (mirrored in config) |
| `_PIP_SIZE["EURUSD"]` | `0.0001` | `adaptive/strategies/ny_momentum_strategy.py` | 26 | Pip size for EURUSD | YES | NO |
| `_PIP_SIZE["GBPUSD"]` | `0.0001` | `adaptive/strategies/ny_momentum_strategy.py` | 27 | Pip size for GBPUSD | YES | NO |
| `_PIP_SIZE["USDJPY"]` | `0.01` | `adaptive/strategies/ny_momentum_strategy.py` | 28 | Pip size for USDJPY | YES | NO |
| Retest zone top (LONG) | `lh + 2 * pip` | `adaptive/strategies/ny_momentum_strategy.py` | 115 | Upper bound of long retest zone (London High + 2 pips) | YES — magic number `2` | NO |
| Retest zone bot (LONG) | `lh - 1 * pip` | `adaptive/strategies/ny_momentum_strategy.py` | 116 | Lower bound of long retest zone (London High - 1 pip) | YES — magic number `1` | NO |
| SL offset (LONG) | `ll - pip` | `adaptive/strategies/ny_momentum_strategy.py` | 119 | SL = london_low minus 1 pip | YES — magic number `1` (via `pip`) | NO |
| Retest zone top (SHORT) | `ll + 1 * pip` | `adaptive/strategies/ny_momentum_strategy.py` | 143 | Upper bound of short retest zone (London Low + 1 pip) | YES — magic number `1` | NO |
| Retest zone bot (SHORT) | `ll - 2 * pip` | `adaptive/strategies/ny_momentum_strategy.py` | 144 | Lower bound of short retest zone (London Low - 2 pips) | YES — magic number `2` | NO |
| SL offset (SHORT) | `lh + pip` | `adaptive/strategies/ny_momentum_strategy.py` | 147 | SL = london_high plus 1 pip | YES — magic number `1` (via `pip`) | NO |

---

## Adapter Parameters

| Parameter | Value | File | Line | Description | Hardcoded | Configurable |
|---|---|---|---|---|---|---|
| `_PIP["EURUSD"]` | `0.0001` | `strategies/adapters/ny_momentum_adapter.py` | 14 | Pip size for EURUSD (DUPLICATE of strategy dict) | YES | NO |
| `_PIP["GBPUSD"]` | `0.0001` | `strategies/adapters/ny_momentum_adapter.py` | 14 | Pip size for GBPUSD (DUPLICATE of strategy dict) | YES | NO |
| `_PIP["USDJPY"]` | `0.01` | `strategies/adapters/ny_momentum_adapter.py` | 14 | Pip size for USDJPY (DUPLICATE of strategy dict) | YES | NO |
| `_PIP["XAUUSD"]` | `0.1` | `strategies/adapters/ny_momentum_adapter.py` | 14 | Pip size for XAUUSD (NOT in strategy dict — inconsistency) | YES | NO |
| Min candle count | `30` | `strategies/adapters/ny_momentum_adapter.py` | 36 | Minimum M15 candle count before adapter runs | YES — magic number | NO |
| `risk_percent` | `0.25` | `strategies/adapters/ny_momentum_adapter.py` | 61 | Risk % of account per trade (0.25%) | YES — magic number | NO |
| Confidence divisor | `2.5` | `strategies/adapters/ny_momentum_adapter.py` | 62 | Denominator in `rr / 2.5` confidence formula; 2R → 0.8, 2.5R+ → 1.0 | YES — magic number | NO |

---

## Config File Parameters (adaptive_engine.yaml)

| Parameter | Value | File | Line | Description | Hardcoded | Configurable |
|---|---|---|---|---|---|---|
| `ny_momentum.sweep_buffer_pips` | `1` | `adaptive/config/adaptive_engine.yaml` | 46 | Sweep buffer in pips (mirrors strategy constant — but strategy does NOT read from config) | NO (config) | YES (but unused by strategy) |
| `ny_momentum.tp_rr` | `2.0` | `adaptive/config/adaptive_engine.yaml` | 47 | Take-profit RR (mirrors strategy constant — but strategy does NOT read from config) | NO (config) | YES (but unused by strategy) |
| `sessions.london.start` | `"06:00"` | `adaptive/config/adaptive_engine.yaml` | 31 | London session start (mirrors strategy constant — strategy does NOT read from config) | NO (config) | YES (but unused by strategy) |
| `sessions.london.end` | `"09:00"` | `adaptive/config/adaptive_engine.yaml` | 32 | London session end | NO (config) | YES (but unused by strategy) |
| `sessions.new_york.start` | `"11:00"` | `adaptive/config/adaptive_engine.yaml` | 36 | NY session start | NO (config) | YES (but unused by strategy) |
| `sessions.new_york.end` | `"15:00"` | `adaptive/config/adaptive_engine.yaml` | 37 | NY session end | NO (config) | YES (but unused by strategy) |
| `risk.per_trade` | `0.005` (0.5%) | `adaptive/config/adaptive_engine.yaml` | 13 | Per-trade risk % (used by risk_manager DEFAULT_CONFIG — strategy adapter uses its own 0.25%) | NO (config) | YES |
| `risk.daily_loss_limit` | `0.015` (1.5%) | `adaptive/config/adaptive_engine.yaml` | 14 | Daily loss cap — halt at this level | NO (config) | YES |
| `risk.max_trades_per_day` | `6` | `adaptive/config/adaptive_engine.yaml` | 15 | Max signals/trades per day | NO (config) | YES |
| `risk.max_consecutive_losses` | `3` | `adaptive/config/adaptive_engine.yaml` | 16 | Consecutive loss halt threshold | NO (config) | YES |
| `filters.min_score` | `7` | `adaptive/config/adaptive_engine.yaml` | 19 | Signal score gate (0–10) | NO (config) | YES |
| `filters.max_spread_pips.EURUSD` | `1.5` | `adaptive/config/adaptive_engine.yaml` | 21 | Max spread EURUSD | NO (config) | YES |
| `filters.max_spread_pips.GBPUSD` | `2.0` | `adaptive/config/adaptive_engine.yaml` | 22 | Max spread GBPUSD | NO (config) | YES |
| `filters.max_spread_pips.USDJPY` | `2.0` | `adaptive/config/adaptive_engine.yaml` | 23 | Max spread USDJPY | NO (config) | YES |
| `filters.max_atr_pct` | `0.008` | `adaptive/config/adaptive_engine.yaml` | 25 | ATR% ceiling filter | NO (config) | YES |
| `filters.min_atr_pct` | `0.001` | `adaptive/config/adaptive_engine.yaml` | 26 | ATR% floor filter | NO (config) | YES |

---

## Engine / Scorer Constants (not in config)

| Parameter | Value | File | Line | Description | Hardcoded | Configurable |
|---|---|---|---|---|---|---|
| `MIN_SCORE` | `7` | `adaptive/engine/signal_scorer.py` | 15 | Min score for signal approval (DUPLICATE of config `filters.min_score`) | YES | NO (code) — config value exists but scorer reads its own constant |
| `_MAX_SPREAD["EURUSD"]` | `1.5` | `adaptive/engine/signal_scorer.py` | 19 | Max spread EURUSD (DUPLICATE of config) | YES | NO (code) |
| `_MAX_SPREAD["GBPUSD"]` | `2.0` | `adaptive/engine/signal_scorer.py` | 20 | Max spread GBPUSD (DUPLICATE of config) | YES | NO (code) |
| `_MAX_SPREAD["USDJPY"]` | `2.0` | `adaptive/engine/signal_scorer.py` | 21 | Max spread USDJPY (DUPLICATE of config) | YES | NO (code) |
| `_MAX_ATR_PCT` | `0.008` | `adaptive/engine/signal_scorer.py` | 24 | ATR% max (DUPLICATE of config) | YES | NO (code) |
| `_MIN_ATR_PCT` | `0.001` | `adaptive/engine/signal_scorer.py` | 25 | ATR% min (DUPLICATE of config) | YES | NO (code) |
| `_SESSION_WINDOWS["new_york"]` | `(11, 15)` | `adaptive/engine/signal_scorer.py` | 32 | NY session window for scoring (DUPLICATE of config) | YES | NO (code) |

---

## Risk Manager Constants (DEFAULT_CONFIG)

| Parameter | Value | File | Line | Description | Hardcoded | Configurable |
|---|---|---|---|---|---|---|
| `risk_per_trade` | `0.005` | `adaptive/engine/risk_manager.py` | 24 | Default per-trade risk 0.5% (DUPLICATE of config; adapter overrides to 0.25%) | YES (fallback) | YES (via config arg) |
| `daily_loss_limit` | `0.015` | `adaptive/engine/risk_manager.py` | 25 | 1.5% daily loss halt (DUPLICATE of config) | YES (fallback) | YES (via config arg) |
| `max_trades_per_day` | `6` | `adaptive/engine/risk_manager.py` | 26 | Max trades/day (DUPLICATE of config) | YES (fallback) | YES (via config arg) |
| `max_consecutive_losses` | `3` | `adaptive/engine/risk_manager.py` | 27 | Consecutive loss halt (DUPLICATE of config) | YES (fallback) | YES (via config arg) |

---

## Regime Detector Constants

| Parameter | Value | File | Line | Description | Hardcoded | Configurable |
|---|---|---|---|---|---|---|
| `ATR_PERIOD` | `14` | `adaptive/engine/regime_detector.py` | 15 | ATR smoothing period | YES | PARTIAL (function arg with default) |
| `ADX_PERIOD` | `14` | `adaptive/engine/regime_detector.py` | 16 | ADX smoothing period | YES | PARTIAL (function arg with default) |
| `ADX_TRENDING` | `25.0` | `adaptive/engine/regime_detector.py` | 18 | ADX threshold for TRENDING regime | YES — magic number | NO |
| `ADX_RANGING` | `20.0` | `adaptive/engine/regime_detector.py` | 19 | ADX threshold for RANGING regime | YES — magic number | NO |
| `ATR_PCT_HIGH` | `0.005` | `adaptive/engine/regime_detector.py` | 20 | ATR% for BREAKOUT/HIGH-vol classification | YES — magic number | NO |
| `ATR_PCT_LOW` | `0.002` | `adaptive/engine/regime_detector.py` | 21 | ATR% for LOW-vol floor | YES — magic number | NO |
| `MAX_SPREAD_PIPS` | `3.0` | `adaptive/engine/regime_detector.py` | 22 | Spread ceiling → UNSAFE regime | YES — magic number | NO |

---

## Portfolio Manager Constants

| Parameter | Value | File | Line | Description | Hardcoded | Configurable |
|---|---|---|---|---|---|---|
| `RISK_TIERS["tier2"]` | `0.20` (20%) | `core/portfolio_manager.py` | 23 | Risk % for tier2 strategies including NYMomentum | YES | NO |
| `_STRATEGY_TIER["NYMomentum"]` | `"tier2"` | `core/portfolio_manager.py` | 33 | NYMomentum tier assignment | YES | NO |
| `max_trades_per_day` | `8` | `core/portfolio_manager.py` | 38 | Portfolio-level max trades/day | YES (fallback) | YES (via config) |
| `max_open_positions` | `3` | `core/portfolio_manager.py` | 39 | Max simultaneous open positions | YES (fallback) | YES (via config) |
| `daily_loss_limit_pct` | `2.0` | `core/portfolio_manager.py` | 40 | Daily loss % halt (different from adaptive engine's 1.5%) | YES (fallback) | YES (via config) |
| `min_confidence` | `0.6` | `core/portfolio_manager.py` | 43 | Minimum signal confidence to pass portfolio filter | YES (fallback) | YES (via config) |
| Correlation group | `["EURUSD", "GBPUSD"]` | `core/portfolio_manager.py` | 46 | Correlated pair group | YES (fallback) | YES (via config) |

---

## Notes on Magic Numbers and Duplicates

**Magic numbers (unexplained literals):**
- Retest zone bounds: `2` and `1` pip offsets above/below London High/Low (lines 115–116, 143–144) — asymmetric and undocumented
- Adapter confidence divisor: `2.5` (line 62 of adapter) — maps 2R to 0.8 confidence; formula is inline, no comment explaining the choice
- Min candle count `30` in adapter (line 36) — not derived from any session length calculation
- Portfolio tier risk `0.20` (20% of account) — appears very large; likely this is meant as 0.20% but code uses it as a fraction multiplied by account balance elsewhere; requires verification
- HTF bias threshold `1.001` and `0.999` (run_shadow.py lines 231–232) — ±0.1% band around 20-bar mean; undocumented

**Duplicate parameters (defined in both code and config but code does not read config):**
- `sweep_buffer_pips` (config) vs `SWEEP_BUFFER` (code constant)
- `tp_rr` (config) vs `TP_RR` (code constant)
- Session windows (config) vs `LONDON_START/END`, `NY_START/END` (code constants)
- `min_score` (config) vs `MIN_SCORE` (signal_scorer.py constant)
- Max spread (config) vs `_MAX_SPREAD` (signal_scorer.py dict)
- ATR% bounds (config) vs `_MAX_ATR_PCT`/`_MIN_ATR_PCT` (signal_scorer.py constants)

The strategy and scorer read their own hardcoded constants, making the YAML config values for `ny_momentum`, `filters`, and `sessions` have no runtime effect.
# NY Momentum Parameters

## Source Defaults

| Parameter | Default | Meaning |
| --- | --- | --- |
| `LONDON_START` | `6` | London session start in UTC, inclusive. |
| `LONDON_END` | `9` | London session end in UTC, inclusive. |
| `NY_START` | `11` | New York session start in UTC, inclusive. |
| `NY_END` | `15` | New York session end in UTC, inclusive. |
| `TP_RR` | `2.0` | Fixed reward/risk target. |
| `SWEEP_BUFFER` | `1` pip | Minimum sweep distance beyond the London level. |

## Portfolio Settings

| Source | Value |
| --- | --- |
| `config/strategy_portfolio.yaml` execution mode | `demo` |
| `config/strategy_portfolio.yaml` risk | `0.20` |
| Adapter `core.Signal.risk_percent` | `0.25` |
| Adapter confidence | derived from RR, capped at `1.0` |
