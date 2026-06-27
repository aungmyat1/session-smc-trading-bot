# Execution Flow: London Breakout

Complete execution path from data ingestion to trade execution (or rejection).
Two operational paths exist: the Portfolio Runner path (primary) and the Adaptive
Shadow Runner path (alternative). Both share the core strategy module.

---

## Path A: Portfolio Runner (scripts/run_portfolio.py)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          run_portfolio.py — _tick()                         │
│                          (every INTERVAL=60 seconds)                        │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │   Daily Reset Check          │
                    │   risk_state["last_reset"]   │
                    │   vs today's date            │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │  PortfolioManager.any_        │
                    │  loss_limit_hit()?           │
                    │  (daily/weekly/monthly caps) │
                    └──────┬──────────────┬────────┘
                           │ YES          │ NO
                           ▼             │
                      [TICK SKIP]        │
                                         ▼
              ┌──────────────────────────────────────────┐
              │  PHASE 1: Data Fetch (per symbol)         │
              │  VantageDemoExecutor.get_candles()        │
              │    M15: 200 bars                          │
              │    H4: 100 bars (LondonBreakout: unused)  │
              │  VantageDemoExecutor.get_price()          │
              │    → spread_pips, bid                     │
              └──────────────────┬───────────────────────┘
                                 │
              ┌──────────────────▼───────────────────────┐
              │  Spread guard: spread > _MAX_SPREAD?      │
              │  EURUSD:1.5  GBPUSD:2.0  USDJPY:1.5      │
              └────────────┬─────────────────────────────┘
                           │ spread > threshold
                           ▼
                    [SKIP SYMBOL — log]
                           │ spread OK
                           ▼
              ┌────────────────────────────────────────────┐
              │  Bar count guard: len(m15) < 50?            │
              └────────────┬───────────────────────────────┘
                           │ < 50 bars
                           ▼
                  [SKIP SYMBOL — debug log]
                           │ >= 50 bars
                           ▼
              ┌────────────────────────────────────────────┐
              │  PHASE 2: Signal Generation                 │
              │  (LondonBreakout runs for each symbol       │
              │   in its configured pair list)              │
              └────────────────────────────────────────────┘
                                   │
              ┌────────────────────▼────────────────────────┐
              │  LondonBreakoutAdapter.generate_signal()     │
              │  strategies/adapters/london_breakout_        │
              │  adapter.py                                  │
              └────────────────────┬────────────────────────┘
                                   │
              ┌────────────────────▼────────────────────────┐
              │  Adapter bar count guard: len(m15) < 30?    │
              └────────────┬────────────────────────────────┘
                           │ < 30
                           ▼
                    [return None]
                           │ >= 30
                           ▼
              ┌────────────────────────────────────────────────┐
              │  adaptive/strategies/london_breakout_strategy   │
              │  .generate_signals(m15, symbol)                 │
              └────────────────────┬───────────────────────────┘
                                   │
              ┌────────────────────▼───────────────────────────┐
              │  RULE 2: Build Asian range                      │
              │  Filter bars: 00:00 <= utc_hour < 06:00         │
              └────────────┬───────────────────────────────────┘
                           │ no bars in window
                           ▼
                    [return [] → None]
                           │ bars found
                           ▼
              ┌────────────────────────────────────────────────┐
              │  RULE 3: Validate range pips                    │
              │  15.0 <= (high-low)/pip <= 50.0                 │
              └────────────┬───────────────────────────────────┘
                           │ out of range
                           ▼
                    [return [] → None]
                           │ in range
                           ▼
              ┌────────────────────────────────────────────────┐
              │  RULE 4+5: Scan London bars (06-09 UTC)         │
              │  - RULE 4: Filter to London window              │
              │  - RULE 5: Detect first breakout close          │
              │    close > asian_high → LONG                    │
              │    close < asian_low  → SHORT                   │
              └────────────┬───────────────────────────────────┘
                           │ no breakout found in London window
                           ▼
                    [return [] → None]
                           │ breakout found
                           ▼
              ┌────────────────────────────────────────────────┐
              │  RULE 6/7: Retest confirmation on next bars     │
              │  LONG: (ah-2pip) <= candle.low <= (ah+0.3pip)   │
              │  SHORT: (al-0.3pip) <= candle.high <= (al+2pip) │
              └────────────┬───────────────────────────────────┘
                           │ no retest in remaining London bars
                           ▼
                    [return [] → None]
                           │ retest found
                           ▼
              ┌────────────────────────────────────────────────┐
              │  RULE 8/9: Compute SL and TP                    │
              │  risk = |entry - sl|; tp = entry ± risk*1.5     │
              └────────────┬───────────────────────────────────┘
                           │ risk <= 0
                           ▼
                    [reset, continue → no signal]
                           │ risk > 0
                           ▼
              ┌────────────────────────────────────────────────┐
              │  RULE 10: Emit AdaptiveSignal                   │
              │  liquidity_swept=False, structure_confirmed=True│
              │  breakout_direction reset → one signal/session  │
              └────────────────────────────────────────────────┘
                                   │
              ┌────────────────────▼───────────────────────────┐
              │  Adapter: AdaptiveSignal → core.Signal          │
              │  action = "BUY"/"SELL"                          │
              │  risk_percent = 0.25 (hardcoded)                │
              │  confidence = min(1.0, rr/2.0) → 0.75 for 1.5R │
              │  timestamp = datetime.now(UTC) (wall clock)     │
              └────────────────────────────────────────────────┘
                                   │
                    [sig.metadata["execution_mode"] = "demo"]
                                   │
              ┌────────────────────▼───────────────────────────┐
              │  PHASE 3: SignalRouter.route(raw_signals)        │
              │  core/signal_router.py                          │
              │  Validates: TTL, geometry, conflict resolution  │
              └────────────┬───────────────────────────────────┘
                           │ rejected by router
                           ▼
                    [REJECTED — logged to TradeJournalDB]
                           │ approved
                           ▼
              ┌────────────────────────────────────────────────┐
              │  PHASE 4: CircuitBreaker.check("LondonBreakout")│
              │  core/circuit_breaker.py                        │
              │  Checks: cooldown | signals/hr | trades/day |   │
              │          consecutive losses                     │
              │  (Uses defaults: 6/hr, 4/day, 4 losses, 4h CD) │
              └────────────┬───────────────────────────────────┘
                           │ blocked
                           ▼
                    [REJECTED — logged BLOCKED]
                           │ approved
                           ▼
              ┌────────────────────────────────────────────────┐
              │  PHASE 5: PortfolioManager.evaluate(signals)    │
              │  core/portfolio_manager.py                      │
              │  Checks: max_open_positions=3 | daily/weekly/  │
              │          monthly loss limits | correlation groups│
              └────────────┬───────────────────────────────────┘
                           │ blocked
                           ▼
                    [REJECTED — logged BLOCKED]
                           │ approved
                           ▼
              ┌────────────────────────────────────────────────┐
              │  PHASE 6: demo_risk_manager.check_limits()      │
              │  execution/demo_risk_manager.py                 │
              └────────────┬───────────────────────────────────┘
                           │ blocked
                           ▼
                    [SKIP — log]
                           │ approved
                           ▼
              ┌────────────────────────────────────────────────┐
              │  calculate_lots(balance, sl_pips, symbol)       │
              │  execution/demo_risk_manager.py                 │
              └────────────────────────────────────────────────┘
                                   │
              ┌────────────────────▼───────────────────────────┐
              │  Determine final exec_mode                      │
              │  if global_mode == "shadow" → exec_mode=shadow  │
              │  else: use signal.metadata["execution_mode"]    │
              └────────────────────┬───────────────────────────┘
                         ┌─────────┴──────────┐
                    SHADOW mode          DEMO mode
                         │                    │
                         ▼                    ▼
              ┌──────────────────┐  ┌────────────────────────┐
              │ ShadowTracker    │  │ TradeManager            │
              │ .track(signal)   │  │ .open_position(signal,  │
              │ TradeJournalDB   │  │  lots) → broker order   │
              │ journal.log_open │  │ TradeJournalDB.record   │
              │                  │  │ journal.log_open        │
              └──────────────────┘  └────────────────────────┘
```

---

## Path B: Adaptive Shadow Runner (adaptive/run_shadow.py)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          run_shadow.py — _tick()                            │
│                          (every DEFAULT_INTERVAL=60 seconds)                │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │  StateStore.needs_daily_     │
                    │  reset()? → reset if so      │
                    └──────────────┬──────────────┘
                                   │
              ┌────────────────────▼───────────────────────────┐
              │  NewsFilter.is_safe(symbol)                     │
              │  adaptive/filters/news_filter.py                │
              │  → always True (stub)                           │
              └────────────┬───────────────────────────────────┘
                           │ not safe (manual block only)
                           ▼
                    [SKIP SYMBOL]
                           │ safe
                           ▼
              ┌────────────────────────────────────────────────┐
              │  MarketFeed.get_candles(symbol, "M15", 200)     │
              │  MarketFeed.get_candles(symbol, "H4", 100)      │
              │  MarketFeed.get_candles(symbol, "M5", 100)      │
              │  MarketFeed.get_current_spread(symbol)          │
              └────────────┬───────────────────────────────────┘
                           │ feed error
                           ▼
                    [SKIP SYMBOL — warning]
                           │ OK
                           ▼
              ┌────────────────────────────────────────────────┐
              │  Bar count guard: len(m15) < 30                 │
              └────────────┬───────────────────────────────────┘
                           │ < 30
                           ▼
                    [SKIP SYMBOL — debug]
                           │ >= 30
                           ▼
              ┌────────────────────────────────────────────────┐
              │  Update open paper trades at current price      │
              │  PaperExecution.update() → if closed:           │
              │    TradeJournal.log_trade(closed)               │
              └────────────────────────────────────────────────┘
                                   │
              ┌────────────────────▼───────────────────────────┐
              │  lb_signals(m15, symbol)  ← LondonBreakout       │
              │  [same core logic as Path A]                    │
              │  Returns list[AdaptiveSignal]                   │
              └────────────────────┬───────────────────────────┘
                                   │ (combined with other strategies)
              ┌────────────────────▼───────────────────────────┐
              │  Build context dict:                            │
              │  htf_bias = _derive_htf_bias(h4)               │
              │    (last close vs 20-bar mean, ±0.1% threshold) │
              │  utc_hour = datetime.now(UTC).hour              │
              │  spread_pips = spread (from feed)               │
              │  news_event = False (stub always safe)          │
              └────────────────────────────────────────────────┘
                                   │
              ┌────────────────────▼───────────────────────────┐
              │  For each signal in all_signals:                │
              │  trade_router.route_signal(signal, m15,         │
              │    context, risk_state, dry_run=True)           │
              └────────────────────────────────────────────────┘
                                   │
              ┌────────────────────▼───────────────────────────┐
              │  Stage 1: detect_regime(m15, spread_pips)       │
              │  → TRENDING/BREAKOUT/RANGING/UNSAFE             │
              └────────────┬───────────────────────────────────┘
                           │ UNSAFE or not in {BREAKOUT,RANGING}
                           ▼
                    [REJECTED REGIME_BLOCKED / REGIME_MISMATCH]
                           │ OK regime
                           ▼
              ┌────────────────────────────────────────────────┐
              │  Stage 2: score_signal(signal, context)         │
              │  Scoring: structure(2) + session(1) +           │
              │  spread(1) + volatility(1) + news(1) +          │
              │  htf_bias(0 or 2) + liquidity(always 0)         │
              └────────────┬───────────────────────────────────┘
                           │ score < 7
                           ▼
                    [REJECTED SCORE_REJECTED]
                           │ score >= 7
                           ▼
              ┌────────────────────────────────────────────────┐
              │  Stage 3: risk_manager.check_risk(signal,       │
              │  risk_state, config)                            │
              │  Checks: halted | daily_loss | trade_count |    │
              │  consec_losses | correlation                    │
              └────────────┬───────────────────────────────────┘
                           │ not approved
                           ▼
                    [REJECTED RISK_BLOCKED]
                           │ approved + dry_run=True
                           ▼
              ┌────────────────────────────────────────────────┐
              │  APPROVED (dry_run)                             │
              │  TradeJournal.log_signal(sig, result)           │
              │  PaperExecution.open_trade(sig) → trade_id      │
              │  register_open_position(sig, state)             │
              │  StateStore.update(state)                       │
              └────────────────────────────────────────────────┘
```

---

## Modules Touched (London Breakout signal path)

| Module | Role | Path |
|--------|------|------|
| `adaptive/strategies/london_breakout_strategy.py` | Core signal generation | Both |
| `strategies/adapters/london_breakout_adapter.py` | AdaptiveSignal → core.Signal | Path A |
| `core/signal.py` | Signal dataclass | Path A |
| `core/signal_router.py` | TTL/geometry/conflict | Path A |
| `core/circuit_breaker.py` | Per-strategy rate limit | Path A |
| `core/portfolio_manager.py` | Portfolio limits | Path A |
| `execution/demo_risk_manager.py` | Lot calculation + limits | Path A |
| `execution/vantage_demo_executor.py` | Broker API wrapper | Path A |
| `execution/trade_manager.py` | Order placement | Path A (demo) |
| `strategies/shadow_tracker.py` | Shadow signal logging | Path A (shadow) |
| `core/trade_journal_db.py` | Persistent signal log | Path A |
| `execution/trade_journal.py` | Trade log | Path A |
| `adaptive/engine/trade_router.py` | Approval pipeline | Path B |
| `adaptive/engine/regime_detector.py` | ADX/ATR regime | Path B |
| `adaptive/engine/signal_scorer.py` | 0-10 point score | Path B |
| `adaptive/engine/risk_manager.py` | Intra-day risk state | Path B |
| `adaptive/filters/news_filter.py` | News stub | Path B |
| `adaptive/simulation/paper_execution.py` | Paper trade tracker | Path B |
| `adaptive/journal/trade_journal.py` | Signal/trade log | Path B |
| `adaptive/state/state_store.py` | Risk state persistence | Path B |
| `adaptive/data/market_feed.py` | Data abstraction | Path B |

---

## Decision Gates and Early Exits

| Gate | Condition | Effect |
|------|-----------|--------|
| Portfolio loss limit | any_loss_limit_hit() | Skip entire tick |
| Daily reset | new trading day | Reset risk counters |
| Spread > threshold | per-symbol max | Skip symbol entirely |
| Bar count < 50 (runner) | M15 bars < 50 | Skip symbol |
| Bar count < 30 (adapter) | M15 bars < 30 | Return None |
| No Asian bars | No M15 bars in 00-06 UTC | Return empty list |
| Range out of bounds | < 15 or > 50 pips | Return empty list |
| No breakout in London | No close beyond range | Return empty list |
| No retest | No qualifying retest candle | Return empty list |
| Risk <= 0 | Entry inside SL | Discard, continue |
| No raw signals | All strategies return empty | Skip routing |
| Regime UNSAFE | spread >= 3.0 or < 29 bars | REJECTED |
| Regime MISMATCH | Not BREAKOUT or RANGING | REJECTED |
| Score < 7 | Insufficient score | REJECTED |
| Risk blocked | Any of 5 risk checks fail | REJECTED |
| CircuitBreaker blocked | Rate/loss limit | REJECTED |
| PortfolioManager blocked | Portfolio limits | REJECTED |
| demo_risk_manager blocked | Execution-level limits | SKIP |
| DRY_RUN = True | Default | Simulated result, no real order |
| mode = live | run_portfolio.py | sys.exit(1) — blocked permanently |
# London Breakout Flow

1. Filter M15 candles into the Asian session.
1. Build the Asian high/low box.
1. Reject the day if the range is outside the allowed band.
1. Scan London-session bars in order.
1. Mark breakout direction on the first close beyond the Asian box.
1. Wait for a retest candle that touches the breakout area.
1. Build the signal at the retest close.
1. Reset the breakout state after a signal is emitted.
