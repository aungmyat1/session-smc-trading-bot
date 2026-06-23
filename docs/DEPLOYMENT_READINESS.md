# DEPLOYMENT_READINESS.md
# DEP-01 — Demo Deployment Readiness
# Date: 2026-06-21

---

## Verdict

### READY FOR DEMO DEPLOYMENT — pending broker credentials

All code gates pass. Broker credentials (`METAAPI_TOKEN`, `METAAPI_ACCOUNT_ID`) must be
set in `.env` before starting `bot.py`. `LIVE_TRADING` remains `false` (owner flips only).

---

## Architecture

```
bot.py  (main loop, 60s poll)
  ├── MetaAPIClient      — broker connectivity (VT Markets demo via MetaAPI Cloud SDK)
  │     ├── connect() / disconnect()
  │     ├── get_account_info()    → equity, balance
  │     ├── get_symbol_price()    → bid/ask/spread_pips
  │     ├── check_spread()        → reject if > 3.0 pip EURUSD / 4.0 pip GBPUSD
  │     ├── get_candles()         → M15 + H4 OHLCV
  │     ├── get_open_positions()  → current open positions (filtered by magic)
  │     └── place_order()         → DRY_RUN when LIVE_TRADING=false
  │
  ├── run_strategy()     — ST-A2 signal chain (strategy/session_liquidity/)
  │     5yr backtest PASS: n=169, PF(2×)=1.025 @ RR5, min_sl_pips=5.0
  │
  ├── OrderManager       — signal validation → sizing → broker → log
  │     └── process_signal(signal, symbol, equity) → (success, detail)
  │
  ├── RiskManager        — circuit breakers + lot sizing guard
  │     State persisted in logs/bot_state.json
  │
  └── TradeLogger        — append-only JSONL to logs/trades.jsonl
        Events: SIGNAL_CREATED, ORDER_SUBMITTED, ORDER_FILLED,
                ORDER_REJECTED, POSITION_CLOSED, ERROR
```

**Signal dedup:** `seen_signals[symbol]` is a `set[str]` of `signal.timestamp.isoformat()`.
Each signal is processed at most once per bot run, regardless of how many polls return it.

**Health monitor:** heartbeat logged and sent via Telegram every 5 minutes.
Fields: timestamp, connected, live_trading, balance, open_positions.

---

## Order Flow

```
1  Signal produced by run_strategy(m15, h4, symbol)
2  Dedup check — skip if timestamp already seen
3  process_signal(signal, symbol, equity):
     a  SIGNAL_CREATED logged
     b  Circuit breakers checked (daily/weekly/consecutive limits)
     c  Spread checked — reject if too wide or unavailable
     d  Open positions checked — reject if MAX_OPEN_TRADES (1) reached
     e  Lot size calculated: (equity × 1%) / (sl_pips × pip_value_per_lot)
     f  ORDER_SUBMITTED logged
     g  place_order() → DRY_RUN when LIVE_TRADING=false
     h  ORDER_FILLED or ORDER_REJECTED logged
4  Telegram alert on success
```

---

## Risk Controls

| Control | Value | Source |
|---|---|---|
| Risk per trade | 1% equity | RISK_SPEC.md |
| Max open trades (per magic) | 1 | ORDER_MANAGER.MAX_OPEN_TRADES |
| Max SL width | 50 pip | position_sizer._MAX_SL_PIPS |
| Min SL width | 3 pip | position_sizer._MIN_SL_PIPS |
| Min SL width (strategy) | 5 pip | ST-A2 min_sl_pips in DEFAULT_CONFIG |
| Max daily loss | 3R | config.json risk.max_daily_loss_r |
| Max weekly loss | 8R | config.json risk.max_weekly_loss_r |
| Max consecutive losses | 5 | config.json risk.max_consecutive_losses |
| Drawdown kill switch | 10% from peak | RISK_SPEC.md (manual reset) |
| Max spread — EURUSD | 3.0 pip | metaapi_client._MAX_SPREAD_PIPS |
| Max spread — GBPUSD | 4.0 pip | metaapi_client._MAX_SPREAD_PIPS |
| Session-end close | automatic | bot._close_session_positions() |

**LIVE_TRADING gate:** `LIVE_TRADING=false` in `.env`. Agent never changes this.
Owner changes it manually only, after 30-day paper trade passes.

---

## Failure Modes

| Failure | Behaviour |
|---|---|
| MetaAPI connect fails | RuntimeError raised at startup → bot exits cleanly, Telegram error sent |
| Connection drops mid-run | `get_candles()` returns `[]`, scan skipped; next poll retries |
| Spread too wide (news/weekend) | `check_spread()` returns False → ORDER_REJECTED logged |
| Market closed | Session filter returns None → bot sleeps until next session |
| Circuit breaker triggered | `check_circuit_breakers()` returns halted → sleep, retry next poll |
| Order rejected by broker | Exception caught → ORDER_REJECTED + ERROR logged; bot continues |
| Position already open | `get_open_positions()` count ≥ 1 → ORDER_REJECTED; no re-entry |
| SL outside valid range | `calculate_lots()` returns `valid=False` → ORDER_REJECTED |
| Telegram fails | Non-fatal: logged but does not halt the bot |

---

## Recovery Procedures

**Bot restart (planned):**
1. `RiskManager` reloads state from `logs/bot_state.json` (daily/weekly counters preserved)
2. `seen_signals` is reset — bot will re-evaluate live signals on next fetch
3. Open positions reloaded from broker via `get_open_positions(magic=...)`
4. No re-entry for any pair already at MAX_OPEN_TRADES (1)

**Connection lost mid-trade:**
- Existing orders are broker-managed (SL/TP set on the order)
- Bot reconnects on next poll attempt
- Position is still protected by broker-side SL; no orphan risk

**Circuit breaker triggered:**
- State persisted in `logs/bot_state.json`
- Auto-resets: daily (MAX_DAILY_LOSS) and weekly (MAX_WEEKLY_LOSS) on schedule
- Consecutive losses: reset after next win or daily reset
- Kill switch (10% DD): requires owner to set `KILL_SWITCH_OVERRIDE=true` in `.env`

---

## Manual Shutdown Procedure

```bash
# 1. Stop the bot process
kill $(pgrep -f "python3 bot.py")

# 2. Verify no open positions remain (check MetaAPI dashboard or broker terminal)
# 3. If positions are open: close manually from broker platform (VT Markets)
# 4. Archive the trade log
cp logs/trades.jsonl logs/archive/trades_$(date +%Y%m%d).jsonl

# 5. Check circuit breaker state
cat logs/bot_state.json
```

For emergency stop with open positions: close all manually from the VT Markets
web terminal. The bot's DRY_RUN mode means all orders in Phase-1 are simulated
anyway — there are no real positions to close until `LIVE_TRADING=true`.

---

## Pre-Flight Checklist

Before starting `python3 bot.py`:

```
[ ] .env contains: METAAPI_TOKEN, METAAPI_ACCOUNT_ID, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
[ ] .env LIVE_TRADING=false  (confirm before EVERY run)
[ ] VT Markets demo account active and deployed in MetaAPI dashboard
[ ] logs/ directory writable
[ ] config/config.json pairs = ["EURUSD", "GBPUSD"]
[ ] python3 -m pytest → 610/610 passing
[ ] Telegram bot reachable (send test message)
```

---

## Files Produced — DEP-01

| File | Lines | Purpose |
|---|---|---|
| `execution/metaapi_client.py` | 233 | MetaAPI broker connectivity |
| `execution/position_sizer.py` | 103 | Lot sizing from risk model |
| `execution/trade_logger.py` | 107 | Append-only JSONL event log |
| `execution/order_manager.py` | 148 | Order flow orchestration |
| `bot.py` | 194 | Main loop wired to ST-A2 |
| `tests/test_metaapi_client.py` | — | 19 tests (6 categories) |
| `tests/test_position_sizer.py` | — | 16 tests (4 categories) |
| `tests/test_trade_logger.py` | — | 15 tests (4 categories) |
| `tests/test_order_manager.py` | — | 16 tests (6 categories) |

**Test count added:** 66 new tests (544 → 610 total)

---

## Success Criteria (from task spec)

| Criterion | Status |
|---|---|
| 1. Connects to demo account | Ready — requires `.env` credentials to verify live |
| 2. Can place and cancel test orders | DRY_RUN verified; live verify needs credentials |
| 3. Position sizing matches risk model | ✅ 16 position_sizer tests pass |
| 4. No duplicate orders | ✅ MAX_OPEN_TRADES=1 enforced + 4 tests |
| 5. Logs all trade lifecycle events | ✅ All 6 JSONL event types tested |
| 6. Runs 7 consecutive days without errors | Pending demo run |

---

## Remaining Blockers

1. **Broker credentials** — `METAAPI_TOKEN` + `METAAPI_ACCOUNT_ID` must be populated in `.env`.
   Obtain from MetaAPI dashboard at https://app.metaapi.cloud → Accounts.

2. **VT Markets demo account** — must be deployed and connected in MetaAPI dashboard
   before bot.py can reach the broker.

3. **7-day clean run** — the final success criterion. No blockers in the code;
   all code-level checks pass. Monitoring required during the run.

*DEP-01 | Date: 2026-06-21*
