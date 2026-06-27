# Incident Response Runbook
# Session SMC Trading Bot — OPS-01+
# Date: 2026-06-23 | Read this when something breaks

---

## Quick Reference

| Incident | First command | Safe to wait? |
|---|---|---|
| MT5 disconnect | `tail -20 logs/bot.log` | Yes — bot auto-reconnects |
| Bot process gone | `tmux ls` | No — restart immediately |
| VPS reboot | `tmux ls && pgrep python3` | No — restart bot |
| MetaAPI outage | Check `status.metaapi.cloud` | Yes — SDK retries |
| Telegram silent | `grep "Telegram send" logs/bot.log` | Yes — alerts only |
| Duplicate trade | `grep ORDER_FILLED logs/trades.jsonl \| wc -l` | No — investigate |
| Kill switch fired | `cat logs/bot_state.json` | Yes — review then reset |

**LIVE_TRADING=false.** All positions are demo. No real capital is at risk today.
That said, execution bugs matter — a habit built on wrong behavior is hard to unlearn.

---

## Incident 1 — MT5 Disconnect

### What it looks like

```
ERROR  execution.metaapi_client  MetaAPI RPC timeout after 30s — marking disconnected
INFO   bot  [HEARTBEAT] ... connection_status=DISCONNECTED  balance=0.00
INFO   bot  Connection lost after heartbeat — attempting reconnect
ERROR  execution.metaapi_client  MetaAPI reconnect failed: Timed out waiting ...
```

### Severity

| Duration | Level | Action |
|---|---|---|
| < 30 min | LOW | Watch — SDK auto-reconnects |
| 30 min–4 hours | MEDIUM | No action if heartbeat still firing |
| > 4 hours | HIGH | Manual reconnect attempt |
| > 24 hours | CRITICAL | Check VT Markets server status, new account |

### Detection

```bash
tail -50 logs/bot.log | grep -E "DISCONNECTED|reconnect|RPC timeout"
```

### Recovery — automatic

The bot attempts `reconnect()` after every heartbeat (every 5 min). No action needed
if the heartbeat loop continues (check: `grep HEARTBEAT logs/bot.log | tail -5`).

Since the current runtime now emits explicit reconnect alerts, a successful recovery
should also appear in Telegram as:

```text
[MetaAPI reconnect] restored connection successfully
```

The startup alert now includes recovered state from `logs/bot_state.json` and
the append-only trade journal, so after a restart you should see whether prior
loss counters or open-state markers were loaded.

### Recovery — manual (if SDK stuck)

```bash
# Step 1: verify heartbeat is still firing (max 10 min gap = OK)
python3 scripts/health_check.py

# Step 2: if bot process alive but stuck > 24h without reconnect
tmux attach -t bot           # Ctrl-C to stop
python3 bot.py >> logs/bot.log 2>&1 &   # restart in background
# OR in tmux:
tmux kill-session -t bot
tmux new-session -d -s bot "python3 bot.py >> logs/bot.log 2>&1"
```

### Verification

```bash
# Confirm reconnected
grep "MetaAPI connected\|reconnected" logs/bot.log | tail -3
python3 scripts/health_check.py | grep -E "MetaAPI|heartbeat"
```

### Root causes seen

| Date | Cause | Resolution |
|---|---|---|
| 2026-06-21 | VT Markets demo weekend maintenance | Waited; resolved Monday |
| 2026-06-22 | Old demo account (026ea073) MT5 sync never recovered | Migrated to d6f6eec3 |

---

## Incident 2 — Bot Process Gone (crash / OOM / VPS kill)

### What it looks like

```bash
tmux ls    # no 'bot' session
pgrep -f bot.py   # no output
```

### Severity: HIGH — restart immediately

No session monitoring is running. Signals will be missed.

### Detection

```bash
tmux ls
pgrep -f bot.py
python3 scripts/health_check.py | grep "bot process"
```

### Recovery

```bash
# 1. Check why it stopped
tail -100 logs/bot.log | grep -E "ERROR|CRITICAL|Traceback|Killed"

# 2. If clean stop (Ctrl-C or SIGTERM)
tmux new-session -d -s bot "cd /home/aungp/session-smc-trading-bot && python3 bot.py >> logs/bot.log 2>&1"

# 3. If OOM or crash — check memory first
free -h
python3 scripts/health_check.py | grep memory

# 4. Verify startup
sleep 10 && tail -20 logs/bot.log
python3 scripts/health_check.py
```

### Recovery evidence to confirm

```bash
# Health check now includes a Recovery probe
python3 scripts/health_check.py | grep Recovery

# Startup summary should show recovered state if bot_state.json and trades.jsonl exist
grep "recovered_signals\|halt_state\|risk_state" logs/bot.log | tail -5
```

### Verification

```bash
pgrep -a python3 | grep bot.py    # should show PID
tmux ls | grep bot                 # should show session
python3 scripts/health_check.py   # expect VERDICT: OK
grep "MetaAPI connected" logs/bot.log | tail -1   # confirm connection
```

### Post-incident

1. Check if any signal fired while bot was down (look at price action in missed window)
2. Confirm no open positions were left dangling (MT5 will show them even if bot is down)
3. If trade was open: check MetaAPI dashboard or MT5 terminal — SL/TP are server-side,
   so position is protected even without the bot running
4. Log incident in next daily OPS report

---

## Incident 3 — VPS Reboot

### What it looks like

- SSH connection drops / times out
- On reconnect: `tmux ls` shows no sessions
- `uptime` shows short uptime (minutes/hours)

### Severity: HIGH — restart bot within minutes

### Detection

```bash
uptime                         # short uptime = rebooted
last reboot | head -3          # reboot history
tmux ls 2>&1                   # "no server running" if fresh reboot
```

### Recovery

```bash
# 1. Verify system is healthy after reboot
df -h / && free -h

# 2. Check if tmux server auto-started (it doesn't by default)
tmux ls 2>&1

# 3. Start bot
tmux new-session -d -s bot "cd /home/aungp/session-smc-trading-bot && python3 bot.py >> logs/bot.log 2>&1"

# 4. Verify
sleep 10 && python3 scripts/health_check.py
```

### Prevention

Add to crontab to auto-start on reboot:
```bash
@reboot sleep 30 && cd /home/aungp/session-smc-trading-bot && tmux new-session -d -s bot "python3 bot.py >> logs/bot.log 2>&1"
```

*(Not yet implemented — requires testing before enabling)*

### Post-incident

1. Check `logs/bot.log.YYYY-MM-DD` (rotated log) for last state before reboot
2. Confirm LIVE_TRADING=false in .env after restart
3. Confirm no open positions were orphaned

---

## Incident 4 — MetaAPI Cloud Outage

### What it looks like

```
ERROR  execution.metaapi_client  MetaAPI reconnect failed: ...
httpx  HTTP Request: GET https://mt-provisioning-api-v1.agiliumtrade... "HTTP/1.1 503"
```

OR: bot connects but all RPC calls return errors.

### Severity: MEDIUM (demo) — no action unless persistent > 4 hours

### Detection

```bash
# Check MetaAPI status
curl -s https://status.metaapi.cloud/ | head -50   # or visit in browser

# Check bot log
grep -E "503|502|Gateway|outage|maintenance" logs/bot.log | tail -10
```

### Recovery — wait

MetaAPI outages are typically < 2 hours. The bot's reconnect loop runs every 5 minutes
and will auto-recover. No manual action needed during the outage.

### Recovery — if > 4 hours

```bash
# 1. Verify MetaAPI account is still provisioned
python3 -c "
import asyncio, os
from metaapi_cloud_sdk import MetaApi
async def check():
    api = MetaApi(os.getenv('METAAPI_TOKEN'))
    accounts = await api.metatrader_account_api.get_accounts_with_infinite_scroll_pagination()
    for a in accounts:
        print(a.id, a.state, a.connection_status)
    await api.close()
asyncio.run(check())
"

# 2. If account shows UNDEPLOYED — re-deploy
python3 scripts/validate_connection.py
```

### Post-incident

Note duration and impact in daily OPS report. If outage > 8 hours, assess whether
missed sessions should be logged as downtime vs. infrastructure event.

---

## Incident 5 — Telegram Alerts Silent

### What it looks like

```
WARNING  monitoring.telegram  Telegram send failed 400: Bad Request: can't parse entities
```
OR: no Telegram messages received for > 30 minutes during active hours.

### Severity: LOW — operational visibility gap only, no trading impact

### Detection

```bash
grep "Telegram send" logs/bot.log | tail -10
```

### Known issues

| BUG | Description | Status |
|---|---|---|
| BUG-02 | `parse_mode: Markdown` on raw heartbeat string | ✅ Fixed 2026-06-23 — requires bot restart |

### Recovery

```bash
# 1. If BUG-02 style (parse entities error):
# Fixed in monitoring/telegram.py — restart bot to apply
tmux kill-session -t bot
tmux new-session -d -s bot "cd /home/aungp/session-smc-trading-bot && python3 bot.py >> logs/bot.log 2>&1"

# 2. Test Telegram manually
python3 -c "
import asyncio, os
from monitoring.telegram import TelegramAlerter
async def test():
    t = TelegramAlerter()
    await t.start()
    await t.send('TEST: Telegram manual check [OK]')
    await t.stop()
asyncio.run(test())
"

# 3. If Telegram bot token is invalid or chat_id wrong:
grep -E "TELEGRAM_BOT_TOKEN|TELEGRAM_CHAT_ID" .env
# Verify token at: https://api.telegram.org/bot{TOKEN}/getMe
```

### Verification

After fix: confirm next heartbeat generates no WARNING in logs.

---

## Incident 6 — Duplicate Trade Detected

### What it looks like

```bash
grep "ORDER_FILLED" logs/trades.jsonl | grep EURUSD
# shows 2 fills close together for same symbol
```

### Severity: CRITICAL — investigate immediately

### Detection

```bash
# Check for duplicate fills
python3 -c "
import json
from pathlib import Path
events = [json.loads(l) for l in Path('logs/trades.jsonl').read_text().splitlines() if l.strip()]
fills = [e for e in events if e.get('event') == 'ORDER_FILLED']
by_sym = {}
for f in fills:
    by_sym.setdefault(f['symbol'], []).append(f['ts'])
for sym, ts in by_sym.items():
    if len(ts) > 1:
        print(f'DUPLICATE: {sym} has {len(ts)} fills: {ts}')
"
```

### Recovery

1. Connect to MetaAPI/MT5 terminal and close the duplicate position manually
2. Log the incident with full timestamp + order IDs
3. Review `bot.py` signal dedup (`seen_signals`) and `order_manager.py` position guard
4. Do NOT restart the bot until you've confirmed positions are clean
5. File a bug report with the exact log sequence

### Prevention (existing)

- Signal dedup: `bot.py:109` — `seen_signals[symbol]` set
- Position guard: `order_manager.py:114` — MAX_OPEN_TRADES = 1 per symbol
- If both layers failed: likely a concurrent signal from two sessions or a race condition
  in the reconnect path

---

## Incident 7 — Kill Switch / Circuit Breaker Activated

### What it looks like

```
WARNING  execution.risk_manager  Daily loss limit hit (3R) — halting trading
INFO     bot  [CIRCUIT BREAKER] trading halted
```

OR `cat logs/bot_state.json` shows `"halted": true`.

### Severity: MEDIUM — normal risk management, not a bug

### Detection

```bash
cat logs/bot_state.json | python3 -m json.tool
grep "CIRCUIT_BREAKER\|halted\|halt" logs/bot.log | tail -5
```

### Recovery

The kill switch resets automatically at UTC midnight (daily reset) for daily-loss halts.
For consecutive-loss halts: resets on next UTC day.

**Manual override (use only after reviewing cause):**
```bash
# Reset halt state manually — only if you've reviewed the loss sequence
python3 -c "
import json
from pathlib import Path
state_file = Path('logs/bot_state.json')
state = json.loads(state_file.read_text())
state['halted'] = False
state['halt_reason'] = ''
state_file.write_text(json.dumps(state, indent=2))
print('Halt cleared:', state)
"
```

### Review checklist before clearing halt

- [ ] Review all POSITION_CLOSED events to understand loss sequence
- [ ] Confirm no execution bugs caused losses (wrong SL, wrong direction)
- [ ] Confirm losses are within normal strategy drawdown expectation (max ~19R)
- [ ] If 3 consecutive days of halts: pause bot, review regime, do not clear

---

## General Diagnostic Commands

```bash
# One-line status check
python3 scripts/health_check.py

# Today's heartbeats
grep HEARTBEAT logs/bot.log | grep $(date -u +%Y-%m-%d) | wc -l

# Today's errors
grep ' ERROR ' logs/bot.log | grep $(date -u +%Y-%m-%d)

# Trade events summary
cat logs/trades.jsonl | python3 -c "
import json, sys, collections
events = [json.loads(l) for l in sys.stdin if l.strip()]
c = collections.Counter(e['event'] for e in events)
for k, v in sorted(c.items()): print(f'{k}: {v}')
"

# Generate full status report
python3 research/daily_status_report.py

# Bot state
cat logs/bot_state.json | python3 -m json.tool

# Check open positions via MetaAPI
python3 scripts/validate_connection.py
```

---

*Incident Response Runbook | Session SMC Trading Bot | ST-A2 | 2026-06-23*
*Update this file whenever a new incident type is encountered.*
