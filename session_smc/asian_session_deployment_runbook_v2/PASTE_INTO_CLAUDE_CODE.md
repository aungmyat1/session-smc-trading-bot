# Claude Code VPS Prompts — session-smc-trading-bot v2
## EURUSD · GBPUSD · XAUUSD · Vantage MT5 via MetaAPI · 2–3 trades/day

Paste each block into Claude Code on the VPS **in order**.
Do NOT proceed to the next block until the current one completes and you confirm.
All blocks are propose-only. Nothing commits or goes live without your CONFIRM token.

---

## P0 — Sync + safety baseline
```
Read CLAUDE.md in full, then git pull and run `pytest -q`.

Report ALL of the following — do NOT change anything yet:
1. signal_only_mode, LIVE_TRADING, and metaapi.demo values in config.yaml + .env
2. MetaAPI SDK installed? Run: python -c "import metaapi_cloud_sdk; print('ok')"
3. METAAPI_TOKEN and METAAPI_ACCOUNT_ID set in .env? (show presence, not values)
4. Any remaining Bybit SDK imports — search: grep -r "bybit" smc_bot/ --include="*.py"
5. Current signal_source value in config.yaml
6. pytest result: pass / fail / count

Just report. No edits.
```

---

## P0.5 — MetaAPI broker migration (Bybit → Vantage MT5)

> **Before running:** install the SDK on the VPS:
> ```bash
> pip install metaapi-cloud-sdk
> ```
> Then add to `.env`:
> ```
> METAAPI_TOKEN=your_token_here
> METAAPI_ACCOUNT_ID=your_account_id_here
> ```

```
PROPOSE ONLY — do not commit until I reply CONFIRM-COMMIT-METAAPI.

Copy the file smc_bot/broker/metaapi_executor.py from the provided source
(available at /home/deploy/session-smc-bot-files/metaapi_executor.py) into
smc_bot/broker/metaapi_executor.py.

Then:
1. Rename smc_bot/broker/bybit_executor.py → smc_bot/broker/bybit_executor.py.disabled
   (preserve git history, do not delete)
2. Update any import of bybit_executor in bot.py to import metaapi_executor instead.
3. Copy tests/test_metaapi_executor.py from the provided source.
4. Copy smc_bot/risk.py from the provided source (forex lot sizing).
5. Copy tests/test_risk.py from the provided source.
6. Run pytest tests/test_metaapi_executor.py tests/test_risk.py -v and show results.
7. Show me the full diff of all changed files.

Do NOT commit until CONFIRM-COMMIT-METAAPI.
```

---

## P1 — Build the multi-session signal module

```
PROPOSE ONLY — do not commit until I reply CONFIRM-COMMIT-SESSION.

Copy smc_bot/session_range.py from the provided source
(/home/deploy/session-smc-bot-files/session_range.py) into the repo.

This module may import ONLY: structure, tp_engine, dataclasses, pandas, datetime.
No broker SDK — must pass tests/test_ast_guard.py.

Then:
1. Copy tests/test_session_range.py from the provided source.
2. Run pytest tests/test_session_range.py -v and show the full output.
3. If any tests fail, diagnose and propose a fix — do not commit anything broken.
4. Show me the full diff.

Do NOT commit until CONFIRM-COMMIT-SESSION.
```

---

## P2 — Config: instruments + sessions block

```
PROPOSE ONLY — do not commit until I reply CONFIRM-COMMIT-CONFIG.

Copy config.yaml from the provided source
(/home/deploy/session-smc-bot-files/config.yaml) and MERGE it into the existing
smc_bot/config.yaml.

Rules for merging:
- ADD all new top-level keys: instruments, sessions, asian, metaapi, risk (new fields)
- DO NOT overwrite existing keys that control the smc_sniper live path
- signal_source must remain: smc_sniper (do not change to asian_session yet)
- metaapi.demo must remain: true
- Show me a SIDE-BY-SIDE diff of old vs new config

Do NOT commit until CONFIRM-COMMIT-CONFIG.
```

---

## P3 — Wire multi-instrument scanner into the run loop

```
PROPOSE ONLY — do not commit until I reply CONFIRM-COMMIT-WIRING.

In smc_bot/bot.py run_cycle(), add the asian_session branch:

1. Read cfg['signal_source'].

2. When signal_source == 'asian_session':
   a. Fetch df_4h and df_1h for EACH instrument in cfg['instruments'] via
      metaapi_executor.get_candles(symbol, '1h', 500) and ('4h', 200).
      Convert the returned list of dicts to pd.DataFrame with columns:
      time, open, high, low, close, volume. Set time as DatetimeIndex (UTC).
   b. Build data dict: {'EURUSD': {'df_4h': ..., 'df_1h': ...}, ...}
   c. Call session_range.scan_all(data, cfg, utc_now=datetime.utcnow())
   d. For each signal in results:
      - Call risk.symbol_already_open(signal.instrument, open_positions) → skip if True
      - Call risk.check_max_open_positions(open_positions, cfg) → skip all if True
      - Call risk.check_daily_loss_limit(await executor.get_today_closed_pnl(), cfg) → skip all if True
      - Call risk.calc_qty(signal, cfg, await executor.get_balance()) → lots
      - If lots == 0.0: log warning and skip
      - Call await executor.place_market_order(signal.instrument, signal.side, lots,
          signal.sl, signal.tp, comment=f"{signal.session}_{signal.setup}")
      - Register position in position_manager state
      - Log: instrument, session, setup, side, entry, sl, tp, lots, positionId

3. After signal processing, call:
   await position_manager.manage_positions(executor, data, state, cfg)
   save_state(state)

4. When signal_source == 'smc_sniper' (default): behave exactly as today.
   Do NOT modify that path.

5. Do NOT duplicate risk/log code. Factor _execute_signal(sig, cfg, executor, state)
   helper if more than 3 signals share the same execution block.

Add a test: mock scan_all returning 2 signals with same instrument → verify only
one order placed. Run pytest. Show me the full diff.

Do NOT commit until CONFIRM-COMMIT-WIRING.
```

---

## P4 — Session-specific position management

```
PROPOSE ONLY — do not commit until I reply CONFIRM-COMMIT-MGMT.

Copy smc_bot/position_manager.py from the provided source
(/home/deploy/session-smc-bot-files/position_manager.py) into the repo.

Copy tests/test_position_manager.py from the provided source.

Then:
1. Verify position_manager.STATE_FILE path is data/position_state.json
   (create data/ dir if missing: mkdir -p data)
2. Run pytest tests/test_position_manager.py -v and show full output
3. If any tests fail, diagnose and fix — do not commit broken tests
4. Show full diff

Do NOT commit until CONFIRM-COMMIT-MGMT.
```

---

## P5 — Backtest gate (non-negotiable before any live trading)

> **Before running:** install dependencies if not present:
> ```bash
> pip install yfinance pandas numpy
> ```

```
PROPOSE ONLY — do not change any live config or flip signal_source.
Do NOT commit until I reply CONFIRM-COMMIT-BACKTEST.

Copy scripts/backtest.py from the provided source
(/home/deploy/session-smc-bot-files/backtest.py) into the repo.

Then run:
  python scripts/backtest.py --fetch

This will:
1. Download 2 years of 1h + 4h OHLCV for EURUSD, GBPUSD, XAUUSD into
   data/historical/ (yfinance fallback — use MetaAPI historical API if available)
2. Run walk-forward backtest across all instrument × session combinations
3. Print the results table and PASS/FAIL verdict
4. Append one row to docs/VERDICT_LOG.md

Show me the full output table and verdict.

PASS criteria (ALL required on COMBINED row):
  net PF >= 1.4  ·  n >= 100  ·  win% >= 35%  ·  max_consec_loss <= 8

If COMBINED FAILS: list which instrument × session combinations are failing
and recommend specific parameter adjustments (sweep_beyond_pct, sl_pct_of_range,
range_thr / trend_thr) — do NOT suggest going live.

If COMBINED PASSES: show me the diff to docs/VERDICT_LOG.md only.
Do NOT change signal_source or asian.enabled.
```

---

## P6 — Demo run on Vantage MT5 (no real money)

> **Only run this block after P5 COMBINED verdict = PASS.**

```
With P5 PASS confirmed only.

Make these and ONLY these config changes:
  signal_source: asian_session
  asian.enabled: true
  metaapi.demo: true        (keep — this is demo, not live)
  LIVE_TRADING=false        (keep in .env — do not touch)

Also disable any instrument × session rows flagged FAILING in P5:
  For each failing combination, add enabled: false to that session entry
  in the instrument's sessions list in config.yaml.

Show me the diff and these systemd commands to restart:
  sudo systemctl restart smc-bot
  journalctl -u smc-bot -f

After I reply CONFIRM-DEMO-ON I will run the commands myself.

Monitor for 30 days / 100+ trades:
- Telegram alert feed for every entry, first-close, SL-to-BE, exit
- data/position_state.json for stale/orphaned positions daily
- Flag IMMEDIATELY if:
  (a) order placed without valid signal log entry
  (b) lot size deviates > 5% from risk calc
  (c) MetaAPI reconnection takes > 5 minutes mid-trade
  (d) position_state.json and MetaAPI open positions are out of sync

After 30 days, report: live net PF, live win%, avg slippage vs backtest,
execution discrepancies. Do NOT suggest P7 unless net PF >= 1.2 and zero
critical execution bugs.
```

---

## P7 — Go live (OWNER ONLY — agent must never perform this step)

```
Do NOT perform this step. Describe it only.

After P5 PASS and 30 clean demo days (net PF >= 1.2, zero critical bugs):

OWNER actions only — manual edits on VPS:
1. Fund the Vantage MT5 LIVE account.
2. Edit .env:
     LIVE_TRADING=true
3. Edit config.yaml:
     metaapi.demo: false
     risk.risk_usd: 0              # switch to % sizing for live
     risk.risk_pct_per_trade: 0.005   # 0.5% per trade for Phase-1
     risk.max_lots_per_symbol: 0.20   # conservative cap for Phase-1
4. Issue CONFIRM-LIVE-ON in the VPS Claude Code session.

The agent will REFUSE to set LIVE_TRADING=true or metaapi.demo=false itself.
These are OWNER-ONLY edits, always.
```

---

## Operating commands (after P6 deployment)

```bash
# Start bot (auto-restarts on reboot)
sudo systemctl enable --now smc-bot

# Stop bot cleanly
sudo systemctl stop smc-bot

# Watch live logs
journalctl -u smc-bot -f

# Check open position state
cat data/position_state.json | python3 -m json.tool

# Check today's verdict log
tail -5 docs/VERDICT_LOG.md

# Manually run backtest (no fetch — use cached data)
python scripts/backtest.py

# Re-fetch data and rerun backtest
python scripts/backtest.py --fetch
```

---

## Files provided in /home/deploy/session-smc-bot-files/

Upload these to your VPS before running P0.5:

| File | Destination in repo |
|------|---------------------|
| `metaapi_executor.py` | `smc_bot/broker/metaapi_executor.py` |
| `session_range.py` | `smc_bot/session_range.py` |
| `position_manager.py` | `smc_bot/position_manager.py` |
| `risk.py` | `smc_bot/risk.py` |
| `config.yaml` | merge into `smc_bot/config.yaml` |
| `backtest.py` | `scripts/backtest.py` |
| `test_session_range.py` | `tests/test_session_range.py` |
| `test_metaapi_executor.py` | `tests/test_metaapi_executor.py` |
| `test_risk.py` | `tests/test_risk.py` |
| `test_position_manager.py` | `tests/test_position_manager.py` |

SCP command (from your local machine):
```bash
scp metaapi_executor.py session_range.py position_manager.py risk.py config.yaml \
    backtest.py test_session_range.py test_metaapi_executor.py test_risk.py \
    test_position_manager.py \
    user@your-vps-ip:/home/deploy/session-smc-bot-files/
```
