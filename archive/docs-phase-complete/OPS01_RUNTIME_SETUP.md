# OPS01_RUNTIME_SETUP.md
# OPS-01 — Process Management & Runtime Setup
# Date: 2026-06-21

---

## Chosen Method: tmux

tmux is the process manager for this VPS. It keeps `bot.py` running across
SSH disconnects and provides clean attach/detach without a daemon.

---

## Start Command

```bash
cd ~/session-smc-trading-bot
tmux new-session -d -s bot 'python3 bot.py 2>&1 | tee logs/bot.log'
```

This starts `bot.py` in a detached tmux session named `bot`.
stdout and stderr are tee'd to `logs/bot.log` for offline inspection.

---

## Attach (view live output)

```bash
tmux attach -t bot
```

Detach without stopping: `Ctrl-B  D`

---

## Stop Command

```bash
tmux send-keys -t bot C-c
# allow graceful shutdown (client.disconnect + telegram.stop)
sleep 3
tmux kill-session -t bot
```

Do NOT `kill -9` — the bot needs `finally:` to disconnect MetaAPI cleanly.

---

## Restart Command

```bash
tmux send-keys -t bot C-c
sleep 3
tmux kill-session -t bot 2>/dev/null
tmux new-session -d -s bot 'cd ~/session-smc-trading-bot && python3 bot.py 2>&1 | tee -a logs/bot.log'
```

Uses `tee -a` (append) to preserve the previous log across restarts.

---

## Status Check

```bash
tmux ls                          # is session 'bot' running?
tail -40 logs/bot.log            # last 40 log lines
tail -f logs/bot.log             # stream live
grep HEARTBEAT logs/bot.log      # check heartbeat timing
grep ERROR logs/bot.log          # scan for errors
```

---

## Log Locations

| File | Contents | Retention |
|---|---|---|
| `logs/bot.log` | Full stdout/stderr from bot.py | Append across restarts |
| `logs/trades.jsonl` | Append-only JSONL trade events (6 event types) | Never deleted |
| `logs/bot_state.json` | RiskManager state (circuit breakers, daily loss) | Overwritten on each save |

---

## Recovery Procedure

### Bot crashes / process dies

```bash
# 1. Check what happened
tail -50 logs/bot.log
grep "Fatal\|ERROR\|Exception" logs/bot.log | tail -20

# 2. Check state integrity
cat logs/bot_state.json          # ensure JSON is valid
tail -5 logs/trades.jsonl        # last events logged

# 3. Check open positions (broker side)
python3 -c "
import os, asyncio, sys; sys.path.insert(0,'.')
os.environ['LIVE_TRADING']='false'
from dotenv import load_dotenv; load_dotenv('.env')
from execution.metaapi_client import MetaAPIClient
import os
async def check():
    c = MetaAPIClient(os.getenv('METAAPI_TOKEN'), os.getenv('METAAPI_ACCOUNT_ID'))
    await c.connect()
    pos = await c.get_open_positions()
    print(f'Open positions: {len(pos)}')
    for p in pos: print(f'  {p.symbol} {p.direction} id={p.position_id}')
    await c.disconnect()
asyncio.run(check())
"

# 4. Restart
tmux new-session -d -s bot 'cd ~/session-smc-trading-bot && python3 bot.py 2>&1 | tee -a logs/bot.log'
```

### MetaAPI connection lost mid-session

bot.py handles this automatically:
- `get_candles()` returns `[]` → scan skipped
- 60s poll → SDK reconnects in background
- No action required unless bot exits

### Circuit breaker triggered (daily/weekly loss)

```bash
cat logs/bot_state.json    # check halted=true, halt_reason
# MAX_DAILY_LOSS: auto-resets next trading day
# MAX_WEEKLY_LOSS: auto-resets next week (Monday)
# Kill switch: requires KILL_SWITCH_OVERRIDE=true in .env
```

---

## Pre-start Checklist

```
[ ] tmux session 'bot' not already running:  tmux ls
[ ] .env has LIVE_TRADING=false (single entry)
[ ] .env has METAAPI_ACCOUNT_ID=026ea073-5241-4d53-9a87-b0cb791443af
[ ] logs/ directory exists and is writable
[ ] Run pre-flight:  python3 scripts/ops01_preflight.py
[ ] All tests pass:  python3 -m pytest (610/610)
[ ] Telegram bot reachable (send test message)
```

---

## Systemd Alternative (optional, not currently active)

If the VPS reboots frequently, a systemd unit provides auto-start:

```ini
# /etc/systemd/system/trading-bot.service
[Unit]
Description=Session Trading Bot (ST-A2)
After=network.target

[Service]
User=aungp
WorkingDirectory=/home/aungp/session-smc-trading-bot
ExecStart=/usr/bin/python3 bot.py
Restart=on-failure
RestartSec=30s
StandardOutput=append:/home/aungp/session-smc-trading-bot/logs/bot.log
StandardError=append:/home/aungp/session-smc-trading-bot/logs/bot.log
Environment=LIVE_TRADING=false

[Install]
WantedBy=multi-user.target
```

**NOT activated** — tmux is the active method for OPS-01.
Enable only if VPS reboots become a problem.

*OPS-01 | Runtime Setup | 2026-06-21*
