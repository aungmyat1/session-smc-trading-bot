# Asian-Session Strategy — Fully-Auto Deployment Runbook v2
### For the `session-smc-trading-bot` repo · VPS agent (Claude Code)
### Instruments: EURUSD · GBPUSD · XAUUSD · Broker: Vantage MT5 via MetaAPI

This runbook upgrades the original single-session, single-instrument Asian-session
bot into a **multi-session × multi-instrument signal engine** that targets **2–3
quality trades per day** across EURUSD, GBPUSD, and XAUUSD. Signal logic is
session-aware (Asian / London / New York / London-NY Overlap) and instrument-aware
(forex pip math vs. XAUUSD point math). Execution routes through MetaAPI to
Vantage MT5, replacing the Bybit SDK entirely.

Each numbered block is a self-contained prompt to paste into Claude Code on the
VPS, in order. All blocks respect your CLAUDE.md rules: propose-only, CONFIRM
tokens for writes, never self-enable live trading, one trial per change.

---

## What changed from v1 and why

| v1 (original) | v2 (this runbook) |
|---|---|
| Single instrument (BTC assumed) | EURUSD, GBPUSD, XAUUSD |
| Asian session only (00:00–08:00) | 4 sessions scanned per cycle |
| ~0–1 signal/day | Target 2–3 signals/day |
| Bybit SDK | MetaAPI → Vantage MT5 |
| Single sweep_beyond_pct global | Per-instrument pip/point config |
| P5 pass: net PF > 1.0, n ≥ 50 | P5 pass: net PF ≥ 1.4, n ≥ 100, win% ≥ 35%, max consec. loss ≤ 8 |
| No per-session management rules | Session-specific management baked in |

---

## How 2–3 trades/day is achieved

The bot scans **4 session windows × 3 instruments = up to 12 signal opportunities**
per day. Quality gates (HTF bias, session classification, sweep detection) reduce
this to a realistic 2–3 confirmed setups:

- **Asian (00:00–08:00 UTC):** Best on EURUSD and GBPUSD. Range/sweep setups.
  XAUUSD included but signal weight lower (gold often trends through Asia).
- **London (07:00–12:00 UTC):** All three instruments active. Best session for
  EURUSD/GBPUSD breakout and sweep signals. XAUUSD London open is a strong
  directional window.
- **London-NY Overlap (12:00–15:00 UTC):** Highest liquidity. All three.
  Trend continuation setups dominate. One additional trade most days.
- **New York (12:00–17:00 UTC):** XAUUSD primary (gold NY session very active).
  EURUSD/GBPUSD secondary (fade NY extension). Overlap included, standalone NY
  scanned separately for late-session XAUUSD trend.

One-position-per-instrument rule applies (not global one-position). The bot can
hold EURUSD + XAUUSD simultaneously, but never two EURUSD trades at once.

---

## Instrument config reference (baked into all prompts below)

```yaml
instruments:
  EURUSD:
    symbol: "EURUSD"          # MetaAPI symbol string
    pip_size: 0.0001
    atr_period: 14
    sweep_beyond_pct: 0.008   # 0.8 pip beyond box extreme
    sl_pct_of_range: 0.25
    spread_allowance_pips: 1.0
    sessions: [asian, london, overlap, newyork]
    signal_weight: 1.0

  GBPUSD:
    symbol: "GBPUSD"
    pip_size: 0.0001
    atr_period: 14
    sweep_beyond_pct: 0.010   # GBP wider spread, needs more confirmation
    sl_pct_of_range: 0.25
    spread_allowance_pips: 1.5
    sessions: [london, overlap, newyork]  # skip Asian — too thin
    signal_weight: 0.9

  XAUUSD:
    symbol: "XAUUSD"
    pip_size: 0.01            # gold point = $0.01
    atr_period: 14
    sweep_beyond_pct: 0.005   # 50 cents beyond box extreme
    sl_pct_of_range: 0.20     # tighter stop — gold range wider in $ terms
    spread_allowance_pips: 3.0
    sessions: [london, overlap, newyork]  # skip Asian for gold
    signal_weight: 1.0
```

> **GBPUSD in Asian session is excluded.** Spread/ATR ratio during Asian hours
> on GBP makes the edge marginal; London open is where GBP finds direction.

---

## Session window reference

```yaml
sessions:
  asian:
    start_h: 0
    end_h: 8
    label: "Asian"
    range_thr: 0.50     # range/ATR < 0.50 → RANGE session
    trend_thr: 0.70     # range/ATR > 0.70 → TREND session
    first_close_target: "opposite_box_edge"
    first_close_pct: 0.75
    trail_remainder: false

  london:
    start_h: 7
    end_h: 12
    label: "London"
    range_thr: 0.55
    trend_thr: 0.75
    first_close_target: "opposite_box_edge"
    first_close_pct: 0.75
    trail_remainder: false

  overlap:
    start_h: 12
    end_h: 15
    label: "Overlap"
    range_thr: 0.60
    trend_thr: 0.80
    first_close_target: "4R"
    first_close_pct: 0.75
    trail_remainder: true   # overlap trends run further

  newyork:
    start_h: 12
    end_h: 17
    label: "NewYork"
    range_thr: 0.55
    trend_thr: 0.75
    first_close_target: "opposite_box_edge"
    first_close_pct: 0.75
    trail_remainder: false
```

---

## P0 — Sync + safety baseline
```
Read CLAUDE.md in full, then git pull and run `pytest -q`.

Report ALL of the following — do NOT change anything yet:
1. signal_only_mode, LIVE_TRADING, and demo flag values in config + .env
2. MetaAPI connection status (can you reach the MetaAPI SDK? is the account token
   set in .env?)
3. Current htf/ltf timeframe pairs in config.yaml
4. Whether any Bybit SDK imports exist in bot.py, executor.py, or any other module
   (we will replace these with MetaAPI calls)
5. pytest result — pass/fail/count

Just report. No edits.
```

---

## P0.5 — MetaAPI broker migration (Bybit → Vantage MT5)
```
PROPOSE ONLY — do not commit until CONFIRM-COMMIT-METAAPI.

Replace all Bybit SDK references with MetaAPI calls to Vantage MT5. Specifically:

1. Create smc_bot/broker/metaapi_executor.py:
   - connect(): initialise MetaApi(token=cfg['metaapi']['token']),
     await api.metatrader_account_api.get_account(cfg['metaapi']['account_id']),
     deploy and wait_connected with timeout_in_seconds=300.
   - place_market_order(symbol, side, volume, sl, tp, comment): use
     connection.create_market_buy_order / create_market_sell_order with stopLoss
     and takeProfit in price terms (not pips). Log the returned positionId.
   - place_limit_order(symbol, side, volume, price, sl, tp, comment): use
     create_limit_buy_order / create_limit_sell_order.
   - place_reduce_only_limit(symbol, side, volume, price, comment): partial close
     via connection.close_position_partially(positionId, volume).
   - set_sl(positionId, new_sl): connection.modify_position(positionId,
     stopLoss=new_sl).
   - get_open_positions(): connection.get_positions() — return list filtered to
     this account.
   - close_position(positionId): connection.close_position(positionId).

2. Update smc_bot/risk.py calc_qty() for forex lot sizing:
   - For EURUSD/GBPUSD: lots = risk_usd / (sl_pips * pip_value_per_lot)
     where pip_value_per_lot = 10.0 for standard lot (USD account).
   - For XAUUSD: lots = risk_usd / (sl_points * point_value_per_lot)
     where point_value_per_lot = 1.0 (1 point = $1 per 0.01 lot on gold, scale
     accordingly). Min lot 0.01, max lot from cfg['risk']['max_lots_per_symbol'].
   - Round to 2 decimal places (MetaAPI/MT5 requirement).

3. Add to config.yaml:
   metaapi:
     token: ""              # populated from .env METAAPI_TOKEN
     account_id: ""         # populated from .env METAAPI_ACCOUNT_ID
     demo: true             # true = demo MT5 account; false = live
     deploy_timeout: 300

4. Add to .env.example:
   METAAPI_TOKEN=your_token_here
   METAAPI_ACCOUNT_ID=your_account_id_here

5. Delete or stub out smc_bot/broker/bybit_executor.py (rename to
   bybit_executor.py.disabled so git history is preserved, don't delete).

6. Update any import in bot.py from bybit_executor to metaapi_executor.

Add tests/test_metaapi_executor.py using unittest.mock to patch the MetaAPI SDK
— no real network calls in tests. Run pytest. Show me the full diff.
Do NOT commit until CONFIRM-COMMIT-METAAPI.
```

---

## P1 — Build the multi-session signal module
```
PROPOSE ONLY — do not commit until CONFIRM-COMMIT-SESSION.

Create smc_bot/session_range.py. It may import ONLY structure, liquidity,
tp_engine, and the instrument/session config dicts — no broker SDK — so it passes
tests/test_ast_guard.py.

Implement these functions:

─── A. Session box builder ───────────────────────────────────────────────────

def build_session_box(df_1h: pd.DataFrame, start_h: int, end_h: int) -> dict:
    """
    Filter df_1h to candles whose hour (UTC) falls in [start_h, end_h).
    Return:
      box_high  = max(high) of session candles
      box_low   = min(low)  of session candles
      box_range = box_high - box_low
      atr       = ATR(14) computed on the full df_1h passed in
    Raise ValueError if fewer than 3 candles found (session not yet complete).
    """

─── B. Session classifier ────────────────────────────────────────────────────

def classify_session(box: dict, session_cfg: dict) -> str:
    """
    ratio = box['box_range'] / box['atr']
    Return 'range'  if ratio < session_cfg['range_thr']
    Return 'trend'  if ratio > session_cfg['trend_thr']
    Return 'neutral' otherwise
    """

─── C. Sweep detector ────────────────────────────────────────────────────────

def detect_sweep(df_1h: pd.DataFrame, box: dict, instr_cfg: dict
                 ) -> dict | None:
    """
    Scan candles AFTER the session window closes (index > end_h candle).
    A sweep is valid when:
      - A candle wick exceeds box_high by >= sweep_beyond_pct * box_range
        (HIGH sweep) OR wick goes below box_low by the same threshold (LOW sweep)
      - AND the candle CLOSES back inside the box
    Return {'direction': 'high'|'low', 'candle': row} for the FIRST sweep found.
    Return None if no sweep detected.
    IMPORTANT: 'high' sweep → price swept liquidity above → bias SHORT (smart
    money reversal). 'low' sweep → bias LONG.
    """

─── D. Master signal builder ─────────────────────────────────────────────────

@dataclass
class SessionSignal:
    instrument: str       # "EURUSD" | "GBPUSD" | "XAUUSD"
    session:    str       # "asian" | "london" | "overlap" | "newyork"
    setup:      str       # "sweep" | "range" | "trend"
    side:       str       # "long" | "short"
    entry:      float
    sl:         float
    tp:         float
    box_high:   float
    box_low:    float
    mgmt:       dict      # {first_close_pct, first_close_target, trail}

def build_session_signal(
    df_4h: pd.DataFrame,
    df_1h: pd.DataFrame,
    instrument: str,
    session_name: str,
    cfg: dict
) -> SessionSignal | None:
    """
    1. HTF bias gate: structure.get_bias(df_4h). If 'neutral' → return None.
    2. Build session box from df_1h + session window.
    3. Classify session.
    4. Detect sweep (always check regardless of classification).
    5. Route:
         sweep detected:
           side = 'short' if sweep.direction == 'high' else 'long'
           entry = sweep candle close (body back inside box)
           sl    = box_high + sl_pct_of_range * box_range  (for short)
                   box_low  - sl_pct_of_range * box_range  (for long)
           tp    = entry - (entry - sl) * target_r         (for short)
           setup = 'sweep'

         session == 'range' and no sweep:
           long if HTF bias bullish: entry = box_low, sl below box_low, tp = 5R
           short if HTF bias bearish: entry = box_high, sl above box_high, tp = 5R
           setup = 'range'

         session == 'trend':
           long if bullish: entry = box midpoint on 1h pullback (LTF retest)
           short if bearish: same inverted
           sl = entry ± sl_pct_of_range * box_range
           setup = 'trend'

         session == 'neutral' and no sweep → return None

    6. Validate spread: if (entry - box_low) / instr_cfg['pip_size'] <
       instr_cfg['spread_allowance_pips'] → return None (entry too close to
       current spread, not worth it).

    7. Build mgmt dict from session_cfg: {first_close_pct, first_close_target,
       trail_remainder}.

    8. Call tp_engine.build_plan(entry, sl, target_r) for R math.

    9. Return SessionSignal(...).
    """

─── E. Multi-instrument scanner ─────────────────────────────────────────────

def scan_all(data: dict, cfg: dict, utc_now: datetime) -> list[SessionSignal]:
    """
    data = {'EURUSD': {'df_4h': ..., 'df_1h': ...}, 'GBPUSD': {...}, ...}
    For each instrument in cfg['instruments']:
      For each session in instr_cfg['sessions']:
        If utc_now.hour >= session_cfg['end_h']:  # session box is complete
          sig = build_session_signal(...)
          if sig: signals.append(sig)
    Return signals sorted by signal_weight DESC (from instr_cfg).
    Cap at cfg['risk']['max_concurrent_signals'] (default 3) to prevent
    signal flood.
    """

─── Tests ───────────────────────────────────────────────────────────────────

Add tests/test_session_range.py covering:
  - Asian EURUSD sweep long and short (synthetic df)
  - London GBPUSD range short (neutral HTF → None)
  - Overlap XAUUSD trend long
  - GBPUSD excluded from Asian session (sessions list gate)
  - XAUUSD excluded from Asian session
  - scan_all cap at max_concurrent_signals=2 returns only top 2

Run pytest. Show me the full diff. Do NOT commit until CONFIRM-COMMIT-SESSION.
```

---

## P2 — Config: instruments + sessions block
```
PROPOSE ONLY — do not commit until CONFIRM-COMMIT-CONFIG.

In smc_bot/config.yaml make these additions. Do NOT change any existing key that
controls the live smc_sniper path.

1. Add top-level switch:
   signal_source: smc_sniper   # values: smc_sniper | asian_session
                                # asian_session activates multi-instrument loop

2. Add instruments block (full spec from the runbook header).

3. Add sessions block (full spec from the runbook header).

4. Add to risk block:
   risk:
     max_concurrent_signals: 3      # max signals from scan_all per cycle
     max_lots_per_symbol: 1.0       # hard cap regardless of risk_usd calc
     max_open_positions: 3          # one per instrument max
     max_daily_loss_usd: 150        # bot stops new signals if hit
     risk_pct_per_trade: 0.01       # 1% of balance per trade (used if
                                    # risk_usd not set; MetaAPI balance query)

5. Add metaapi block (tokens empty, populated from .env):
   metaapi:
     token: ""
     account_id: ""
     demo: true
     deploy_timeout: 300

Show me the full diff. Do NOT commit until CONFIRM-COMMIT-CONFIG.
```

---

## P3 — Wire multi-instrument scanner into the run loop
```
PROPOSE ONLY — do not commit until CONFIRM-COMMIT-WIRING.

In smc_bot/bot.py run_cycle():

1. Read cfg['signal_source'].

2. When signal_source == 'asian_session':
   a. Fetch df_4h and df_1h for EACH instrument in cfg['instruments'] via
      MetaAPI connection.get_history_deals / get_candles (or equivalent). Store
      in data dict keyed by symbol.
   b. Call session_range.scan_all(data, cfg, utc_now=datetime.utcnow()).
      This returns up to max_concurrent_signals SessionSignal objects.
   c. For each signal:
      - Check one-position-per-instrument: if a position already exists for
        signal.instrument → skip (do NOT skip other instruments).
      - Check max_open_positions: if total open positions >= limit → skip all.
      - Check max_daily_loss_usd: query today's closed P&L from MetaAPI; if
        loss exceeds limit → skip all and log "DAILY LOSS LIMIT HIT".
      - Call risk.calc_qty(signal, cfg, account_balance) → lots.
      - Call metaapi_executor.place_market_order(signal.instrument, signal.side,
        lots, signal.sl, signal.tp, comment=f"{signal.session}_{signal.setup}").
      - Log: instrument, session, setup, side, entry, sl, tp, lots, positionId.

3. When signal_source == 'smc_sniper' (default) → behave exactly as today.
   Do NOT touch that path.

4. Do NOT duplicate risk/log code. Factor a _execute_signal(sig, cfg, conn)
   helper that both paths can call if needed.

Add a test mocking scan_all returning 2 signals with one duplicate instrument
— verify only one order placed per instrument. Run pytest. Show me the diff.
Do NOT commit until CONFIRM-COMMIT-WIRING.
```

---

## P4 — Session-specific position management (75% / 4R / trail)
```
PROPOSE ONLY — do not commit until CONFIRM-COMMIT-MGMT.

Extend bot.py manage_open_positions() so that when signal_source ==
'asian_session', each open MT5 position is managed using the mgmt dict stored
in its comment/metadata:

1. On each run_cycle, for each open position placed by the asian_session path
   (identify by comment prefix containing session/setup string):

   a. Retrieve current price from MetaAPI connection.get_symbol_price(symbol).
   b. Compute R-distance: r = (current_price - entry) / (entry - sl)  [long]
      or (entry - current_price) / (sl - entry)  [short].

   SWEEP / RANGE management:
   c. If first_close not yet done AND price has reached opposite box edge:
      - place_reduce_only (close first_close_pct of volume at market).
      - set_sl(positionId, entry)  # move SL to breakeven
      - Mark first_close_done in position metadata (store in comment field or
        a local state file: data/position_state.json, keyed by positionId).

   TREND / OVERLAP management:
   d. If first_close not yet done AND r >= trend_first_close_r (4.0):
      - partial close first_close_pct.
      - set_sl to breakeven.
      - If trail_remainder: begin trailing SL at 1 ATR behind price.
      - Mark first_close_done.

   e. If first_close_done AND trail_remainder:
      - trail_sl = current_price - 1 * atr  (long) or + 1 * atr (short)
      - If trail_sl > current_sl (long) or < current_sl (short):
        set_sl(positionId, trail_sl).

2. State persistence: use data/position_state.json as a lightweight dict
   {positionId: {first_close_done: bool, entry: float, sl: float, setup: str,
   session: str, mgmt: dict}}. Load on startup, save after every mutation.
   If positionId disappears from MetaAPI (closed), remove from state file.

3. Gate everything behind signal_source == 'asian_session' check. The smc_sniper
   management path is untouched.

Add tests for both management branches (mock MetaAPI calls). Run pytest.
Show me the full diff. Do NOT commit until CONFIRM-COMMIT-MGMT.
```

---

## P5 — Backtest gate (Phase-0, non-negotiable)
```
PROPOSE ONLY — do not change any live config. Do NOT set asian.enabled or flip
signal_source. Do NOT commit results until CONFIRM-COMMIT-BACKTEST.

Adapt scripts/backtest.py to score the asian_session signal on a 2-year holdout
using historical 1h + 4h OHLC data for EURUSD, GBPUSD, and XAUUSD.

Data source: download from MetaAPI historical data API or from a local CSV if
already present in data/historical/. Save any downloaded data to
data/historical/{symbol}_1h.csv and data/historical/{symbol}_4h.csv so the
backtest is reproducible offline.

Fee model:
  EURUSD / GBPUSD: Vantage ECN spread avg 0.8 pip round-turn = 0.00008 per lot
  XAUUSD: avg spread 0.30 points round-turn = $0.30 per lot
  No commission (Vantage ECN included in spread estimate above).

For each instrument × session combination, run build_session_signal on every
completed session window in the 2-year period. Record:
  - signal count (n)
  - wins / losses (TP hit vs SL hit, accounting for partial close at first target)
  - gross P&L in R-multiples
  - net P&L after fees
  - gross PF, net PF, win%
  - max consecutive losses

Report a summary table:

| Instrument | Session  | n   | Win% | Net PF | Max ConsecLoss |
|------------|----------|-----|------|--------|----------------|
| EURUSD     | Asian    | ... | ...  | ...    | ...            |
| EURUSD     | London   | ... | ...  | ...    | ...            |
| ...        | ...      | ... | ...  | ...    | ...            |
| COMBINED   | ALL      | ... | ...  | ...    | ...            |

PASS criteria (ALL must be met on the COMBINED row):
  - net PF >= 1.4
  - n >= 100 trades total
  - win% >= 35%
  - max consecutive losses <= 8

If any instrument × session row has net PF < 1.0 AND n >= 30, flag it as
FAILING and recommend DISABLING that specific combination (not the whole system).

Append a verdict row to docs/VERDICT_LOG.md:
  | DATE | v2 multi-session | EURUSD+GBPUSD+XAUUSD | net_pf | n | win% | PASS/FAIL |

If COMBINED row FAILS: print "STOP — do not proceed to P6. Failing combinations:
[list]. Recommended action: [specific tuning suggestions]." and halt.
```

---

## P6 — Demo run on Vantage MT5 (fully-auto, no real money)
```
With P5 COMBINED verdict PASSED only — do not run this step otherwise.

Make these config changes and show me the diff:
  signal_source: asian_session
  metaapi.demo: true          # Vantage MT5 demo account
  LIVE_TRADING=false          # in .env
  signal_only_mode: false     # allow demo orders to be placed

Also disable any instrument × session rows flagged FAILING in P5 by setting
their enabled: false in the instruments block (add per-session enable flags
if not already present).

Show the systemd commands to restart the service. After I reply CONFIRM-DEMO-ON,
I will run them myself.

Then for 30 days (or 100+ trades, whichever comes first):
- Monitor the Telegram alert feed for entry/exit confirmations.
- Check data/position_state.json daily for stale positions.
- Flag immediately if: (a) a position is opened without a valid signal in logs,
  (b) lot sizing deviates from the risk calc by > 5%, (c) MetaAPI drops
  connection mid-trade and reconnection takes > 5 min.
- After 30 days, report: live net PF, live win%, avg slippage vs backtest entry,
  and any execution discrepancies.

Do NOT move to P7 unless live demo net PF >= 1.2 AND no critical execution bugs.
```

---

## P7 — Go live (OWNER ONLY — the agent must never do this)
```
Do NOT perform this step. Only describe what the OWNER does manually:

1. Confirm P5 PASS and P6 demo results (30 days, net PF >= 1.2).
2. Fund the Vantage MT5 LIVE account.
3. Edit .env: LIVE_TRADING=true
4. Edit config.yaml: metaapi.demo: false
5. Set risk.risk_pct_per_trade: 0.005  (0.5% of equity per trade for Phase-1)
   — do NOT use risk_usd absolute; use the % of balance so position size scales.
6. Issue CONFIRM-LIVE-ON manually in the VPS Claude Code session.

The agent will refuse to flip LIVE_TRADING=true or metaapi.demo: false itself
under any circumstances. These are OWNER-ONLY edits.
```

---

## Daily trade frequency reference

Under normal market conditions, expect:

| Session | EURUSD | GBPUSD | XAUUSD | Daily signals |
|---------|--------|--------|--------|---------------|
| Asian | ✅ | ❌ (excluded) | ❌ (excluded) | 0–1 |
| London | ✅ | ✅ | ✅ | 1–2 |
| Overlap | ✅ | ✅ | ✅ | 0–1 |
| New York | ✅ | ✅ | ✅ | 0–1 |
| **Total** | | | | **2–3 / day** |

High-volatility days (NFP, FOMC, CPI) may produce 4–5 signals. The
max_concurrent_signals: 3 cap and max_daily_loss_usd: 150 guard prevent
over-trading on event days.

---

## Your operating commands (after deployment)

**Set capital** — set per-trade risk as % of balance (scales automatically):
```yaml
# config.yaml
risk:
  risk_pct_per_trade: 0.01   # 1% per trade during demo
  max_lots_per_symbol: 0.50  # hard cap while validating
```

**Run** (starts the fully-auto loop, survives reboot):
```bash
sudo systemctl enable --now smc-bot
```

**Stop** (clean shutdown):
```bash
sudo systemctl stop smc-bot
```

**Watch**:
```bash
systemctl status smc-bot
journalctl -u smc-bot -f
```

**Check open positions and state**:
```bash
cat data/position_state.json | python3 -m json.tool
```

---

## Honest caveats

- This is not financial advice. The backtest gate (P5) exists to find out if the
  edge is real before you risk capital. Most intraday strategies underperform
  live vs. backtest due to spread, slippage, and data lookahead.
- XAUUSD has the widest spread of the three. The 0.20 sl_pct_of_range (tighter
  than forex) compensates for this, but verify your Vantage MT5 spread on gold
  during London and NY sessions before going live — if it widens beyond 0.50 on
  your account type, re-run the backtest with the real spread figure.
- GBPUSD exclusion from the Asian session is a deliberate conservative choice.
  If your P5 backtest shows GBPUSD Asian actually passes, you can add it back by
  appending 'asian' to its sessions list and re-running P5.
- The 2–3 trades/day target is a realistic average, not a guarantee. The Asian
  session on EURUSD can go weeks without a clean sweep setup during choppy macro
  conditions. The multi-session design is specifically to avoid those dry spells.
- Your CLAUDE.md rule against self-enabling live trading is protecting you. The
  P5 → P6 → P7 gate is the minimum responsible path. Do not skip P6.
