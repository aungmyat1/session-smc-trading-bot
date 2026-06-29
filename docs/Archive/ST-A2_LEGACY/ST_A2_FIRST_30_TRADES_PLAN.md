# ST-A2 — First 30 Demo Trades Protocol
# Phase 1: Demo Validation
# Reference: CLAUDE.md §3 Phase 1 — Paper trade 30 days, 50+ trades, no execution bugs

---

## Objective

Collect 30 demo trades on the Vantage MT5 demo account to:
1. Validate execution quality (entry slippage, SL/TP placement, order fill confirmation)
2. Confirm strategy signal frequency matches backtest expectations
3. Detect any execution bugs before live capital is involved
4. Establish a live win rate, profit factor, and avg-R baseline

Phase 1 success does NOT guarantee Phase 2 approval. It only clears the "no execution bugs" gate.

---

## Trade Rules (Non-Bypassable)

| Rule | Value |
|------|-------|
| Allowed pairs | EURUSD, XAUUSD only |
| Max trades per day | 2 |
| Max open positions | 1 at any time |
| Risk per trade | 0.25% of account |
| Daily loss limit | 1.5% |
| Parameter changes | PROHIBITED mid-protocol (new trial ID required) |
| Manual override | PROHIBITED — all signals from strategy only |
| Live trading | PROHIBITED until Phase 2 gate |

---

## Recording — Every Trade Must Log

All fields automatically written to `data/trade_journal.db` by the runner.
After each session, verify the trade was recorded:

```python
python3 -c "
from core.trade_journal_db import TradeJournalDB
import json
db = TradeJournalDB()
for t in db.get_open_trades():
    print(json.dumps(t, indent=2, default=str))
"
```

Fields captured per trade:
- `timestamp` — UTC signal generation time
- `strategy_name` — ST-A2
- `symbol` — EURUSD or XAUUSD
- `direction` — long / short
- `signal_price` — price at signal generation
- `entry_price` — actual fill price (update on close)
- `stop_loss`, `take_profit` — levels sent to broker
- `position_size` — lot size
- `risk_percentage` — 0.25%
- `router_result`, `breaker_result`, `portfolio_result` — pipeline audit trail
- `execution_result` — OPEN / SHADOW / BLOCKED / ERROR
- `broker_order_id` — from MetaAPI
- `close_price`, `profit_loss`, `r_multiple` — filled on close
- `reason_for_exit` — tp_hit / sl_hit / session_close / manual

---

## Review Schedule

### After Every 10 Trades

Run this query and record results:
```python
python3 -c "
from core.trade_journal_db import TradeJournalDB
import json
db = TradeJournalDB()
s = db.summary()
print(json.dumps(s, indent=2))
"
```

Compare against baseline targets below. If any RED threshold is hit, STOP and review.

### 10-Trade Targets (minimum viability)

| Metric | Target | STOP threshold |
|--------|--------|---------------|
| Win rate | ≥ 30% | < 20% (3 consecutive losses = halt) |
| Avg R per closed trade | ≥ +0.3R | < -1.0R cumulative |
| Execution fill vs signal | < 1 pip slippage | > 3 pip consistently |
| SL placement confirmed | 100% of trades | Any trade without SL = STOP |
| Orders filled without error | 100% | Any ERROR execution_result = review |
| Daily loss limit hit | 0 times | 2+ times in first 10 = review config |

### 30-Trade Phase 1 Gate (minimum to consider Phase 2)

| Metric | Gate Value | Rationale |
|--------|-----------|-----------|
| Total trades | ≥ 30 | CLAUDE.md §3 Phase 1 minimum |
| Net profit factor | > 1.0 | Strategy has edge in live execution |
| Win rate | ≥ 25% | Consistent with 4R/5R TP structure |
| Avg R | ≥ +0.2R | After fees and slippage |
| Execution error rate | 0% | No order bugs allowed |
| Max drawdown | < 5% of account | Demo capital protection |
| Consecutive loss halt triggers | ≤ 1 | If ≥ 2, strategy config review required |

**All gates must PASS.** One FAIL = Phase 2 postponed, new investigation required.

---

## Tracking Log

### Trade-by-Trade Ledger

| # | Date | Pair | Dir | Entry | SL | TP | Exit | R | Notes |
|---|------|------|-----|-------|----|----|------|---|-------|
| 1 | | | | | | | | | |
| 2 | | | | | | | | | |
| 3 | | | | | | | | | |
| ... | | | | | | | | | |

*Fill this manually from data/trade_journal.db after each trade closes.*

---

### 10-Trade Review Notes

**Review at trade 10:**
- Date:
- Win: / Loss: / Break-even:
- Avg R:
- Execution quality notes:
- Any errors or anomalies:
- Decision: [ ] Continue  [ ] Pause and review  [ ] STOP

**Review at trade 20:**
- Date:
- Win: / Loss: / Break-even:
- Cumulative avg R:
- Execution quality notes:
- Decision: [ ] Continue  [ ] Pause and review  [ ] STOP

**Review at trade 30:**
- Date:
- Win: / Loss: / Break-even:
- Net profit factor:
- Maximum drawdown:
- Execution error count:
- Phase 2 decision: [ ] APPROVED  [ ] EXTEND DEMO  [ ] ABORT

---

## What to Watch

### Execution Quality
- **Fill vs signal price:** Large slippage (>2 pip) indicates broker re-quote or latency issue.
- **SL/TP confirmation:** Broker must confirm SL and TP levels via `get_positions()`. Log if either is missing.
- **Order ID in journal:** Every demo trade must have a non-SHADOW `broker_order_id`. Shadow entries indicate DEMO_ONLY was still true.

### Strategy Compliance
- **Signal rate:** Expect 2–4 signals per week per pair (backtest frequency ÷ 5yr period).
- **Session filter:** All signals must fire during London (07–10 UTC) or NY (13–16 UTC).
- **Setup type:** Confirm each signal follows the Phase 2–9 signal chain (sweep → CHoCH → BOS → FVG entry).

### Risk State
- After each trade, confirm `check_limits()` is returning correct values.
- Monitor `data/trade_journal.db` for `execution_result="ERROR"` rows — any such row needs investigation.

---

## Metrics Reference (From Backtest)

These are the Phase-0 backtest benchmarks for context:
- Net PF (standard spread): > 1.0 at RR5 (ST-A2 internal spec)
- Win rate: ~31.5% (ST-A FAIL data point — ST-A2 targets similar range)
- Avg winning R: ~4.0 (TP1 target = 4R)
- Avg losing R: ~-1.0 (full SL)

If live demo metrics significantly diverge (e.g. win rate < 20% over 30 trades), the strategy has an execution problem or the signal spec is degraded. Do not proceed to live without understanding the divergence.

---

## Phase 2 Unlock Conditions

**All of the following must be true:**

1. ≥ 30 demo trades completed (not shadow — actual demo broker orders)
2. Net profit factor > 1.0 over those 30 trades
3. Zero execution errors (ERROR rows in trade_journal.db)
4. No daily loss limit hit more than once
5. Manual review by owner of the trade-by-trade ledger above
6. Owner manually sets LIVE_TRADING=true in .env (agent cannot do this)

Phase 2 is micro-live: $200–500 capital, 0.5% risk, verify slippage vs demo.
