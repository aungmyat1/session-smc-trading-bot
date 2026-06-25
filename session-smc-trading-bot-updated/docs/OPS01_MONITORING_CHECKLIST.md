# OPS01_MONITORING_CHECKLIST.md
# OPS-01 — 7-Day Operational Monitoring Dashboard
# Purpose: daily health check during ST-A2 paper trade stability run

---

## Pass Criteria (fill at end of Day 7)

| Criterion | Target | Actual |
|---|---|---|
| Bot starts successfully | ✅ | |
| Heartbeat active (every 5 min) | ✅ | |
| Reconnect logic works | ✅ | |
| State survives restart | ✅ | |
| Logging valid (no corruption) | ✅ | |
| No duplicate orders | ✅ | |
| No critical runtime errors | ✅ | |
| LIVE_TRADING remains false | ✅ | |

---

## Daily Log

### Day 1 — Start Date: ___________

| Metric | Value | Notes |
|---|---|---|
| Uptime % | | |
| Reconnect count | | |
| Errors (grep ERROR logs/bot.log) | | |
| Heartbeats received | | |
| Signals generated | | |
| Orders submitted (DRY_RUN) | | |
| Orders rejected | | |
| Open position EOD | | |
| LIVE_TRADING | false | must stay false |

**Commands:**
```bash
grep HEARTBEAT logs/bot.log | wc -l          # heartbeat count
grep SIGNAL_CREATED logs/trades.jsonl | wc -l  # signals
grep ORDER_SUBMITTED logs/trades.jsonl | wc -l  # orders
grep ERROR logs/bot.log | wc -l              # errors
```

---

### Day 2

| Metric | Value | Notes |
|---|---|---|
| Uptime % | | |
| Reconnect count | | |
| Errors | | |
| Heartbeats | | |
| Signals | | |
| Orders | | |
| Orders rejected | | |
| Open position EOD | | |
| Notes | | |

---

### Day 3

| Metric | Value | Notes |
|---|---|---|
| Uptime % | | |
| Reconnect count | | |
| Errors | | |
| Heartbeats | | |
| Signals | | |
| Orders | | |
| Orders rejected | | |
| Open position EOD | | |
| Notes | | |

---

### Day 4

| Metric | Value | Notes |
|---|---|---|
| Uptime % | | |
| Reconnect count | | |
| Errors | | |
| Heartbeats | | |
| Signals | | |
| Orders | | |
| Orders rejected | | |
| Open position EOD | | |
| Notes | | |

---

### Day 5

| Metric | Value | Notes |
|---|---|---|
| Uptime % | | |
| Reconnect count | | |
| Errors | | |
| Heartbeats | | |
| Signals | | |
| Orders | | |
| Orders rejected | | |
| Open position EOD | | |
| Notes | | |

---

### Day 6

| Metric | Value | Notes |
|---|---|---|
| Uptime % | | |
| Reconnect count | | |
| Errors | | |
| Heartbeats | | |
| Signals | | |
| Orders | | |
| Orders rejected | | |
| Open position EOD | | |
| Notes | | |

---

### Day 7

| Metric | Value | Notes |
|---|---|---|
| Uptime % | | |
| Reconnect count | | |
| Errors | | |
| Heartbeats | | |
| Signals | | |
| Orders | | |
| Orders rejected | | |
| Open position EOD | | |
| Notes | | |

---

## 7-Day Summary

| Metric | Total / Result |
|---|---|
| Total uptime % | |
| Total reconnects | |
| Total errors | |
| Total heartbeats | |
| Total signals | |
| Total orders submitted | |
| Total orders rejected | |
| Duplicate orders | must be 0 |
| LIVE_TRADING violations | must be 0 |

---

## OPS-01 Verdict (fill Day 7)

```
[ ] Bot starts successfully
[ ] Heartbeat active every 5 min
[ ] Reconnect logic verified
[ ] State survives restart
[ ] Logging valid, no corruption
[ ] No duplicate orders
[ ] No critical runtime errors
[ ] LIVE_TRADING=false throughout

VERDICT: [ ] PASS  [ ] FAIL
```

---

## Daily Log Commands (copy-paste)

```bash
# Status check
tmux ls
tail -20 logs/bot.log

# Counts
echo "Heartbeats: $(grep -c HEARTBEAT logs/bot.log)"
echo "Errors:     $(grep -c ' ERROR ' logs/bot.log)"
echo "Signals:    $(grep -c SIGNAL_CREATED logs/trades.jsonl 2>/dev/null || echo 0)"
echo "Orders:     $(grep -c ORDER_SUBMITTED logs/trades.jsonl 2>/dev/null || echo 0)"
echo "Rejected:   $(grep -c ORDER_REJECTED logs/trades.jsonl 2>/dev/null || echo 0)"

# Verify no duplicates (all signal timestamps should be unique)
python3 -c "
import json; from pathlib import Path
events = [json.loads(l) for l in Path('logs/trades.jsonl').read_text().splitlines() if l.strip()]
sigs = [e for e in events if e['event']=='SIGNAL_CREATED']
keys = [f\"{e.get('symbol','')}:{e.get('ts','')[:16]}\" for e in sigs]
dupes = [k for k in keys if keys.count(k) > 1]
print(f'Signals: {len(sigs)}  Duplicates: {len(set(dupes))}')
" 2>/dev/null || echo "No trade log yet"

# Verify LIVE_TRADING never enabled
grep -i "live_trading=true\|LIVE=True" logs/bot.log | wc -l  # must be 0
```

---

## Escalation

If any of these occur, STOP the bot and investigate before resuming:

| Event | Action |
|---|---|
| `LIVE_TRADING=true` in logs | STOP immediately. Check .env. Never auto-restart. |
| Duplicate ORDER_SUBMITTED for same signal | STOP. Review dedup logic. |
| Uncaught exception in bot.py main loop | Investigate stack trace before restart. |
| `bot_state.json` corrupted | Restore from last known good, verify circuit breakers. |
| Balance drops (unexpected in DRY_RUN) | STOP. DRY_RUN should never affect real balance. |

*OPS-01 | Monitoring Checklist | 2026-06-21*
