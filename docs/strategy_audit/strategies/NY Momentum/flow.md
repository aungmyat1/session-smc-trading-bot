# Execution Flow: NY Momentum

ASCII flowchart of the complete execution path from data ingestion to trade execution.
Every module touched, every decision gate, and every early-exit condition is identified.

---

## Top-Level Entry Point

```
adaptive/run_shadow.py :: main()
        |
        v
asyncio.run( run(pairs, interval) )
        |
        v
  _connect_executor()
  [execution/mt5_executor.py :: MT5Executor]
  [metaapi-cloud-sdk :: MetaApi, account.deploy(), connection.connect()]
        |
        +--[FAIL: token/account missing or connection error]--> LOG ERROR, return None, EXIT
        |
        v
  _build_feed(executor)
  [adaptive/data/market_feed.py :: MarketFeed(ForexData(executor))]
        |
        v
  StateStore()         [adaptive/state/state_store.py]  -- loads data/adaptive_state.json
  NewsFilter()         [adaptive/filters/news_filter.py]
  PaperExecution()     [adaptive/simulation/paper_execution.py]
  TradeJournal()       [adaptive/journal/trade_journal.py]
        |
        v
  MAIN LOOP: while True:
        |
        v
    await _tick(feed, state_store, news_filter, paper, journal, pairs)
        |
        v
    await asyncio.sleep(interval)   [default: 60 seconds]
```

---

## Tick Cycle (_tick function)

```
_tick()
  |
  v
state_store.needs_daily_reset()?
  |-- YES --> state_store.reset_daily()  [resets daily_loss, trades_today, consecutive_losses]
  |-- NO  --> continue
  |
  v
FOR EACH symbol IN pairs:  [default: EURUSD, GBPUSD]

    +-----------------------------------------+
    |  NEWS FILTER                            |
    |  news_filter.is_safe(symbol)            |
    |  [adaptive/filters/news_filter.py]      |
    |                                         |
    |  _live == False? -> always safe (STUB)  |
    |  _live == True?  -> check events        |
    +-----------------------------------------+
        |
        +--[not safe_to_trade]--> LOG "SKIP symbol — news block", CONTINUE to next symbol
        |
        v
    FETCH CANDLES
    [adaptive/data/market_feed.py :: MarketFeed.get_candles()]
    [data/forex_data.py :: ForexData.get_candles() -> metaapi-cloud-sdk]

        feed.get_candles(symbol, "M15", 200)
        feed.get_candles(symbol, "H4",  100)
        feed.get_candles(symbol, "M5",  100)   <-- fetched but not used by ny_momentum
        feed.get_current_spread(symbol)
        |
        +--[OSError / SDK Exception]--> LOG WARNING, CONTINUE to next symbol
        |
        v
    len(m15) < 30?
        +--[YES]--> LOG DEBUG "Insufficient bars", CONTINUE to next symbol
        |
        v
    UPDATE OPEN PAPER TRADES
    [adaptive/simulation/paper_execution.py :: PaperExecution.update()]
        |
        FOR EACH open paper trade WHERE trade["pair"] == symbol:
            current_price = m15[-1]["close"]
            closed = paper.update(trade_id, current_price)
            |
            +--[closed is not None]--> journal.log_trade(closed)
                                       LOG "Trade closed: pair status R=pnl_r"
        |
        v
    GENERATE SIGNALS (all 3 strategies run in parallel on same M15 data)
    |
    +--london_breakout_strategy.generate_signals(m15, symbol)
    |  [adaptive/strategies/london_breakout_strategy.py]
    |
    +--ny_momentum_strategy.generate_signals(m15, symbol)   <-- THIS STRATEGY
    |  [adaptive/strategies/ny_momentum_strategy.py]
    |
    +--smc_session_strategy.generate_signals(m15, h4, symbol)
       [adaptive/strategies/smc_session_strategy.py]
        |
        +--[Exception in any strategy]--> LOG WARNING, all_signals may be partial
        |
        v
    len(all_signals) == 0?
        +--[YES]--> CONTINUE to next symbol
        |
        v
    BUILD CONTEXT
        htf_bias = _derive_htf_bias(h4)   [H4 close vs 20-bar mean, ±0.1% band]
        utc_hour = datetime.now(UTC).hour
        context  = {htf_bias, utc_hour, spread_pips, news_event}
        |
        v
    state = state_store.get()
        |
        v
    FOR EACH signal IN all_signals:
        route_signal(signal, candles=m15, context, risk_state=state, dry_run=True)
```

---

## NY Momentum Signal Generation (generate_signals)

```
ny_momentum_strategy.generate_signals(candles_m15, symbol)
  |
  v
pip = _PIP_SIZE.get(symbol, 0.0001)   [dict lookup with fallback]
  |
  v
_build_london_levels(candles_m15)
  |-- Filter candles: 6 <= utc_hour(c) <= 9
  |-- max(high) over London bars -> lh
  |-- min(low)  over London bars -> ll
  |
  +--[no London bars]--> return []  EARLY EXIT
  |
  v
lh, ll = london["high"], london["low"]
signals = []
swept_long = swept_short = awaiting_retest_long = awaiting_retest_short = False
  |
  v
FOR EACH candle IN candles_m15:

    h = _utc_hour(candle)
    h < NY_START (11) or h > NY_END (15)?
        +--[YES]--> CONTINUE (skip non-NY candle)
        |
        v
    close, high, low, ts = candle values

    +-------------------------------------------------+
    |  SWEEP DETECTION: LONG                         |
    |  if not swept_long and not awaiting_retest_long|
    |    if high > lh + 1*pip AND close > lh:        |
    |      swept_long = True                         |
    |      awaiting_retest_long = True               |
    +-------------------------------------------------+

    +-------------------------------------------------+
    |  SWEEP DETECTION: SHORT                        |
    |  if not swept_short and not awaiting_retest_sh |
    |    if low < ll - 1*pip AND close < ll:         |
    |      swept_short = True                        |
    |      awaiting_retest_short = True              |
    +-------------------------------------------------+

    +-------------------------------------------------------+
    |  RETEST ENTRY: LONG                                   |
    |  if awaiting_retest_long:                             |
    |    retest_top = lh + 2*pip                            |
    |    retest_bot = lh - 1*pip                            |
    |    if (retest_bot <= low <= retest_top) OR            |
    |       (retest_bot <= close <= retest_top):            |
    |                                                       |
    |      entry = close                                    |
    |      sl    = ll - pip                                 |
    |      risk  = entry - sl                               |
    |                                                       |
    |      risk > 0?                                        |
    |        YES: tp = entry + risk*2.0                     |
    |             append AdaptiveSignal(LONG, new_york)     |
    |        NO:  signal silently dropped                   |
    |                                                       |
    |      awaiting_retest_long = False  (always cleared)  |
    +-------------------------------------------------------+

    +-------------------------------------------------------+
    |  RETEST ENTRY: SHORT                                  |
    |  if awaiting_retest_short:                            |
    |    retest_top = ll + 1*pip                            |
    |    retest_bot = ll - 2*pip                            |
    |    if (retest_bot <= high <= retest_top) OR           |
    |       (retest_bot <= close <= retest_top):            |
    |                                                       |
    |      entry = close                                    |
    |      sl    = lh + pip                                 |
    |      risk  = sl - entry                               |
    |                                                       |
    |      risk > 0?                                        |
    |        YES: tp = entry - risk*2.0                     |
    |             append AdaptiveSignal(SHORT, new_york)    |
    |        NO:  signal silently dropped                   |
    |                                                       |
    |      awaiting_retest_short = False  (always cleared) |
    +-------------------------------------------------------+

    [continue to next NY candle]

return signals  (may be [])
```

---

## Adapter Translation (NYMomentumAdapter.generate_signal)

```
NYMomentumAdapter.generate_signal(data)
  |
  v
m15    = data.get("m15", [])
symbol = data.get("symbol", "")

len(m15) < 30?
    +--[YES]--> return None  EARLY EXIT
    |
    v
from adaptive.strategies.ny_momentum_strategy import generate_signals
    +--[ImportError]--> return None  EARLY EXIT
    |
    v
raw_list = generate_signals(m15, symbol)

len(raw_list) == 0?
    +--[YES]--> return None  EARLY EXIT
    |
    v
raw = raw_list[-1]   [ONLY LAST SIGNAL USED; earlier signals in list discarded]

action  = "BUY" if raw.direction == "LONG" else "SELL"
pip     = _PIP.get(symbol, 0.0001)
sl_pips = abs(raw.entry_price - raw.sl_price) / pip
tp_pips = abs(raw.tp_price   - raw.entry_price) / pip
rr      = round(tp_pips / sl_pips, 2)   [0.0 if sl_pips == 0]

return Signal(
    timestamp     = datetime.now(UTC).isoformat(),   [wall-clock, NOT candle time]
    strategy_name = "NYMomentum",
    symbol        = symbol,
    action        = "BUY" | "SELL",
    order_type    = "MARKET",
    entry_price   = raw.entry_price,
    stop_loss     = raw.sl_price,
    take_profit   = raw.tp_price,
    risk_percent  = 0.25,
    confidence    = min(1.0, rr / 2.5),
    metadata      = {session, reason, risk_pips, reward_pips, rr}
)
```

Note: `NYMomentumAdapter` is NOT called from `run_shadow.py`. The shadow runner calls `ny_momentum_strategy.generate_signals()` directly and works with `AdaptiveSignal`, bypassing the adapter. The adapter is used only when the strategy is invoked through the `core.BaseStrategy` / `core.strategy_registry` path.

---

## Signal Routing Pipeline (trade_router.route_signal)

```
route_signal(signal, candles=m15, context, risk_state, dry_run=True)
  |
  v
STAGE 1: REGIME FILTER
  detect_regime(candles, spread_pips)
  [adaptive/engine/regime_detector.py]
    |-- spread_pips >= 3.0? -> regime = UNSAFE, confidence=1.0
    |-- len(candles) < 29?  -> regime = UNSAFE, confidence=0.5
    |-- Compute ATR(14) + ADX(14) via Wilder smoothing
    |-- ADX>=25 and ATR expanding?      -> TRENDING
    |-- ADX>=20 and ATR%>=0.5% and exp? -> BREAKOUT
    |-- ADX<20 and 0.2%<=ATR%<0.5%?    -> RANGING
    |-- else                            -> UNSAFE
    |
    regime in {"UNSAFE"}?
        +--[YES]--> REJECT "REGIME_BLOCKED", log, return
    |
    v
    _STRATEGY_REGIME_MAP["ny_momentum"] = {"TRENDING", "BREAKOUT"}
    regime in {"TRENDING", "BREAKOUT"}?
        +--[NO]--> REJECT "REGIME_MISMATCH", log, return
        |
        v
STAGE 2: SIGNAL SCORING
  score_signal(signal, context_with_atr)
  [adaptive/engine/signal_scorer.py]
    |
    |  +2: htf_bias aligned (BULLISH+LONG or BEARISH+SHORT)?
    |  +2: signal.metadata["liquidity_swept"] == True?   [always True for ny_momentum]
    |  +2: signal.metadata["structure_confirmed"] == True? [always True for ny_momentum]
    |  +1: utc_hour in [11,15]?
    |  +1: spread_pips <= threshold for pair?
    |  +1: 0.001 <= atr_pct <= 0.008?
    |  +1: not context["news_event"]?  [stub: always True -> always +1]
    |
    score >= 7?
        +--[NO]--> REJECT "SCORE_REJECTED: N/10", log, return
        |
        v
STAGE 3: RISK CHECK
  risk_manager.check_risk(signal, risk_state, config)
  [adaptive/engine/risk_manager.py]
    |
    |  Check 1: not state["halted"]
    |  Check 2: state["daily_loss_pct"] < 0.015
    |  Check 3: state["trades_today"] < 6
    |  Check 4: state["consecutive_losses"] < 3
    |  Check 5: no correlated position (LONG EURUSD + LONG GBPUSD)
    |
    all checks pass?
        +--[NO]--> REJECT "RISK_BLOCKED: [failed_checks]", log, return
        |
        v
APPROVED (dry_run=True)
  [log to logs/adaptive_engine.log]
  return {"decision": "APPROVED", ...}

  dry_run=False path: REJECT "LIVE_TRADING_NOT_ENABLED"
  [live execution is never reached — blocked by DRY_RUN default]
```

---

## Post-Approval (Shadow Mode)

```
result["decision"] == "APPROVED"?
    +--[YES]-->
        trade_id = paper.open_trade(sig)
        [adaptive/simulation/paper_execution.py]
        -- stores entry, sl, tp, direction, session in _open dict
        -- assigned uuid4[:8] trade_id

        state = register_open_position(sig, state)
        [adaptive/engine/risk_manager.py]
        -- appends {pair, direction} to state["open_positions"]

        state_store.update(state)
        [adaptive/state/state_store.py]
        -- persists to data/adaptive_state.json

        journal.log_signal(sig, result)
        [adaptive/journal/trade_journal.py]
        -- appends signal record to logs/adaptive_trades.jsonl

        LOG INFO "APPROVED strategy pair direction score regime id"

    +--[NO]-->
        journal.log_signal(sig, result)
        LOG DEBUG "REJECTED strategy pair direction reason"
```

---

## Trade Close (Paper Execution)

```
Each subsequent _tick(), for open paper trades:

    paper.update(trade_id, m15[-1]["close"])
    [adaptive/simulation/paper_execution.py :: update()]

    LONG:
        price >= tp?  -> status="tp",  pnl_r = (tp - entry) / risk
        price <= sl?  -> status="sl",  pnl_r = (sl - entry) / risk  [negative]

    SHORT:
        price <= tp?  -> status="tp",  pnl_r = (entry - tp) / risk
        price >= sl?  -> status="sl",  pnl_r = (entry - sl) / risk  [negative]

    Hit detected?
        +--[YES]-->
            journal.log_trade(closed_trade)
            del paper._open[trade_id]
            return closed_trade
        +--[NO]--> update unrealised pnl_r, return None

NOTE: close_all() is NEVER called. Trades that are not hit remain open indefinitely.
NOTE: risk_manager.record_trade() is NEVER called from run_shadow.py.
      state["consecutive_losses"] and state["daily_loss_pct"] are never updated from trade outcomes.
```

---

## Module Map

```
run_shadow.py
    |-- adaptive/data/market_feed.py
    |       |-- data/forex_data.py  [MetaAPI candle fetch]
    |       |-- data/session_filter.py
    |
    |-- adaptive/state/state_store.py
    |       |-- adaptive/engine/risk_manager.py  [new_state, reset_daily]
    |
    |-- adaptive/filters/news_filter.py  [STUB]
    |
    |-- adaptive/simulation/paper_execution.py
    |
    |-- adaptive/journal/trade_journal.py
    |
    |-- adaptive/engine/trade_router.py
    |       |-- adaptive/engine/regime_detector.py
    |       |-- adaptive/engine/signal_scorer.py
    |       |-- adaptive/engine/risk_manager.py  [check_risk]
    |
    |-- adaptive/strategies/ny_momentum_strategy.py  [generate_signals]
    |       |-- adaptive/strategies/__init__.py  [AdaptiveSignal]
    |
    |-- adaptive/strategies/london_breakout_strategy.py
    |-- adaptive/strategies/smc_session_strategy.py
    |
    |-- execution/mt5_executor.py  [MetaAPI SDK connection]

strategies/adapters/ny_momentum_adapter.py  [SEPARATE PATH, not used by run_shadow.py]
    |-- core/base_strategy.py
    |-- core/signal.py
    |-- adaptive/strategies/ny_momentum_strategy.py
```
# NY Momentum Flow

1. Build London high/low levels from the London session.
1. Scan New York bars in order.
1. Watch for a swept long or short side.
1. Require a close beyond the swept level.
1. Wait for a retest candle.
1. Build the final signal from the retest close.
1. Reset the corresponding side after a signal is emitted.
