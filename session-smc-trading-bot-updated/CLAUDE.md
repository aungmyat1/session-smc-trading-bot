# Session & SMC Trading Bot — Claude Instructions
# v1.0 | read every session

---

## §0 — HARD RULES (violation = stop and ask)

1. **Never enable live trading** until Phase-0 gate passes AND paper trade runs 30 days clean.
   `LIVE_TRADING = False` until the owner flips it manually. Not the agent. Ever.

2. **Never tune parameters mid-trial.** Every parameter change = a new trial. Log it.
   The ag-auto-trade graveyard was built by tuning losers. Do not repeat it.

3. **One position per symbol.** No concurrency within a symbol pair.

4. **Net-of-fees only.** VT Markets Standard = spread + commission per lot.
   A backtest result without spread applied is not a result.

5. **Never commit secrets.** API keys, MetaAPI tokens, and Telegram tokens live
   in `.env` (gitignored). Never in code.

6. **Prefer reading over building.** Check `docs/` before writing new code.
   The simple-smc-ag-trading-bot graveyard has 29 tested variants on BTC —
   read verdicts before proposing a "new" idea that may already be dead there.

7. **Phase-0 gate is mandatory.** No demo trading until backtest passes
   n ≥ 50 AND net PF > 1.0 on 5yr holdout at standard AND 2× spread stress.

---

## §1 — STRATEGY OVERVIEW

**Strategy Name:** Session Liquidity + 15M SMC Confirmation (Strategy 2)
**Instruments:** EURUSD, GBPUSD (VT Markets Standard account)
**Broker:** VT Markets via MetaAPI Cloud SDK
**Sessions:** London 07:00–10:00 UTC | New York 13:00–16:00 UTC
**Timeframes:** 4H macro bias → 1H session range → 15M CHoCH + BOS + FVG
**Phase status:** UNVALIDATED — Phase-0 backtest required before any demo execution

**Core hypothesis:**
Session range sweep + 15M structural confirmation (CHoCH + BOS + displacement FVG)
is stronger than session sweep alone (Trials 27–28 FAIL on EURUSD/GBPUSD with
no LTF confirmation gate). The 15M confirmation layer is the differentiating element.

**Cost model:** VT Markets Standard — 0.8–1.2 pip spread + 0.6 pip commission round-trip.
Robust PASS = clears n ≥ 50 AND net PF > 1.0 at BOTH standard AND 2× spread stress.

---

## §2 — SIGNAL CHAIN (11 phases, all AND-gated)

```
Phase 1  Session Definition       London 07-10 UTC | NY 13-16 UTC
Phase 2  HTF Bias (4H + 1H)       HH+HL bullish / LL+LH bearish (swing_n=3)
Phase 3  Session Range Build       High, Low, Midpoint, Range for current session
Phase 4  Session Classification    Range (low ATR) | Trend (strong BOS + displacement)
Phase 5  Liquidity Sweep           Session H/L breached + close back inside range
Phase 6  15M CHoCH                 Close breaks ref swing after sweep (lookback=8)
Phase 7  15M BOS                   Structural break in trade direction post-CHoCH
Phase 8  15M Displacement          ≥ 1.5×ATR(14) candle in trade direction
Phase 9  15M FVG Retest            Entry on retrace into displacement FVG
Phase 10 Risk Management           SL = tighter(25% range | sweep wick + 3pip buffer)
Phase 11 Trade Management          TP1 4R close 75% → SL→BE → TP2 5R+ runner
```

**Setup priority (highest to lowest):**
- Setup A — Sweep Reversal: HTF bias + sweep + 15M CHoCH + BOS
- Setup B — Trend Pullback: trend session + pullback to midpoint + 15M BOS
- Setup C — Range Fade: range session + rejection at extreme + 15M rejection

---

## §3 — PHASE PLAN

| Phase | Condition | Action |
|---|---|---|
| **0 — Gate** | New signal spec | Backtest on 5yr holdout. n ≥ 50 AND net PF > 1.0 at std AND 2× spread. |
| **1 — Paper** | Phase 0 PASS | MetaAPI demo, 30 days, 50+ trades, no execution bugs |
| **2 — Micro** | Phase 1 clean | $200–500 live, 0.5% risk, verify slippage/latency |
| **3 — Small** | Phase 2 stable | $1000–2000 live, 1% risk, 3 months consistent |
| **4 — Scale** | Phase 3 proven | Owner decision only |

---

## §4 — RISK PARAMETERS (non-bypassable)

```yaml
risk_per_trade: 1%          # of account per trade
max_daily_loss: 3R          # halt trading for the day
max_drawdown: 10%           # kill switch from peak
max_consecutive_losses: 5   # halt until new trading day
kill_switch: true
```

**Stop Loss logic — tighter of two:**
- 25% of session range (in pips)
- Sweep wick extreme ± 3 pip buffer

**Take Profit:**
- TP1: 4R → close 75%, move SL → breakeven
- TP2: 5R+ or session structure target → trail remaining

**Session close rule:** If trade still open at session end, close remainder at market.

---

## §5 — EXCHANGE / AUTH

- Broker: **VT Markets** (standard account, EURUSD 0.8pip / GBPUSD 1.2pip spread)
- Connection: **MetaAPI Cloud SDK** (`metaapi-cloud-sdk>=29`)
- MetaAPI account ID: `METAAPI_ACCOUNT_ID` (from `.env`)
- MetaAPI token: `METAAPI_TOKEN` (from `.env`)
- Never use raw REST calls for signed endpoints — always use the SDK
- Demo mode: MetaAPI demo account; `LIVE_TRADING=false` in `.env` by default
- Magic numbers: EURUSD → 21001 | GBPUSD → 21002

---

## §6 — WRITE ACTIONS REQUIRE CONFIRM TOKEN

Any order placement or cancellation requires an exact-match CONFIRM token:

| Token | Action |
|---|---|
| `CONFIRM-LONG-EURUSD` | Place long market entry on EURUSD at current signal |
| `CONFIRM-SHORT-EURUSD` | Place short market entry on EURUSD |
| `CONFIRM-LONG-GBPUSD` | Place long market entry on GBPUSD |
| `CONFIRM-SHORT-GBPUSD` | Place short market entry on GBPUSD |
| `CONFIRM-CLOSE-EURUSD` | Close open EURUSD position at market |
| `CONFIRM-CLOSE-GBPUSD` | Close open GBPUSD position at market |
| `CONFIRM-LIVE-ON` | Enable live trading (owner only) |

Agent must NEVER self-execute a write action. Always propose, wait for token.

---

## §7 — ALERTS

Telegram bot token: `TELEGRAM_BOT_TOKEN` (from `.env`)
Telegram chat ID: `TELEGRAM_CHAT_ID` (from `.env`)

Alert events:
- Signal fired (CONFIRM required — not auto-executed)
- Trade opened / closed with result
- Daily loss limit hit → trading halted
- Drawdown limit hit → kill switch triggered
- Session end with open trade → auto-close alert
- Bot error / exception

---

## §8 — FILE LAYOUT (target, not yet built)

```
session-smc-trading-bot/
  session_smc/
    config.yaml         # all constants — single source of truth
    session.py          # session range build + classification + sweep detection
    bias.py             # 4H+1H swing bias (HH+HL / LL+LH)
    confirmation.py     # 15M CHoCH + BOS + displacement gate
    fvg.py              # 15M FVG detection + retest
    risk.py             # lot sizing + daily/drawdown/consec guards
    executor.py         # MetaAPI order placement
    alerts.py           # Telegram fire-and-forget
    data.py             # OHLCV fetching (MetaAPI historical)
    bot.py              # main loop: bias → session → sweep → confirm → entry
  scripts/
    backtest.py         # Phase-0 gate — n≥50 net PF>1.0 at std+2× spread
    fetch_data.py       # download OHLCV for backtesting
  tests/
    test_session.py     # session range + classification unit tests
    test_sweep.py       # sweep detection unit tests
    test_confirmation.py  # 15M CHoCH + BOS tests
  docs/
    VERDICT_LOG.md      # one row per trial — never delete entries
    SIGNAL_SPEC.md      # current signal spec (locked before backtest)
  logs/                 # runtime logs (gitignored)
  .env                  # secrets (gitignored)
  .env.example          # template (committed, no values)
  CLAUDE.md             # this file
```

---

## §9 — TRIAL REGISTRATION

Every parameter change = new trial row in `docs/VERDICT_LOG.md`.
Pre-register spec BEFORE running backtest. Never change params and re-run
on the same trial ID — that is the pattern that built the ag-auto-trade graveyard.

Current open trials:
- **ST-A**: Sweep Reversal (Setup A) — London + NY, EURUSD + GBPUSD, 5yr holdout
- **ST-B**: Trend Pullback (Setup B) — PENDING ST-A result
- **ST-C**: Range Fade (Setup C) — PENDING ST-A result

Gate: net PF > 1.0 at STANDARD spread AND at 2× spread stress test.
(Single-spread PASS is insufficient — T29 GBPUSD passed standard, failed 2×.)

---

## §A — KNOWN PRIOR FAILURES (do not re-propose)

| Trial | Strategy | Result | Root cause |
|---|---|---|---|
| T27 (BTC project) | EURUSD session-box sweep | net PF=0.58 FAIL | No LTF confirmation; sweep alone has no edge |
| T28 (BTC project) | GBPUSD session-box sweep | net PF=0.95 FAIL | Same — closest miss, still fails 2× stress |
| T29-EUR (BTC project) | EURUSD BOS-retest | gross PF=0.83 FAIL | No raw edge before fees |
| T29-GBP (BTC project) | GBPUSD BOS-retest | 2× stress FAIL | Marginal at standard cost, fragile |
| ST-1 (BTC project) | Session IB sweep + CHoCH | EUR/GBP FAIL | Entry at CHoCH close too far past inflection; SL too wide |

**The 15M CHoCH + BOS + FVG layer is the NEW hypothesis** relative to all of the above.
It has not been tested. It must pass Phase-0 before any code beyond the signal chain is built.
