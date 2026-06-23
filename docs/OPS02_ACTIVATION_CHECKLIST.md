# OPS02_ACTIVATION_CHECKLIST.md
# Demo-Trading Activation Checklist
# OPS-02 | Session SMC Trading Bot — ST-A2
# Created: 2026-06-21 | Status: PENDING (OPS-01 in progress)

---

## What this document is

A step-by-step owner checklist for transitioning the bot from **DRY_RUN mode** (orders
simulated, never sent) to **live order routing on the MetaAPI demo account** (real orders
on VT Markets demo, no real money). This is **Phase-1** of the deployment phase plan.

**LIVE_TRADING=false → LIVE_TRADING=true** is the only change required. The demo account
is already connected (MetaAPI account `026ea073-...`, VantageMarkets-Demo server, $100,000).

> **Agent constraint:** The agent never executes this checklist. All items below are
> owner-executed manual steps. The agent proposes but does not act.

---

## Section 1 — Preconditions

All items must be checked PASS before proceeding to Section 2.

### 1.1 OPS-01 Stability Run

| Check | Requirement | Current | Status |
|---|---|---|---|
| OPS-01 7-day run complete | 2026-06-28 or later | In progress (started 2026-06-21) | PENDING |
| Daily reports filed | Days 0–7, each with health check output | Day-0 filed | PENDING |
| Zero unplanned restarts | Bot ran continuously with no fatal exits | Check logs | PENDING |
| Zero CRITICAL health events | `python3 scripts/health_check.py` — no 🔴 in any daily run | Verify daily | PENDING |
| Heartbeat gaps | No gap > 10 minutes in 7-day log | Check with grep | PENDING |

```bash
# Verify no CRITICAL events in OPS-01 run
grep -c 'CRITICAL\|FATAL\|Exception' logs/bot.log

# Count heartbeats (expect 288/day × 7 = ~2016)
grep -c 'HEARTBEAT' logs/bot.log

# Verify no gap > 10 min between heartbeats
python3 scripts/health_check.py
```

### 1.2 No Critical Runtime Errors

| Check | Requirement | How to verify |
|---|---|---|
| ERROR lines in last 7 days | < 5 total | `grep ' ERROR ' logs/bot.log \| wc -l` |
| Fatal exceptions | 0 | `grep 'Fatal error' logs/bot.log` |
| Order manager exceptions | 0 unhandled | `grep 'GET_POSITIONS_FAILED' logs/bot.log` |
| Uncaught exceptions | 0 | `grep 'Traceback' logs/bot.log` |

```bash
grep ' ERROR ' logs/bot.log | wc -l       # target: < 5
grep 'Traceback' logs/bot.log             # target: 0 lines
grep 'Fatal error' logs/bot.log           # target: 0 lines
```

### 1.3 Heartbeat Healthy

```bash
# Run health check — must show all 9 checks PASS before activation
python3 scripts/health_check.py

# Expected output:
#   ✅  tmux session 'bot': running
#   ✅  bot process: running
#   ✅  MetaAPI status: CONNECTED
#   ✅  heartbeat age: <10m
#   ✅  log freshness: updated <5m ago
#   ✅  disk free: >{10%}
#   ✅  memory (bot RSS): <500MB
#   ✅  LIVE_TRADING guard: false
#   ✅  trade log: ...
#   VERDICT: ✅ OK
```

| Check | Requirement |
|---|---|
| health_check.py verdict | OK (not WARNING, not CRITICAL) |
| MetaAPI status | CONNECTED |
| Heartbeat age | < 5 minutes at time of check |
| LIVE_TRADING guard | false (confirm this one last time BEFORE changing it) |

### 1.4 Reconnect Verified

| Check | Requirement | Source |
|---|---|---|
| Reconnect test passed | 4/4 cycles < 30s | `docs/OPS01_RECONNECT_AUDIT.md` |
| Average reconnect time | < 15 seconds | Audit shows ~9.1s ✅ |

The reconnect test was run during OPS-01 build. Re-run if more than 14 days have elapsed
since the audit or if MetaAPI account credentials were changed:

```bash
python3 scripts/ops01_reconnect_test.py
```

### 1.5 Strategy Gate

| Check | Requirement | Status |
|---|---|---|
| Phase-0 backtest | n ≥ 50, Net PF > 1.0 at std AND 2× | ✅ PASS — n=169, PF_2x=1.025 |
| Run ID registered | In docs/VERDICT_LOG.md | ✅ 20260621T100458-183aaa |
| min_sl_pips enforced | 5.0 in session_strategy.py | ✅ line 178 |
| LIVE_TRADING currently | false | ✅ confirmed |

---

## Section 2 — Activation Procedure

**Perform only after Section 1 is all PASS.** Steps are sequential — do not skip.

### Step 1 — Backup current .env

```bash
cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
ls -la .env.backup.*    # confirm backup created
```

### Step 2 — Verify demo account state

Confirm in the MetaAPI dashboard that the account is DEPLOYED and CONNECTED:

- Account ID: `026ea073-5241-4d53-9a87-b0cb791443af`
- Server: `VantageMarkets-Demo`
- Platform: MT5
- Balance: $100,000 (confirm no unexpected changes)
- Connection status: CONNECTED

```bash
# Quick live check — runs validate_connection.py in read-only mode
python3 scripts/validate_connection.py
# Expected: 30/30 PASS
```

### Step 3 — Stop the running bot

```bash
# Graceful stop
tmux send-keys -t bot 'C-c' Enter
sleep 3

# Confirm stopped
pgrep -f 'python3 bot.py' | wc -l    # expect 0
```

### Step 4 — Set LIVE_TRADING=true in .env

Edit `.env` and change:

```
LIVE_TRADING=false
```

to:

```
LIVE_TRADING=true
```

**Verify the change:**

```bash
grep 'LIVE_TRADING' .env
# Expected output — exactly one line:
# LIVE_TRADING=true
```

Confirm there are no duplicate LIVE_TRADING entries. If two lines appear, the first
wins under python-dotenv (override=False). Remove any duplicate.

### Step 5 — Restart bot in tmux

```bash
tmux new-session -d -s bot 'python3 bot.py 2>&1 | tee logs/bot.log'
```

If session 'bot' already exists:

```bash
tmux kill-session -t bot
tmux new-session -d -s bot 'python3 bot.py 2>&1 | tee logs/bot.log'
```

### Step 6 — Confirm startup logs

```bash
# Attach and observe — detach with Ctrl+B then D
tmux attach -t bot
```

Expected startup sequence within 30 seconds:

```
Connecting to MetaAPI (LIVE_TRADING=True)…
MetaAPI connected.
[Telegram] Bot started — EURUSD GBPUSD | risk=1.0% | LIVE=True
```

**Critical: verify `LIVE_TRADING=True` in the startup log.**
If `LIVE_TRADING=False` appears, stop immediately — the .env change did not take effect.

```bash
grep 'LIVE_TRADING' logs/bot.log | tail -5
# Must show True
```

### Step 7 — Confirm 7-field heartbeat with LIVE_TRADING=true

Wait up to 5 minutes for the first heartbeat:

```bash
grep 'HEARTBEAT' logs/bot.log | tail -3
# Expected (note: live=True in second line):
# [HEARTBEAT] 2026-06-22T07:05 UTC
# uptime=300s  connection_status=CONNECTED  live=True
# balance=100000.00  equity=100000.00  open_positions=0
# last_signal=none
```

Run health check to confirm all 9 PASS:

```bash
python3 scripts/health_check.py
# Heartbeat must show live=True after activation
```

---

## Section 3 — Monitoring Requirements

### First 24 Hours

Run `python3 scripts/health_check.py` at each London session open (07:00 UTC) and close (10:00 UTC)
and at each NY session open (13:00 UTC) and close (16:00 UTC).

| Window | Time UTC | Check |
|---|---|---|
| Pre-London | 06:55 | health_check.py → all PASS |
| London open | 07:00 | First active scan window |
| London close | 10:00 | Any open positions? Session-end close fired? |
| Pre-NY | 12:55 | health_check.py → all PASS |
| NY close | 16:00 | Any open positions? Session-end close fired? |
| End of day | 20:00 | health_check.py + grep ERROR |

```bash
# End of day error check
grep ' ERROR ' logs/bot.log | grep $(date +%Y-%m-%d)
grep 'SIGNAL_CREATED\|ORDER_SUBMITTED\|ORDER_FILLED\|ORDER_REJECTED' logs/trades.jsonl | tail -20
```

### First Order

When the first SIGNAL_CREATED + ORDER_SUBMITTED is logged:

```bash
# Confirm the full trade lifecycle appeared
cat logs/trades.jsonl | python3 -c "
import json, sys
for line in sys.stdin:
    e = json.loads(line)
    print(e['event'], e['symbol'], e.get('side',''), e.get('detail',''))
"
```

**Manual verification — open MetaAPI dashboard and confirm:**

- [ ] Order appears in broker terminal under the correct symbol
- [ ] Magic number matches (EURUSD=21001 | GBPUSD=21002)
- [ ] SL and TP levels match the logged values
- [ ] Lot size is consistent with 1% risk × $100,000 equity ÷ sl_pips × pip_value

**Risk flags from ST-A2 to watch:**
- EURUSD: individually fails 2× spread stress (PF_2x=0.945). If 10 EURUSD trades yield
  win rate < 25%, flag for review before proceeding to Phase-2.
- London session win rate is structurally low (28%). First 3 losses in London are expected,
  not a bug. Do not adjust parameters.
- Max drawdown: 18.72R in 5yr backtest. On a $100k demo account at 1% risk, 18.72R = $18,720
  drawdown before the kill switch triggers (10% DD = $10,000). DD kill switch fires first.

### First SL Hit

- [ ] ORDER_FILLED → POSITION_CLOSED logged with PnL
- [ ] RiskManager daily_loss_r incremented (check logs/bot_state.json)
- [ ] If daily_loss_r reaches 3R → circuit breaker halts → `Bot halted: MAX_DAILY_LOSS` in log
- [ ] Halt is auto-cleared at midnight UTC (next day reset)
- [ ] Telegram alert received

```bash
cat logs/bot_state.json
grep 'MAX_DAILY_LOSS\|halted' logs/bot.log | tail -10
```

### First TP Hit

- [ ] POSITION_CLOSED logged with event detail showing TP fill
- [ ] consecutive_losses reset to 0 in bot_state.json
- [ ] Telegram trade-close alert received
- [ ] PnL in trade log is net-positive after spread

### First Timeout Exit (Session-End Close)

At 10:00 UTC (London close) or 16:00 UTC (NY close), if any position is still open:

- [ ] `_close_session_positions()` fires → position closed at market
- [ ] Telegram session-close alert received with count of positions closed
- [ ] POSITION_CLOSED event logged in trades.jsonl
- [ ] Trade log shows session = correct session name

---

## Section 4 — Rollback Procedure

If **any** of the following occur, roll back immediately:

- health_check.py CRITICAL on any check
- Duplicate orders submitted (same symbol open twice)
- SL or TP not placed on filled order
- ORDER_FILLED but no corresponding broker position visible in dashboard
- LIVE_TRADING guard failure: live trading on despite code error

### Rollback Steps

**Step 1 — Stop the bot**

```bash
tmux send-keys -t bot 'C-c' Enter
sleep 3
pgrep -f 'python3 bot.py' | wc -l    # confirm 0
```

**Step 2 — Set LIVE_TRADING=false**

Edit `.env`:

```
LIVE_TRADING=false
```

Verify:

```bash
grep 'LIVE_TRADING' .env
# Must show: LIVE_TRADING=false
```

**Step 3 — Restart in DRY_RUN mode**

```bash
tmux new-session -d -s bot 'python3 bot.py 2>&1 | tee logs/bot.log'
```

**Step 4 — Verify DRY_RUN active**

```bash
grep 'LIVE_TRADING' logs/bot.log | tail -3
# Must show: LIVE_TRADING=False
```

**Step 5 — Verify no orders can be sent**

In DRY_RUN mode, `place_order()` returns a simulated response without contacting the broker.
Confirm by checking that any ORDER_SUBMITTED log line is followed by ORDER_FILLED with
`dry_run=True` in the event detail.

**Step 6 — Close any open broker positions manually**

If real orders were placed before the rollback:

1. Log in to VT Markets web terminal (or MetaTrader 5 via VantageMarkets-Demo server)
2. Close all open positions with magic 21001 (EURUSD) or 21002 (GBPUSD) manually
3. Confirm positions = 0 in dashboard

**Step 7 — Document the rollback**

Create `docs/OPS02_ROLLBACK_REPORT.md` with:
- Timestamp of activation
- Timestamp of rollback
- Reason for rollback
- Number of trades placed before rollback
- Net PnL at rollback

---

## Section 5 — Success Metrics

The demo-trading phase (Phase-1) is complete when ALL of the following are met:

| Metric | Requirement | Notes |
|---|---|---|
| Duration | 30 calendar days minimum | Count from first live signal, not bot start |
| Trade count | ≥ 50 trades | ST-A2 frequency ~3/month — may require 12+ months |
| No execution errors | 0 ORDER_REJECTED from broker errors | Spread rejects are normal and expected |
| No duplicate orders | 0 cases of same symbol open twice | MAX_OPEN_TRADES=1 enforces this |
| SL placed on every fill | 100% of ORDER_FILLED have SL logged | Verify in trades.jsonl |
| TP placed on every fill | 100% of ORDER_FILLED have TP logged | Verify in trades.jsonl |
| Trade lifecycle fully logged | All 6 event types present in trades.jsonl | SIGNAL_CREATED through POSITION_CLOSED |
| Session-end close working | 0 positions held overnight | Check after each session close |
| Telegram delivery | < 5 missed alerts in 30 days | Check with `grep 'Telegram' logs/bot.log` |
| Drawdown within limits | DD < 10% at all times | bot_state.json peak_equity tracking |
| Net PF (30-day demo) | Track but do NOT gate on it | Sample too small; this is an execution check |

**Important:** Do not use 30-day PF to accept or reject the strategy. With ~3–5 expected
trades per month, no statistically valid PF conclusion is possible at this sample size.
The 30-day phase validates **execution**, not **profitability**. Phase-0 backtest is the
profitability gate.

```bash
# End-of-phase trade lifecycle audit
python3 -c "
import json
from collections import Counter
events = Counter()
with open('logs/trades.jsonl') as f:
    for line in f:
        e = json.loads(line)
        events[e['event']] += 1
for k, v in sorted(events.items()):
    print(f'{k}: {v}')
"

# Check for duplicate order attempts
python3 -c "
import json
fills = []
with open('logs/trades.jsonl') as f:
    for line in f:
        e = json.loads(line)
        if e['event'] == 'ORDER_FILLED':
            fills.append(e['symbol'])
from collections import Counter
c = Counter(fills)
dupes = {k: v for k, v in c.items() if v > 1}
print('Duplicate symbols:', dupes if dupes else 'None')
"
```

---

## Section 6 — Current Blockers

The following must be resolved before activation can proceed:

| # | Blocker | Resolves when | ETA |
|---|---|---|---|
| 1 | OPS-01 7-day stability run incomplete | 2026-06-28 | 2026-06-28 |
| 2 | Daily reports not yet filed (Days 1–7) | Owner fills `docs/OPS01_DAY{N}_REPORT.md` daily | 2026-06-22 → 2026-06-28 |
| 3 | Heartbeat gap audit not yet possible | OPS-01 run completes | 2026-06-28 |

**No code blockers.** All execution layer tests pass (631/631). MetaAPI connection verified
30/30. Reconnect test 4/4. Strategy Phase-0 PASS confirmed.

Earliest activation date (all blockers clear): **2026-06-28** (after OPS-01 Day-7 report filed).

---

## Appendix — Quick-Reference Commands

```bash
# Health check (run before and after activation)
python3 scripts/health_check.py

# Live connection validation (read-only)
python3 scripts/validate_connection.py

# Check LIVE_TRADING guard in .env (must be false until activation)
grep 'LIVE_TRADING' .env

# Check LIVE_TRADING in running bot log
grep 'LIVE_TRADING' logs/bot.log | tail -5

# Count heartbeats today
grep 'HEARTBEAT' logs/bot.log | grep $(date +%Y-%m-%d) | wc -l

# Tail trade events
tail -f logs/trades.jsonl | python3 -c "
import json, sys
for line in sys.stdin:
    e = json.loads(line.strip())
    print(e.get('event'), e.get('symbol'), e.get('detail',''))
"

# Reconnect test (re-run if >14 days since OPS01_RECONNECT_AUDIT.md)
python3 scripts/ops01_reconnect_test.py

# RiskManager state
cat logs/bot_state.json

# Stop bot cleanly
tmux send-keys -t bot 'C-c' Enter

# Start bot in tmux
tmux new-session -d -s bot 'python3 bot.py 2>&1 | tee logs/bot.log'
```

---

*OPS-02 | Demo-Trading Activation Checklist | Session SMC Trading Bot | ST-A2*
*Created: 2026-06-21 | Earliest activation: 2026-06-28 | LIVE_TRADING not changed by agent*
