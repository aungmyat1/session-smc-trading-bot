# Strategy: Adaptive SMC (AdaptiveSMC)

## Version / Status

- **Engine version:** Adaptive Session Engine v1
- **Adapter class:** `AdaptiveSMCAdapter` (`strategies/adapters/adaptive_smc_adapter.py`)
- **Inner strategy module:** `adaptive/strategies/smc_session_strategy.py` (adapter) →
  `strategy/session_liquidity/session_strategy.py` (core logic, SA-07)
- **Status:** DEMO / SHADOW mode only. `DRY_RUN=True` enforced. No live orders can
  be placed until `CONFIRM-LIVE-ON` token is issued and `DRY_RUN=false` is set.
- **Phase:** Pre-validation. Runs inside the shadow runner (`adaptive/run_shadow.py`).
  Paper trade results are logged to `logs/adaptive_trades.jsonl`.

---

## Description

AdaptiveSMC wraps the Session Liquidity Strategy (SA-07) in two adapter layers:

1. `adaptive/strategies/smc_session_strategy.py` — converts `strategy.session_liquidity.session_strategy.Signal`
   objects into `AdaptiveSignal` objects understood by the adaptive engine.
2. `strategies/adapters/adaptive_smc_adapter.py` (`AdaptiveSMCAdapter`) — converts `AdaptiveSignal`
   into the core `Signal` dataclass consumed by the portfolio and execution layers.

The inner strategy (SA-07) is a read-only dependency; neither adapter modifies it.

The strategy identifies sessions where institutional liquidity is swept at Asian session
extremes, then waits for displacement confirmation before entering in the sweep-reversal
direction.

---

## Trading Philosophy

Institutional liquidity rests as stop orders above Asian session highs (bearish traders'
stops) and below Asian session lows (bullish traders' stops). Large market participants
engineered moves to sweep this liquidity before reversing to their intended direction.
The strategy exploits this pattern by:

1. Confirming higher-timeframe directional bias (4H swing structure).
2. Waiting for the Asian session range to be breached with a close-back (sweep reversal candle).
3. Requiring a large-body displacement candle as institutional confirmation within a strict timeout.
4. Entering at the displacement candle's close with a stop loss anchored at the sweep wick.

---

## Market / Timeframe / Session / Direction

| Attribute | Value |
|---|---|
| Instruments | EURUSD, GBPUSD (USDJPY listed in config but not in core strategy min_range_pips) |
| Entry timeframe | M15 (15-minute candles) |
| Bias timeframe | H4 (4-hour candles) |
| Range timeframe | Asian session M15 candles |
| Session — Range build | Asian: 18:00–01:45 EST (prev day 18:00 to trade_date 01:45) |
| Session — Entry window | London: 02:00–04:59 EST / New York: 07:00–09:59 EST |
| Adaptive engine session window | London: 06:00–09:00 UTC / New York: 11:00–15:00 UTC |
| Directions | LONG (bullish sweep reversal) or SHORT (bearish sweep reversal) |
| Max signals | One per session (london or new_york) per calendar day |

Note: The inner strategy uses EST session windows; the adaptive engine config uses UTC windows.
These are different and may diverge during DST transitions.

---

## Signal Chain (phase-by-phase, in execution order)

The complete chain spans two layers: the adaptive routing pipeline (regime + score + risk) and
the inner SA-07 signal pipeline.

### Adaptive Engine Pipeline (outer)

| Stage | Module | Description |
|---|---|---|
| 0 | `news_filter.py` | News safety check (stub — always passes in current code) |
| 1 | `market_feed.py` | Fetch M15 (200 bars), H4 (100 bars), M5 (100 bars), spread |
| 2 | `smc_session_strategy.generate_signals()` | Run inner SA-07 pipeline (see below) |
| 3 | `regime_detector.detect_regime()` | Classify market as TRENDING/BREAKOUT/RANGING/UNSAFE |
| 4 | Regime gate | Reject if UNSAFE or if regime not in {RANGING, BREAKOUT, TRENDING} for smc_session |
| 5 | `signal_scorer.score_signal()` | Score 0–10 against 7 criteria; reject if score < 7 |
| 6 | `risk_manager.check_risk()` | Check daily halt, loss cap, trade count, consec losses, correlation |
| 7 | `paper_execution.open_trade()` | Simulate trade open (DRY_RUN=True; no broker call) |
| 8 | `trade_journal.log_signal()` | Persist routing decision to JSONL log |

### Inner SA-07 Signal Pipeline (per day, per session)

| Phase | Module | Description |
|---|---|---|
| P1 | `session_builder.build_asian_range()` | Build Asian H/L from M15 bars (EST 18:00 prev → 01:45 current) |
| P2 | Min-range filter | Skip day if Asian range < min_range_pips (EURUSD: 15, GBPUSD: 20) |
| P3 | `bias_filter.htf_bias()` | Classify 4H structure as bullish/bearish/neutral (swing_n=2) |
| P4 | Neutral-bias gate | Skip bar if bias is neutral |
| P5 | `sweep_detector.detect_sweep()` | Check if M15 candle breaches Asian extreme and closes back inside |
| P6 | `displacement_detector.detect_displacement()` | Check if displacement candle: body > 1.2×ATR(14), close in upper/lower 25% |
| P7 | Timeout gate | Reject pending sweep if displacement not found within 4 bars |
| P8 | `entry_engine.build_signal()` | Build Signal: entry=displacement close, SL=sweep_wick±buffer, TP=SL_dist×RR |
| P9 | min_sl_pips filter | Reject if risk_pips < 5.0 |
| P10 | One-signal-per-session | After one signal fires per session per day, skip remaining bars |

---

## Entry Rules

- **Entry price:** Close of the M15 displacement candle.
- **Order type:** MARKET (as set in `AdaptiveSMCAdapter.generate_signal()`, line 68).
- **Trigger:** Both sweep detection AND displacement detection must pass in sequence.
- **Direction:** Long if sweep side is "long" (bullish sweep of Asian low); Short if "short".
- **Minimum data requirement:** `len(m15) >= 50` enforced in `AdaptiveSMCAdapter` (line 38).
  The inner strategy additionally requires ATR warmup (period=14 bars) before displacement
  can be evaluated.

---

## Confirmation Rules

All gates are AND-gated. A signal requires ALL of the following:

1. **4H bias confirmed** — `htf_bias()` returns "bullish" (for long) or "bearish" (for short).
   Uses last two swing highs and lows (swing_n=2). Neutral bias → no trade.
2. **Asian range adequate** — Range >= min_range_pips to ensure viable grid.
3. **Liquidity sweep** — M15 candle low < Asian low (long) or high > Asian high (short),
   strict inequality, AND close back inside range, strict inequality.
4. **Displacement within timeout** — Displacement candle must appear within 4 M15 bars
   of the sweep candle.
5. **Displacement body** — Candle body > 1.2 × ATR(14), strict inequality.
6. **Displacement quartile** — Long: close in upper 25% of candle range (close_pos > 0.75).
   Short: close in lower 25% (close_pos < 0.25). Strict inequalities.
7. **Regime gate** — Market regime must be RANGING, BREAKOUT, or TRENDING (not UNSAFE).
   UNSAFE is triggered if spread_pips >= 3.0 or insufficient candles (<29 bars).
8. **Signal score >= 7/10** — scoring breakdown:
   - HTF bias aligned: +2
   - Liquidity swept (metadata flag): +2
   - Structure confirmed (metadata flag): +2
   - In active session: +1
   - Spread acceptable: +1
   - Volatility acceptable (0.1% <= ATR% <= 0.8%): +1
   - News clear: +1

---

## Exit Rules (TP / SL / BE / Trailing / Partial)

Exit logic is defined in `entry_engine.build_signal()` and simulated in `paper_execution.py`.

| Rule | Value | Notes |
|---|---|---|
| Stop Loss | sweep_wick_price - (sl_buffer_pips × 0.0001) for long; sweep_wick_price + buffer for short | Anchored at the actual sweep wick extreme |
| SL buffer | 2.0 pips (configurable: `sl_buffer_pips`) | Added outside sweep wick |
| Take Profit | entry + (SL_distance × rr) for long; entry - (SL_distance × rr) for short | Fixed RR target |
| RR | 3.0 (configurable: `rr`) | |
| Breakeven | NOT IMPLEMENTED in current code | No BE move logic exists in any module |
| Trailing stop | NOT IMPLEMENTED | No trailing logic exists |
| Partial close | NOT IMPLEMENTED | No partial-close logic exists |
| Session close | `paper_execution.close_all()` exists | Called externally — not automatically triggered from within the strategy |
| Min SL distance | 5.0 pips (`min_sl_pips`) | Signals with risk_pips < 5.0 are discarded |

---

## Filters (Spread / Volatility / Session / News)

| Filter | Location | Threshold | Behavior |
|---|---|---|---|
| Spread (regime) | `regime_detector.py` line 150 | >= 3.0 pips → UNSAFE regime | Hard block: signal rejected at regime stage |
| Spread (score) | `signal_scorer.py` line 59 | EURUSD: <=1.5 / GBPUSD: <=2.0 / USDJPY: <=2.0 pips | Soft: -1 point if breached |
| Spread (config) | `adaptive_engine.yaml` line 19 | EURUSD: 1.5 / GBPUSD: 2.0 / USDJPY: 2.0 | Config value; fed into scorer context |
| ATR volatility | `signal_scorer.py` lines 64-65 | 0.1% <= ATR% <= 0.8% | Soft: -1 point if out of range |
| ATR ceiling (config) | `adaptive_engine.yaml` line 25 | max_atr_pct: 0.008 | Config reference only; not separately enforced beyond scorer |
| ATR floor (config) | `adaptive_engine.yaml` line 26 | min_atr_pct: 0.001 | Config reference only |
| Session gate | `signal_scorer.py` line 52 | London: UTC 06–09 / NY: UTC 11–15 | Soft: -1 point if outside window |
| Session gate (inner) | `session_builder.classify_session()` | London: EST 02–04 / NY: EST 07–09 | Hard: inner pipeline only produces signals in these windows |
| News | `news_filter.py` line 43 | Stub — always safe_to_trade=True | NOT enforced (stub) |
| Regime blocked | `adaptive_engine.yaml` line 23 / `trade_router.py` line 31 | UNSAFE | Hard block |
| Min score | `adaptive_engine.yaml` line 18 / `signal_scorer.py` line 15 | 7/10 | Hard block if score < 7 |
| Min Asian range | `session_strategy.py` DEFAULT_CONFIG | EURUSD: 15.0 pip / GBPUSD: 20.0 pip | Hard block: day skipped |
| Min candles (adapter) | `adaptive_smc_adapter.py` line 38 | m15 length >= 50 | Hard block: returns None |

---

## Kill Switch / Safety

| Control | Mechanism | Location |
|---|---|---|
| DRY_RUN | `DRY_RUN` env var; defaults to `"true"`. Live path raises `NotImplementedError` | `demo_executor.py`, `trade_router.py` |
| CONFIRM-LIVE-ON | Token required in `CLAUDE.md §6` before live trading enabled | Process / governance only |
| Daily halt | `risk_manager.record_trade()` sets `halted=True` on daily loss >= 1.5% | `risk_manager.py` line 156 |
| Consecutive loss halt | `halted=True` after 3 consecutive losses | `risk_manager.py` line 160 |
| Daily trade count cap | Rejects after 6 trades/day | `risk_manager.py` / `adaptive_engine.yaml` |
| Daily reset | `StateStore.reset_daily()` resets halt flags each UTC day | `state_store.py` line 77 |
| Correlation guard | Blocks LONG on both EURUSD and GBPUSD simultaneously | `risk_manager.py` line 50 |
| Regime UNSAFE block | Spread >= 3.0 pips or < 29 candles → UNSAFE → REJECTED | `regime_detector.py` |
| LIVE_TRADING=False | `.env` default; agent must never flip (CLAUDE.md §0) | Governance |

---

## Known Limitations

1. **Two-layer adapter mismatch (session windows):** The inner strategy uses EST killzone
   windows (London: 02:00–04:59 EST, NY: 07:00–09:59 EST). The adaptive engine config uses
   different UTC windows (London: 06:00–09:00 UTC, NY: 11:00–15:00 UTC). During DST transitions
   these diverge by one hour. The scorer's session window check may mark a valid inner-strategy
   signal as "outside session" (-1 point).

2. **No FVG retest logic:** The `CLAUDE.md §2` signal chain calls for a Phase 9 FVG retest
   entry. The entry engine enters at the displacement candle close — there is no FVG detection
   or retest wait implemented anywhere in the codebase. The adapter hardcodes
   `"structure_confirmed": True` regardless.

3. **No CHoCH/BOS detection:** `CLAUDE.md §2` Phase 6–7 require CHoCH and BOS confirmation.
   The inner strategy uses displacement detection as its confirmation gate, not CHoCH/BOS.
   Hardcoded metadata `"liquidity_swept": True` and `"structure_confirmed": True` are set
   unconditionally in the adapter (smc_session_strategy.py lines 83–84), causing the scorer
   to always award +4 points for these two criteria regardless of actual signal quality.

4. **News filter is a stub:** `NewsFilter._live = False` hardcoded. No real news feed is wired.
   High-impact news events are not blocked.

5. **No partial close / BE / trailing:** The paper execution only tracks SL/TP binary outcomes.
   The `CLAUDE.md §4` TP1/TP2 structure (75% at 4R, runner at 5R+) is not implemented.

6. **USDJPY pip size inconsistency:** `adaptive_smc_adapter.py` defines `_PIP` for USDJPY as
   0.01 but the inner strategy's `entry_engine.py` hardcodes `_PIP = 0.0001` for all pairs.
   If USDJPY signals were generated, SL/TP calculations in the adapter would be correct but
   the inner strategy would produce wrong pip counts for USDJPY.

7. **M5 candles fetched but never used:** `run_shadow.py` line 149 fetches M5 candles; no
   strategy module consumes them.

8. **HTF bias in run_shadow.py is simplified:** `_derive_htf_bias()` (line 223) uses a 20-bar
   H4 mean vs close threshold (±0.1%), not the swing-structure logic in `bias_filter.htf_bias()`.
   The inner strategy uses the proper `bias_filter.htf_bias()` internally, but the context
   passed to the signal scorer uses the simplified version.

9. **State is not persisted after open position registration:** `register_open_position()` is
   called and state is updated in memory, but `StateStore.update()` is called (`run_shadow.py`
   line 207). However if the process crashes, the in-memory open_positions list is lost.

---

## Dependencies (modules, external)

### Internal modules

| Module | Path | Role |
|---|---|---|
| `AdaptiveSignal` | `adaptive/strategies/__init__.py` | Signal dataclass |
| `SMCSessionStrategy` (inner adapter) | `adaptive/strategies/smc_session_strategy.py` | Converts SA-07 Signal → AdaptiveSignal |
| `run_strategy` / `DEFAULT_CONFIG` | `strategy/session_liquidity/session_strategy.py` | Core SA-07 orchestrator |
| `session_builder` | `strategy/session_liquidity/session_builder.py` | Asian range, killzone classifier |
| `bias_filter` | `strategy/session_liquidity/bias_filter.py` | 4H HTF swing bias |
| `sweep_detector` | `strategy/session_liquidity/sweep_detector.py` | Liquidity sweep detection |
| `displacement_detector` | `strategy/session_liquidity/displacement_detector.py` | Displacement + ATR |
| `entry_engine` | `strategy/session_liquidity/entry_engine.py` | Signal construction |
| `regime_detector` | `adaptive/engine/regime_detector.py` | ADX/ATR regime classification |
| `signal_scorer` | `adaptive/engine/signal_scorer.py` | 0–10 signal scoring |
| `risk_manager` | `adaptive/engine/risk_manager.py` | Daily/consec/correlation risk |
| `trade_router` | `adaptive/engine/trade_router.py` | Full approval pipeline |
| `MarketFeed` | `adaptive/data/market_feed.py` | Candle / spread fetching |
| `NewsFilter` | `adaptive/filters/news_filter.py` | News guard (stub) |
| `PaperExecution` | `adaptive/simulation/paper_execution.py` | Paper trade lifecycle |
| `TradeJournal` | `adaptive/journal/trade_journal.py` | JSONL trade log |
| `StateStore` | `adaptive/state/state_store.py` | Persistent risk state |
| `BaseStrategy` | `core/base_strategy.py` | Abstract adapter interface |
| `Signal` (core) | `core/signal.py` | Core signal dataclass |
| `ForexData` | `data/forex_data.py` | MetaAPI historical data (not audited here) |
| `session_filter` | `data/session_filter.py` | Active session classification |

### External dependencies

| Package | Purpose |
|---|---|
| `metaapi-cloud-sdk >= 29` | Broker connection, historical data, account management |
| `python-dotenv` | `.env` file loading (optional import) |
| `zoneinfo` (stdlib) | EST/EDT timezone handling in session_builder |
| No numpy/pandas | All indicators use pure Python; explicitly noted in regime_detector.py |
