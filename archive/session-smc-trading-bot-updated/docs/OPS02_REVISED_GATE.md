# OPS02_REVISED_GATE.md
# Demo-Trading Gate — Owner-Approved Revision
# ST-A2 | Session Liquidity Reversal
# Proposal date: 2026-06-24 | Owner approved: 2026-06-24
# Status: ACTIVE — supersedes OPS02_ACTIVATION_CHECKLIST.md Section 5

---

## Owner Decision Record

**Date:** 2026-06-24

**Decision:** APPROVED — revised gate replaces the original 30-day / 50-trade requirement.

**Owner rationale (verbatim):**

> "The original requirement: 30 days AND 50 trades does not fit ST-A2.
> Your own backtest shows 169 trades over ~5 years = ~2.88 trades/month.
> Therefore 50 trades ÷ 2.88 ≈ 17.4 months — the original checklist is mathematically impossible.
> Demo is NOT for proving profitability. Profitability was already tested in ST-A, ST-A2, EXP01, EXP05."

**What demo validates:**
1. Execution — can orders actually be placed?
2. Position sizing — is risk calculation correct?
3. State persistence — can the bot restart safely?
4. Session timing — are London and NY sessions detected correctly?
5. Broker integration — can MetaAPI survive disconnects?
6. Logging — do all events appear correctly in trades.jsonl?

---

## Statistical Foundation

| Metric | Value | Source |
|---|---|---|
| Backtest trades | 169 | Run 20260621T100458-183aaa |
| Period | ~4.9yr | 2021–2026 |
| Trades/month | ~2.88 | 169 ÷ 4.9yr ÷ 12 |
| Original 50-trade target | ~17.4 months to achieve | 50 ÷ 2.88 |
| Net PF (2× stress) | 1.025 | Placeholder cost — MUST revalidate |
| PF margin above gate | 0.025 | Thin — cost validation is critical |

**Original gate status: REPLACED.** The 30+50 requirement is retained in
`docs/OPS02_ACTIVATION_CHECKLIST.md` for reference but is no longer the governing gate.

---

## Revised Gate — Owner Version

### E5 + E6 — Cost Validation (MUST complete before E1–E4)

**E6 is the most important remaining item.** The current `active_profile` is
`PLACEHOLDER_vt_markets_assumption` — the ST-A2 PASS is still based on VT Markets
assumptions, not real Vantage costs. Cost revalidation must precede any execution monitoring.

#### E5 — Spread Capture

- Run `scripts/capture_spreads.py` across killzone hours
- Collect: **≥ 5 London sessions AND ≥ 5 NY sessions** (not 30 days)
- Output: `research/spread_samples.csv`
- See `docs/SPREAD_CAPTURE_PLAN.md` for exact tmux command and monitoring procedure

Start command (export fix applied):
```bash
set -a; source .env; set +a && tmux new-session -d -s spreads \
  'python3 scripts/capture_spreads.py --commission-pips 0.0 --interval 30 \
   2>&1 | tee logs/spread_capture.log'
```

**Pass condition:** ≥ 5 London + ≥ 5 NY sessions in `research/spread_samples.csv`

#### E6 — Cost Revalidation

- Update `config/costs.json` → `profiles.vantage_measured` with measured killzone averages
- Set `active_profile = "vantage_measured"`
- Re-run ST-A2 backtest: `python3 scripts/backtest_session_liquidity.py`

**Decision table:**

| Result | Meaning | Action |
|---|---|---|
| PF_2x > 1.05 | Edge confirmed, meaningful margin | Continue to E1–E4 |
| PF_2x 1.00–1.05 | Edge marginal but positive | Demo only — proceed to E1–E4, no micro-live until confirmed |
| PF_2x < 1.00 | Strategy invalidated at real costs | **STOP. No demo. No live.** Prepare `docs/ST_A3_RECOVERY_OPTIONS.md` |

**Hard gate: PF_2x < 1.00 → demo does not begin.**

---

### E1 — 7-Day Runtime

Bot runs 7 consecutive days with LIVE_TRADING=true.

| Requirement | Pass condition |
|---|---|
| No crashes | 0 unplanned process exits |
| No freezes | Heartbeat gaps < 600 seconds throughout |
| Watchdog clean | `health_check.py` → no 🔴 on any daily check |
| Reconnect logic works | Any disconnects → reconnected within 30s |
| State file survives restart | `bot_state.json` intact after E4 restart test |

**Pass: 7/7 days clean.**

```bash
# Daily verification command
python3 scripts/health_check.py

# Heartbeat gap check
grep 'HEARTBEAT' logs/bot.log | awk '{print $1}' | \
  python3 -c "
import sys, datetime
lines = [l.strip().strip('[]') for l in sys.stdin if l.strip()]
for i in range(1, len(lines)):
    a = datetime.datetime.fromisoformat(lines[i-1])
    b = datetime.datetime.fromisoformat(lines[i])
    gap = (b - a).total_seconds()
    if gap > 600:
        print(f'GAP {gap:.0f}s between {lines[i-1]} and {lines[i]}')
print(f'Checked {len(lines)-1} intervals')
"
```

---

### E2 — At Least One Signal

Not one filled trade — one signal. ST-A2 generates ~2.88 trades/month.
A signal that is rejected (spread too wide, duplicate blocked) still validates the detection chain.

| Requirement | Pass condition |
|---|---|
| SIGNAL_CREATED appears | ≥ 1 line in `logs/trades.jsonl` with `event=SIGNAL_CREATED` |
| Signal fields correct | `symbol`, `session`, `side`, `sl_pips`, `tp_r` all present and valid |

```bash
# Check for signals
grep 'SIGNAL_CREATED' logs/trades.jsonl | wc -l    # ≥ 1

# Inspect signal fields
python3 -c "
import json
with open('logs/trades.jsonl') as f:
    for line in f:
        e = json.loads(line)
        if e.get('event') == 'SIGNAL_CREATED':
            print(e)
"
```

**Pass: ≥ 1 signal with correct fields.**

---

### E3 — At Least One Order Lifecycle

Either a filled trade or a valid rejection. Both are acceptable pass conditions.

| Acceptable outcome | What it validates |
|---|---|
| ORDER_FILLED → POSITION_CLOSED | Full execution pipeline: sizing, order placement, position management, close |
| ORDER_REJECTED (spread too wide) | Signal → order attempt → broker rejection → clean state recovery |
| ORDER_REJECTED (duplicate blocked) | Concurrency guard working — MAX_OPEN_TRADES=1 enforced |

**Pass: one full lifecycle observed** (signal → order attempt → terminal state).

```bash
# Check lifecycle
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
```

If a trade fills, additionally verify in MetaAPI dashboard:
- [ ] Magic number correct (EURUSD=21001 | GBPUSD=21002)
- [ ] SL placed at fill
- [ ] TP placed at fill
- [ ] Lot size consistent with 1% risk on account equity

---

### E4 — Manual Restart Test

Perform on Day 2 or Day 3 of the 7-day run.

```bash
# Stop
tmux send-keys -t bot C-c
sleep 5

# Confirm stopped
pgrep -f 'python3 bot.py' | wc -l    # expect 0

# Check state file before restart
cat logs/bot_state.json

# Restart
tmux send-keys -t bot 'python3 bot.py 2>&1 | tee -a logs/bot.log' Enter

# Verify startup within 60s
sleep 30 && grep 'LIVE_TRADING' logs/bot.log | tail -3
```

| Check | Pass condition |
|---|---|
| Reconnects | `MetaAPI connected` or `CONNECTED` in log within 60s |
| No duplicate orders | 0 new ORDER_SUBMITTED events within 5 min of restart |
| State preserved | `bot_state.json` values unchanged after restart |
| LIVE_TRADING guard | Log shows `LIVE_TRADING=True` (not reverted to False) |

**Pass: restart clean — state intact, no spurious orders, reconnected.**

---

## Gate Sequence

```
E5 — Spread capture (5 London + 5 NY sessions)
  └── E6 — Cost revalidation → PF_2x check
        └── PF_2x ≥ 1.00 → proceed
              │
              ▼
E1 — 7-day runtime (LIVE_TRADING=true)
E4 — Manual restart test (Day 2–3, inside E1 window)
E2 — Signal validation (≥1 signal during E1 window)
E3 — Order lifecycle validation (during E1 window)
              │
              ▼
All pass → Micro-Live Decision
```

E1, E2, E3, E4 run concurrently inside the 7-day window. E4 is a single event within E1.

**E5+E6 must complete before E1 begins.** No execution monitoring while cost validation is pending.

---

## Micro-Live Parameters (post-gate)

If all gates pass, owner-stated micro-live parameters:

| Parameter | Value |
|---|---|
| Account | $1,000 Vantage live |
| Risk per trade | 0.25% |
| Max open positions | 1 |
| Validation period | First 20 trades |
| Size increase condition | Live results consistent with ST-A2 expectations after 20 trades |

Max theoretical exposure: $1,000 × 0.25% × 18.72R (backtest max DD) = **$46.80 max drawdown scenario** at micro-live scale. Kill switch (10% DD = $100) fires well before that.

---

## What Is NOT Gated

The following are monitored but do not gate micro-live:

- **30-day PF** — sample is too small for statistical validity; this was Phase-0's job
- **Trade count** — frequency is a property of the market, not the bot
- **Win rate in demo** — 3–5 expected demo trades; no WR conclusion is possible
- **TP1 partial-close path** — exercised in simulation (43/43 forward tests); if not
  triggered in 7 days, document and proceed. Expected wait at 2.88/month.

---

## Superseded Document

`docs/OPS02_ACTIVATION_CHECKLIST.md` Section 5 (Success Metrics) is replaced by this gate.
Sections 1–4 and Section 6 of the checklist remain operative:
- Section 1 (Preconditions): OPS-01 still required
- Section 2 (Activation Procedure): unchanged
- Section 3 (Monitoring): unchanged
- Section 4 (Rollback): unchanged
- Section 6 (Current Blockers): superseded by E5+E6

---

## Current Status

| Gate | Status |
|---|---|
| E5 — Spread capture | PENDING — awaiting CONFIRM-SPREAD-CAPTURE |
| E6 — Cost revalidation | BLOCKED on E5 |
| OPS-01 stability (prerequisite) | In progress — expires 2026-06-28 |
| E1 — 7-day runtime | BLOCKED on E5+E6 |
| E2, E3, E4 | BLOCKED on E1 |
| Micro-live decision | BLOCKED on all gates |

**Fastest path to micro-live: ~14–21 days from spread capture start.**

---

*OPS02_REVISED_GATE.md | Owner-approved 2026-06-24 | No code changes | Agent does not change LIVE_TRADING*
