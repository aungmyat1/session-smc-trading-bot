# ST-A2 Vantage Demo — Operations Runbook
# Version: 1.0 | Phase: Demo Validation (Phase 1)
# DO NOT advance to Phase 2 (live) without completing the 30-trade demo protocol.

---

## Before Startup Checklist

Run this before every session start. All items must be PASS.

```
[ ] 1. .env file present and populated
        METAAPI_TOKEN, VANTAGE_DEMO_METAAPI_ID, DEMO_ONLY, TRADING_MODE, TELEGRAM_BOT_TOKEN

[ ] 2. LIVE_TRADING=false confirmed
        grep LIVE_TRADING .env  → must NOT be "true"

[ ] 3. TRADING_MODE set correctly
        For shadow observation:  TRADING_MODE=shadow
        For demo order sending:  TRADING_MODE=demo  AND  DEMO_ONLY=false

[ ] 4. Run health check (no-broker, fast)
        python3 scripts/health_check.py --no-broker
        Required: Risk Engine=PASS, Portfolio=PASS, Execution=SHADOW or READY

[ ] 5. Run full health check (live broker connection)
        python3 scripts/health_check.py
        Required: Broker=PASS, Data Feed=PASS

[ ] 6. Confirm logs/ directory is writable
        ls -la logs/

[ ] 7. Confirm data/trade_journal.db is accessible
        python3 -c "from core.trade_journal_db import TradeJournalDB; print(TradeJournalDB().summary())"

[ ] 8. No leftover runner processes
        pgrep -f "run_st_a2_demo" && echo "STILL RUNNING — kill first" || echo "OK"
```

---

## How to Start the Runner

### Shadow Mode (signal observation, no orders)
```bash
TRADING_MODE=shadow nohup python3 scripts/run_st_a2_demo.py \
  > logs/st_a2_runner.log 2>&1 &
echo "Runner PID: $!"
```
Use this first. Observe signals during at least one London and one NY session.

### Demo Mode (live orders to Vantage demo account)
```bash
# Verify DEMO_ONLY=false and TRADING_MODE=demo in .env FIRST
grep "DEMO_ONLY\|TRADING_MODE\|LIVE_TRADING" .env

TRADING_MODE=demo nohup python3 scripts/run_st_a2_demo.py \
  > logs/st_a2_runner.log 2>&1 &
echo "Runner PID: $!"
```

### Explicit mode flag (overrides env var)
```bash
nohup python3 scripts/run_st_a2_demo.py --mode demo \
  > logs/st_a2_runner.log 2>&1 &
```

---

## How to Stop Safely

```bash
# 1. Find the PID
pgrep -a -f "run_st_a2_demo"

# 2. Send SIGTERM (graceful shutdown — closes MetaAPI connection)
kill <PID>

# 3. Confirm stopped (wait ~5 seconds)
sleep 5 && pgrep -f "run_st_a2_demo" && echo "still running" || echo "stopped"

# 4. If still running after 10s, force kill
kill -9 <PID>
```

**Do NOT kill -9 immediately.** The graceful shutdown runs `connector.disconnect()` which
properly closes the MetaAPI WebSocket. A hard kill leaves the session hanging.

---

## How to Check Logs

### Real-time tail
```bash
tail -f logs/st_a2_runner.log
```

### Last 50 lines
```bash
tail -50 logs/st_a2_runner.log
```

### Filter signals only
```bash
grep "SIGNAL\|SHADOW\|Order placed" logs/st_a2_runner.log
```

### Filter warnings and errors
```bash
grep "WARNING\|ERROR\|FAIL\|Reconnect\|timeout" logs/st_a2_runner.log
```

### Check today's activity
```bash
grep "$(date -u +%Y-%m-%d)" logs/st_a2_runner.log | tail -30
```

---

## How to Verify Open Positions

### Via health check
```bash
python3 scripts/health_check.py
```

### Via trade journal DB
```python
python3 -c "
from core.trade_journal_db import TradeJournalDB
db = TradeJournalDB()
for t in db.get_open_trades():
    print(t['symbol'], t['direction'], t['entry_price'], t['stop_loss'], t['execution_result'])
"
```

### Via demo status script
```bash
python3 scripts/demo_status.py
```

### Direct broker query (requires MetaAPI connection)
```python
python3 -c "
import asyncio, sys; sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv('.env')
from execution.mt5_connector import MT5Connector
from execution.vantage_demo_executor import VantageDemoExecutor

async def positions():
    c = MT5Connector('demo'); await c.connect()
    ex = VantageDemoExecutor(c)
    ps = await ex.get_positions()
    for p in ps: print(p)
    await c.disconnect()

asyncio.run(positions())
"
```

---

## Emergency Shutdown Procedure

Use when: unusual market event, system error, risk limit breach, margin warning.

### Step 1 — Stop runner immediately
```bash
pkill -f "run_st_a2_demo"
```

### Step 2 — Emergency close all ST-A2 positions
```python
python3 -c "
import asyncio, sys; sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv('.env')
from execution.mt5_connector import MT5Connector
from execution.vantage_demo_executor import VantageDemoExecutor
from execution.trade_manager import TradeManager

async def emergency():
    c = MT5Connector('demo'); await c.connect()
    m = TradeManager(VantageDemoExecutor(c))
    n = await m.emergency_close_all()
    print(f'Emergency closed {n} positions')
    await c.disconnect()

asyncio.run(emergency())
"
```

### Step 3 — Run health check to confirm
```bash
python3 scripts/health_check.py
```

### Step 4 — Log the incident
Append a row to `docs/VERDICT_LOG.md` noting the incident date, cause, and positions closed.

---

## Daily Review Checklist

Run this at the end of each trading day (after NY session close 16:00 UTC).

```
[ ] 1. Check trade journal summary
        python3 -c "from core.trade_journal_db import TradeJournalDB; import json; print(json.dumps(TradeJournalDB().summary(), indent=2))"

[ ] 2. Review today's signals in runner log
        grep "$(date -u +%Y-%m-%d)" logs/st_a2_runner.log | grep "SIGNAL\|SHADOW\|Order"

[ ] 3. Check for errors/warnings today
        grep "$(date -u +%Y-%m-%d)" logs/st_a2_runner.log | grep -c "ERROR\|WARNING"

[ ] 4. Verify no open positions remain at day end
        python3 scripts/health_check.py

[ ] 5. Note any session that fired no signals (London or NY)
        (Expected: 0-2 signals/day based on backtest frequency)

[ ] 6. After every 10 trades — trigger 10-trade review
        See docs/ST_A2_FIRST_30_TRADES_PLAN.md
```

---

## Monitoring Schedule

| Frequency | Action |
|-----------|--------|
| Every startup | Full preflight checklist |
| Session start (07:00 UTC) | `tail -f logs/st_a2_runner.log` for London open |
| Session start (13:00 UTC) | Same for NY open |
| End of day | Daily review checklist |
| After 10 trades | 10-trade review (see FIRST_30_TRADES_PLAN.md) |
| After 30 trades | Full Phase 1 review; decide Phase 2 readiness |

---

## Key File Locations

| File | Purpose |
|------|---------|
| `.env` | Secrets + mode config |
| `config/demo.yaml` | Safety parameters |
| `logs/st_a2_runner.log` | Main runner output |
| `logs/st_a2_demo.log` | Detailed tick log |
| `logs/shadow_trades.jsonl` | Shadow signal journal |
| `logs/st_a2_demo_trades.jsonl` | Demo trade journal (JSONL) |
| `data/trade_journal.db` | Persistent SQLite journal |
| `docs/VERDICT_LOG.md` | One row per trial; never delete |

---

## Session Hours (UTC)

| Session | Hours (UTC) | Notes |
|---------|-------------|-------|
| London | 07:00–10:00 | Primary session for ST-A2 |
| New York | 13:00–16:00 | Secondary session |
| Off-hours | All other | Runner idles; no signals expected |

---

## Known Limitations (Phase 1)

1. **Session close rule not auto-implemented.** If a trade is open at session end, it is not auto-closed by the runner. Review manually.
2. **XAUUSD pip value estimate.** $10/pip/lot is used; verify against actual Vantage MT5 contract spec.
3. **Reconnect not battle-tested.** The auto-reconnect (3 consecutive failures → reconnect) has been coded but not confirmed to recover from a real WebSocket timeout. Monitor closely.
4. **No partial close logic.** TP1 at 4R (75% close) is not automated. Demo phase is full-position exit only.
5. **Phase-0 status: UNVALIDATED.** See VERDICT_LOG.md. Phase-0 backtest passes at ST-A2 spec; 2× spread stress has not been re-run on the final config.
