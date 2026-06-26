# Rules: NY Momentum

Rules are listed in execution order. Each entry covers: Purpose | Inputs | Output | Code location (file:function:line) | Failure modes.

---

## Rule 1 — Minimum Bar Count Guard (Adapter)

**Purpose:** Prevent the strategy from running on insufficient data, which would produce no London levels and thus no signals.

**Inputs:** `len(data.get("m15", []))`

**Output:** Returns `None` from `generate_signal()` if fewer than 30 M15 bars are present.

**Code location:** `strategies/adapters/ny_momentum_adapter.py` : `generate_signal` : line 36

**Failure modes:**
- 30 bars covers only 7.5 hours of M15 data; a full London+NY window requires ~9 hours (36 bars minimum). A feed returning exactly 30 bars from late in the day would contain no London bars and generate no signals anyway, but the guard does not catch the case where bars exist but none are from the London session. The strategy handles that internally (rule 2).
- If `data` dict is missing the `"m15"` key, `data.get("m15", [])` returns `[]` and the guard fires silently.

---

## Rule 2 — London Level Build

**Purpose:** Establish the reference high and low from the London session for use as liquidity level targets.

**Inputs:** All M15 candles where `LONDON_START (6) <= utc_hour(candle) <= LONDON_END (9)`. Uses `candle["high"]` and `candle["low"]`.

**Output:** Dict `{"high": float, "low": float}` or `None` if no London bars exist.

**Code location:** `adaptive/strategies/ny_momentum_strategy.py` : `_build_london_levels` : lines 51–58; called from `generate_signals` : line 78

**Failure modes:**
- Returns `None` if no candles fall in the 06–09 UTC window → `generate_signals` returns `[]` immediately (line 79–80).
- Relies on `_utc_hour()` parsing the `"time"` field. If `time` is absent or in an unrecognised format, `_utc_hour()` returns `-1`, excluding that candle from London bars. Silently drops malformed candles.
- Both `max()` and `min()` are called on the filtered list — if the list is non-empty, these will not raise. But a single-bar London session is accepted without validation.

---

## Rule 3 — NY Session Window Gate

**Purpose:** Restrict signal scanning to NY session hours only; ignore all candles outside the window.

**Inputs:** UTC hour of each candle from `_utc_hour(candle)`.

**Output:** `continue` (skip candle) if hour < 11 or hour > 15.

**Code location:** `adaptive/strategies/ny_momentum_strategy.py` : `generate_signals` : lines 92–93

**Failure modes:**
- Hour boundary is inclusive on both ends (11 and 15). A 15:45 UTC candle has hour=15 and is included; a 16:00 candle (hour=16) is excluded. This is consistent with `NY_END = 15`.
- Candles with unrecognised time format have `_utc_hour` returning `-1`, which is less than `NY_START`, so they are silently skipped.

---

## Rule 4 — Sweep Detection: LONG

**Purpose:** Detect that NY price has genuinely swept (not merely ticked) above the London High with a confirming close.

**Inputs:**
- `candle["high"] > lh + SWEEP_BUFFER * pip` (high exceeds London High by 1 pip)
- `candle["close"] > lh` (close is above London High — confirmation)
- State: `swept_long == False` and `awaiting_retest_long == False`

**Output:** Sets `swept_long = True` and `awaiting_retest_long = True` (one-shot).

**Code location:** `adaptive/strategies/ny_momentum_strategy.py` : `generate_signals` : lines 102–105

**Failure modes:**
- One-shot per session: once `swept_long=True`, subsequent sweeps of London High are ignored. If price sweeps, fails to retest (no signal generated), then sweeps again, the second sweep is missed.
- The guard checks `not swept_long and not awaiting_retest_long`. After a retest attempt clears `awaiting_retest_long` (line 140), `swept_long` remains `True`, so no second sweep is ever detected. This is a permanent lock-out for the session.
- The 1-pip buffer is a fixed absolute. For JPY pairs where pip = 0.01, the buffer is 0.01 price units; for EURUSD, 0.0001. The buffer logic is correct per-pair only if `pip` is set correctly.

---

## Rule 5 — Sweep Detection: SHORT

**Purpose:** Detect that NY price has swept below the London Low with a confirming close.

**Inputs:**
- `candle["low"] < ll - SWEEP_BUFFER * pip`
- `candle["close"] < ll`
- State: `swept_short == False` and `awaiting_retest_short == False`

**Output:** Sets `swept_short = True` and `awaiting_retest_short = True` (one-shot).

**Code location:** `adaptive/strategies/ny_momentum_strategy.py` : `generate_signals` : lines 107–110

**Failure modes:** Same as Rule 4 (LONG sweep), mirrored for short direction.

---

## Rule 6 — Retest Entry: LONG

**Purpose:** Enter long when price retests the swept London High level, providing a reduced-risk entry compared to entering at the sweep extreme.

**Inputs:**
- State: `awaiting_retest_long == True`
- Retest zone: `retest_bot = lh - 1*pip` to `retest_top = lh + 2*pip`
- Condition: `retest_bot <= candle["low"] <= retest_top` OR `retest_bot <= candle["close"] <= retest_top`

**Output:** If retest detected AND `risk > 0`:
- `entry = candle["close"]`
- `sl = ll - pip`
- `tp = entry + risk * 2.0`
- Appends `AdaptiveSignal` with `direction="LONG"`, `session="new_york"`, metadata `liquidity_swept=True`, `structure_confirmed=True`
- Clears `awaiting_retest_long = False` (one-shot per session)

**Code location:** `adaptive/strategies/ny_momentum_strategy.py` : `generate_signals` : lines 113–140

**Failure modes:**
- Entry price is the retest candle's `close`, not an ask/bid price. In live execution, market entry would be at the next tick's offer, not the M15 close.
- If `risk <= 0` (entry price is at or below the SL), the signal is silently dropped without logging. This can occur if the London range is degenerate (low == high) or if entry at close happens to equal the SL.
- Retest zone upper bound is `lh + 2*pip` — a candle that closes above the London High by 1 pip would trigger a retest entry even though it has closed above the swept level (not a true retest). This is a potential false entry.
- `awaiting_retest_long` is cleared regardless of whether `risk > 0`. If the signal is silently dropped due to zero risk, the retest opportunity is consumed with no signal.
- The retest condition checks `candle["low"]` (for long) but this allows a candle whose body is entirely above the retest zone to trigger entry if only the wick dips in. Entry is still at `close` (above the zone), which may not be the actual retest price.

---

## Rule 7 — Retest Entry: SHORT

**Purpose:** Enter short when price retests the swept London Low level.

**Inputs:**
- State: `awaiting_retest_short == True`
- Retest zone: `retest_bot = ll - 2*pip` to `retest_top = ll + 1*pip`
- Condition: `retest_bot <= candle["high"] <= retest_top` OR `retest_bot <= candle["close"] <= retest_top`

**Output:** If retest detected AND `risk > 0`:
- `entry = candle["close"]`
- `sl = lh + pip`
- `tp = entry - risk * 2.0`
- Appends `AdaptiveSignal` with `direction="SHORT"`, `session="new_york"`
- Clears `awaiting_retest_short = False`

**Code location:** `adaptive/strategies/ny_momentum_strategy.py` : `generate_signals` : lines 142–168

**Failure modes:** Mirror of Rule 6 (LONG). Additionally: the short retest checks `candle["high"]` in the zone; for the same reason as LONG, a candle whose body is below the zone but whose wick is inside will trigger with entry at close (below the zone).

---

## Rule 8 — Signal Translation (Adapter)

**Purpose:** Convert `AdaptiveSignal` to the canonical `Signal` dataclass consumed by the execution and portfolio layers.

**Inputs:** Last element of the list returned by `generate_signals()` (`raw_list[-1]`)

**Output:** `Signal` with:
- `action = "BUY"` if `raw.direction == "LONG"` else `"SELL"`
- `order_type = "MARKET"`
- `risk_percent = 0.25` (hardcoded)
- `confidence = min(1.0, rr / 2.5)` where rr is computed from SL/TP pip distances
- `metadata` contains session, reason, risk_pips, reward_pips, rr

**Code location:** `strategies/adapters/ny_momentum_adapter.py` : `generate_signal` : lines 39–68

**Failure modes:**
- Only the **last** signal in the list is used (`raw_list[-1]`). If the strategy generates both a LONG and a SHORT in the same session (theoretically possible if both sweeps happen before any retest), only the last one is forwarded. The first is silently discarded.
- Signal timestamp is set to `datetime.now(timezone.utc)` at adapter call time, not the candle timestamp from the strategy. On replays, this causes the signal to appear current even if the candle data is historical.
- `sl_pips = 0` is possible if `entry_price == sl_price` (degenerate geometry); the adapter then computes `rr = 0.0` and `confidence = 0.0`. The signal will fail the portfolio manager's `min_confidence = 0.6` filter and be dropped.

---

## Rule 9 — Signal Routing: Regime Filter

**Purpose:** Block signals in market regimes unsuitable for ny_momentum (e.g., RANGING or UNSAFE).

**Inputs:** M15 candles passed to `route_signal()`; current spread in pips.

**Output:** `REJECTED` with reason `REGIME_BLOCKED` or `REGIME_MISMATCH` if regime is not in `{"TRENDING", "BREAKOUT"}`.

**Code location:** `adaptive/engine/trade_router.py` : `route_signal` : lines 88–100

**Failure modes:**
- The regime is computed from M15 candles at signal routing time. If fewer than 29 candles are available, regime returns `UNSAFE` and the signal is rejected even if the London/NY logic would produce a valid setup.
- The `_STRATEGY_REGIME_MAP` is hardcoded in `trade_router.py` and not sourced from config.

---

## Rule 10 — Signal Routing: Score Filter

**Purpose:** Require a minimum composite quality score before routing the signal.

**Inputs:** `AdaptiveSignal` + context dict (htf_bias, utc_hour, spread_pips, atr_pct, news_event).

**Output:** `REJECTED` if `score < 7`. Score breakdown:
- HTF bias aligned (+2): requires `context["htf_bias"]` == BULLISH (LONG) or BEARISH (SHORT)
- Liquidity event (+2): `signal.metadata["liquidity_swept"]` — always `True` for ny_momentum
- Structure confirmed (+2): `signal.metadata["structure_confirmed"]` — always `True` for ny_momentum
- Active session (+1): utc_hour in [11, 15]
- Spread acceptable (+1): spread <= threshold for pair
- Volatility acceptable (+1): ATR% in [0.001, 0.008]
- News clear (+1): not `context["news_event"]` (stub always True)

**Code location:** `adaptive/engine/signal_scorer.py` : `score_signal` : lines 75–137; `trade_router.py` : `route_signal` : lines 103–109

**Failure modes:**
- `liquidity_swept` and `structure_confirmed` are hardcoded `True` in every ny_momentum signal (metadata lines 136–138, 162–164 of strategy). This means 4 points are always awarded regardless of actual market structure. A signal that failed HTF alignment would still score 5 (liquidity + structure + session + news), below the threshold of 7 — but the inflation makes borderline signals easier to pass.
- HTF bias is derived in `run_shadow.py` as a simple H4 close vs 20-bar mean ±0.1%. If H4 data is unavailable or returns fewer than 20 bars, bias returns `"NEUTRAL"` and contributes 0 points. A signal would need all remaining checks to pass (5 points max from liquidity+structure+session+news+one-of-spread-or-vol) which still falls short of 7. The signal would be rejected.

---

## Rule 11 — Signal Routing: Risk Check

**Purpose:** Enforce daily loss, trade count, consecutive loss, and correlation guards before approving a signal.

**Inputs:** `AdaptiveSignal`, risk state dict, config.

**Output:** `REJECTED` if any of: `halted==True`, `daily_loss_pct >= 0.015`, `trades_today >= 6`, `consecutive_losses >= 3`, or correlated position detected (LONG on both EURUSD and GBPUSD simultaneously).

**Code location:** `adaptive/engine/risk_manager.py` : `check_risk` : lines 65–113; `trade_router.py` : `route_signal` : lines 111–117

**Failure modes:**
- State is in-memory (not persisted between ticks) unless the `StateStore` is used and `update()` is called. In `run_shadow.py`, `state_store.update(state)` is called after each approval (line 207), so persistence is correct for open positions. But `record_trade()` in risk_manager is never called from `run_shadow.py` — trade outcomes do not update `consecutive_losses` or `daily_loss_pct`.
- The correlation guard only blocks LONG/LONG (not SHORT/SHORT): `_SAME_DIRECTION_BLOCKED = {"LONG"}` (line 35). This is asymmetric.

---

## Rule 12 — Paper Trade Lifecycle

**Purpose:** Simulate trade execution, tracking P&L in R multiples, and closing at SL or TP.

**Inputs:** Approved `AdaptiveSignal` → `PaperExecution.open_trade()`; subsequent M15 close prices → `PaperExecution.update()`.

**Output:** Closed trade dict with `pnl_r`, `status` ("tp" or "sl"), recorded to `TradeJournal`.

**Code location:** `adaptive/simulation/paper_execution.py` : `open_trade` : line 30; `update` : line 48; `adaptive/run_shadow.py` : `_tick` : lines 162–168

**Failure modes:**
- `update()` is called using `m15[-1]["close"]` as the current price — a single price point per M15 candle, not intra-candle extremes. TP/SL are checked against close only. A candle that hit TP on its high but closed below TP would not register as a TP hit until a future candle closes at or above TP. This understates TP hit frequency.
- `close_all()` exists but is never called. Open paper trades are never force-closed at session end or on shutdown. They persist indefinitely until SL or TP is hit on a future candle.
- Paper execution does not simulate spread: entry is at candle close (bid-equivalent); no ask-side adjustment.
