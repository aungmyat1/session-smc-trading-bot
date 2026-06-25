# DEPLOYMENT CHECKLIST — Session SMC Trading Bot
# Demo → Live gate. Every item must be checked before flipping LIVE_TRADING=true.
# Last updated: 2026-06-20

---

## SECTION A — PHASE-0 GATE (Backtest)
Must pass before ANY demo execution.

- [ ] A-01  `scripts/backtest.py` built and reviewed
- [ ] A-02  `scripts/fetch_data.py` downloads 5yr EURUSD+GBPUSD H1/H4 data
- [ ] A-03  ST-A pre-registered in `docs/VERDICT_LOG.md` with locked params before run
- [ ] A-04  `docs/SIGNAL_SPEC.md` locked (no param change allowed after this point)
- [ ] A-05  Backtest uses bar-close execution only (no open-of-next-bar fill)
- [ ] A-06  Backtest applies full RT cost: spread + 0.6pip commission per SIGNAL_SPEC.md cost model
- [ ] A-07  Backtest applies 2× spread stress test as second pass
- [ ] A-08  ST-A result logged in VERDICT_LOG.md: n ≥ 50 AND net PF > 1.0 at std AND 2× spread
- [ ] A-09  ST-A verdict: **PASS** (any FAIL = strategy redesign, new trial ID, restart from A-01)

---

## SECTION B — STRATEGY IMPLEMENTATION
Required for Phase-0 to produce a valid result. Implement in order.

- [ ] B-01  `session_smc/bias.py` — 4H + 1H HH+HL / LL+LH detection (swing_n=3, bar-close only)
- [ ] B-02  `session_smc/session.py` — session range build (H/L from first 2H candles), classification
- [ ] B-03  `session_smc/session.py` — liquidity sweep detection (break + close-back-inside AND gate)
- [ ] B-04  `session_smc/confirmation.py` — 15M CHoCH (lookback=8 bars before sweep)
- [ ] B-05  `session_smc/confirmation.py` — 15M BOS (prior confirmed swing break)
- [ ] B-06  `session_smc/confirmation.py` — displacement candle gate (range ≥ 1.5×ATR(14))
- [ ] B-07  `session_smc/fvg.py` — 3-bar FVG detection; invalidation on close-through
- [ ] B-08  `session_smc/fvg.py` — FVG retest entry (limit at midpoint or market-on-retest-close)
- [ ] B-09  `session_smc/session.py` — session ≥ 2H remaining gate before entry
- [ ] B-10  All indicators use bar-close data (`candles[-1]` = last closed bar, not forming)
- [ ] B-11  Candles sorted ascending by time and deduplicated before any indicator calculation
- [ ] B-12  4H candle fetch uses ≥ 250 count to pre-warm EMA200
- [ ] B-13  Unit tests: `tests/test_session.py`, `tests/test_sweep.py`, `tests/test_confirmation.py`

---

## SECTION C — EXECUTION LAYER FIXES
Required before demo launch.

- [ ] C-01  `risk.record_trade_result()` called after every position close (in session-close loop
           and in active position management callback)
- [ ] C-02  Max drawdown (10% from equity peak) implemented in `RiskManager`:
           - `equity_peak` tracked in `BotState`
           - Updated on each account-info poll
           - Halt + Telegram alert when `(peak - equity) / peak > 0.10`
- [ ] C-03  Max drawdown config key added to `config.json`
- [ ] C-04  Active position management loop implemented:
           - Poll open positions every N seconds
           - Detect TP1 (4R) hit → close 75% of volume → set SL = entry
           - Detect TP2 (5R) hit → close remainder
           - Detect session end → close remainder at market
- [ ] C-05  `MT5Executor.connect()` has reconnection loop with exponential backoff
- [ ] C-06  Connection health check before each API call (check `synchronized` state)
- [ ] C-07  Startup reconciliation: on connect, fetch open bot positions by magic number;
           log + re-arm management state for any found
- [ ] C-08  Session-close loop has per-position try-except; failure sends Telegram alert
           and continues to next position (does not abort the entire close loop)
- [ ] C-09  `get_open_positions()` in main loop filters by bot magic numbers only
           (prevents manual trades from counting toward bot's position limits)
- [ ] C-10  Duplicate signal prevention: track `last_signal_bar_time[symbol]`;
           skip if current 15M candle already produced a signal
- [ ] C-11  Circuit breaker halt sends Telegram alert via `send_circuit_breaker()`
- [ ] C-12  `TradeJournal` updated at trade close with `exit_price`, `result_r`, `reason`
- [ ] C-13  Pending order (limit) management OR explicit decision to use market-on-retest-close
           documented in SIGNAL_SPEC.md

---

## SECTION D — RISK CONTROLS VERIFICATION
Run before flipping to demo.

- [ ] D-01  Simulate 3× daily losses on paper account → bot halts for the day → verified
- [ ] D-02  Simulate 5× consecutive losses → consecutive-loss halt triggers → verified
- [ ] D-03  Simulate equity drawn down 10% → kill switch fires → verified
- [ ] D-04  Simulate bot restart mid-day with existing daily losses → state reloads correctly
           from `logs/bot_state.json`; daily loss counter not reset mid-day
- [ ] D-05  Simulate session end with 1 open position → position closed at market → verified
- [ ] D-06  Manual trade open on same MT5 account → bot position limits NOT affected
           (magic-number filtering working, C-09)
- [ ] D-07  Lot sizing verified: balance=$500, SL=20pip, EURUSD → expected lot confirmed
           (formula: risk_amount / (sl_pips × pip_value) = $2.50 / $200 = 0.01 lot minimum)
- [ ] D-08  max_lot cap enforced; no order exceeds 10.0 lots regardless of account size

---

## SECTION E — MONITORING & ALERTING
Required before demo launch.

- [ ] E-01  Telegram `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` configured in `.env`
- [ ] E-02  Startup message received in Telegram when bot starts in DEMO mode
- [ ] E-03  Session open / close alerts received at correct UTC times
- [ ] E-04  Telegram alert received when circuit breaker triggers (daily/weekly/consec/drawdown)
- [ ] E-05  Telegram alert received on fatal exception
- [ ] E-06  4-hour heartbeat message implemented and confirmed (with: uptime, balance, open positions)
- [ ] E-07  All logs written to `logs/bot.log` and Docker-volume-mounted (survive container restart)
- [ ] E-08  Trade journal `logs/trades.jsonl` records entries AND exits correctly
- [ ] E-09  `journal.get_all_stats()` returns correct win rate and total_r after test trades

---

## SECTION F — DEMO PHASE (30-Day Run, ≥50 Trades)
Phase-1 requirements before any live capital.

- [ ] F-01  MetaAPI demo account connected (not live account)
- [ ] F-02  `LIVE_TRADING=false` in `.env` confirmed before start
- [ ] F-03  Bot runs for 30 consecutive calendar days without crash
- [ ] F-04  ≥ 50 trades executed (not signals — actual demo fills)
- [ ] F-05  Zero execution bugs: correct SL/TP placement, correct lot sizing, correct session close
- [ ] F-06  Circuit breakers trigger correctly on at least one real-money-equivalent bad streak
- [ ] F-07  TP1 partial close and breakeven SL move executed correctly on at least 5 trades
- [ ] F-08  Trade journal results match MetaAPI trade history (manual spot-check 10 trades)
- [ ] F-09  No orphan positions after any bot restart during the demo period
- [ ] F-10  Net PF over 30-day demo: > 1.0 (sanity check; not the primary gate, but a red flag if < 1.0)
- [ ] F-11  Demo verdict logged in `docs/VERDICT_LOG.md` as ST-A-DEMO

---

## SECTION G — PRE-LIVE FINAL CHECKS
Run on the day of live flip.

- [ ] G-01  Confirm MetaAPI account ID in `.env` is the LIVE account (not demo)
- [ ] G-02  Confirm VT Markets Standard account funded with ≥ $200
- [ ] G-03  Confirm `risk_per_trade_pct = 0.5` (micro phase — half of normal risk)
- [ ] G-04  Confirm `max_lot = 0.5` (cap lot size for micro phase)
- [ ] G-05  Confirm Telegram alerts working on live account credentials
- [ ] G-06  Confirm `.env` is NOT committed to git (check `git status`)
- [ ] G-07  Docker image rebuilt from clean state; container tested with `docker-compose up`
- [ ] G-08  VPS uptime monitoring configured (e.g., UptimeRobot pinging the VPS)
- [ ] G-09  Owner has read and accepted current drawdown from peak is 0% (fresh start)
- [ ] G-10  Owner manually sets `LIVE_TRADING=true` in `.env` — no agent, no script does this

---

## SIGN-OFF

| Gate | Owner sign-off | Date |
|------|----------------|------|
| Phase-0 backtest PASS (A-09) | | |
| Execution fixes complete (C-01 to C-13) | | |
| Demo phase PASS (F-01 to F-11) | | |
| Pre-live checks complete (G-01 to G-10) | | |
| **LIVE_TRADING=true authorized** | | |

> "Never enable live trading until Phase-0 gate passes AND paper trade runs 30 days clean.
>  LIVE_TRADING = False until the owner flips it manually. Not the agent. Ever."
>  — CLAUDE.md §0 Rule 1
