# ST-A2 Demo Risk Policy
# Phase: Demo validation (Phase 1)
# Source: config/demo.yaml + CLAUDE.md §4

---

## Governing Rules (CLAUDE.md §0 — non-bypassable)

1. LIVE_TRADING = False until Phase-0 gate PASSES AND 30-day demo runs clean.
2. No parameter tuning mid-trial. Every change = new trial ID in VERDICT_LOG.md.
3. One position per symbol at all times.
4. Net-of-fees only. Backtest results without spread are invalid.
5. Never commit secrets. All keys stay in .env (gitignored).
6. Phase-0 gate is mandatory: n ≥ 50, net PF > 1.0 at standard AND 2× spread.

---

## Position Sizing

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Risk per trade | 0.25% of balance | Conservative — demo phase only; raises to 0.50% on Phase 2 |
| SL method | Tighter of: 25% session range OR sweep wick + 3pip buffer | Strategy rule, do not override |
| TP1 | 4R → close 75%, SL → breakeven | Strategy rule |
| TP2 | 5R+ or session structure target | Strategy rule |
| Max lot size | 0.50 | Hard cap in `demo_risk_manager.py` |
| Min lot size | 0.01 | MetaTrader minimum |

---

## Daily Risk Limits (Phase 1 — conservative)

| Limit | Threshold | Action |
|-------|-----------|--------|
| Max trades per day | 2 | Halt trading for the day |
| Max open positions | 1 | Block new orders |
| Daily loss limit | 1.5% of account | Halt all trading for the day |
| Weekly loss limit | 4.0% | Halt until weekly review |
| Monthly loss limit | 7.0% | Stop demo, review required |
| Consecutive losses | 3 | Halt + 4-hour cooldown via CircuitBreaker |

---

## Allowed Instruments (Phase 1)

| Pair | Max Spread | Pip Size | Pip Val/Lot |
|------|-----------|----------|-------------|
| EURUSD | 1.5 pip | 0.0001 | $10 |
| XAUUSD | 3.0 pip | 0.1 | $10 |

GBPUSD excluded from Phase 1 demo: identified as primary drag in ST-A FAIL (VERDICT_LOG.md ST-A). Will be re-evaluated after 30 EURUSD/XAUUSD trades.

---

## Prohibited Behaviors

| Behavior | Status |
|----------|--------|
| Martingale (double-up after loss) | PROHIBITED |
| Averaging down (add to losing position) | PROHIBITED |
| Unlimited order retries on failure | PROHIBITED (max 1 retry) |
| Aggressive recovery (oversized next trade) | PROHIBITED |
| Auto-enable live trading | PROHIBITED (LIVE_TRADING is owner-only) |
| Parameter tuning during trial | PROHIBITED (new trial ID required) |

---

## Session Close Rule

If a trade is still open at session end (London 10:00 UTC or NY 16:00 UTC), the runner logs a session-close warning. Manual review decides whether to close. Auto-close is NOT implemented in Phase 1 (requires 30-trade observation first).

---

## Kill Switch

The `emergency_close_all()` method in `execution/trade_manager.py` closes all ST-A2 demo positions filtered by magic=21099. Run manually:

```python
# From scripts/health_check.py -- interactive prompt
python3 -c "
import asyncio, sys
sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv('.env')
from execution.mt5_connector import MT5Connector
from execution.vantage_demo_executor import VantageDemoExecutor
from execution.trade_manager import TradeManager

async def emergency():
    c = MT5Connector('demo'); await c.connect()
    m = TradeManager(VantageDemoExecutor(c))
    n = await m.emergency_close_all()
    print(f'Closed {n} positions')
    await c.disconnect()

asyncio.run(emergency())
"
```

---

## Config Source

All parameters in this document are derived from `config/demo.yaml`.
Do not hard-code risk values in code — always read from config or `demo_risk_manager.py` constants.

Last reviewed: 2026-06-24
Next review: After first 10 demo trades.
