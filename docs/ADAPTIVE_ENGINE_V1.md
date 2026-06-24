# Adaptive Session Engine v1

**Status:** DEMO FRAMEWORK — not deployed, not live  
**Mode:** DRY_RUN=true (no order placement)  
**Protected systems:** SMC Session Liquidity strategy, E6 pipeline, spread research — untouched

---

## Architecture

```
adaptive/
├── strategies/
│   ├── __init__.py               AdaptiveSignal dataclass (shared contract)
│   ├── smc_session_strategy.py   Adapter — wraps existing session_liquidity/
│   ├── london_breakout_strategy.py
│   └── ny_momentum_strategy.py
├── engine/
│   ├── regime_detector.py        ATR + ADX classifier
│   ├── signal_scorer.py          0-10 scoring gate
│   ├── risk_manager.py           Daily/consecutive/correlation guards
│   └── trade_router.py           Pipeline orchestrator (APPROVED/REJECTED only)
└── config/
    └── adaptive_engine.yaml      All parameters — single source of truth
```

Tests: `tests/adaptive_engine/` (isolated, does not affect existing tests)

---

## Signal Flow

```
Strategy Signal (AdaptiveSignal)
        │
        ▼
Regime Filter (regime_detector)
  UNSAFE → REJECTED
  regime not suited for strategy → REJECTED
        │
        ▼
Signal Score (signal_scorer)
  score < 7 → REJECTED
        │
        ▼
Risk Check (risk_manager)
  daily loss / trade count / consecutive / correlation → REJECTED
        │
        ▼
APPROVED  ←→  DRY_RUN=true → log only, no order
```

---

## Modules

### regime_detector.py
- Inputs: OHLCV candle list + spread_pips
- Outputs: `{"regime": str, "confidence": float, "adx": float, "atr_pct": float, ...}`
- States: TRENDING | BREAKOUT | RANGING | UNSAFE
- Pure Python — no numpy/pandas
- Wilder-smoothed ATR(14) and ADX(14) computed from scratch

### signal_scorer.py
- Inputs: AdaptiveSignal + runtime context dict
- Outputs: `{"score": int, "approved": bool, "breakdown": dict}`
- Scoring table (max 10):

| Criterion | Points |
|---|---|
| HTF bias aligned | +2 |
| Liquidity event | +2 |
| Structure confirmation | +2 |
| Active session | +1 |
| Spread acceptable | +1 |
| Volatility acceptable | +1 |
| News clear | +1 |

Trade threshold: score ≥ 7

### risk_manager.py
- Stateless across calls — caller persists the state dict
- Per-trade risk: 0.5% (configurable)
- Daily loss limit: 1.5% → halt
- Max trades/day: 6
- Max consecutive losses: 3 → halt
- Correlation guard: blocks LONG EURUSD + LONG GBPUSD simultaneously

### trade_router.py
- Orchestrates the 3-stage pipeline
- DRY_RUN=true (default, reads env var): logs APPROVED decisions, places no orders
- Writes JSON log lines to `logs/adaptive_engine.log`
- Live execution path exists but is blocked until DRY_RUN=false AND CONFIRM token flow (CLAUDE.md §6)

---

## Strategies

### smc_session_strategy.py
- Thin adapter over the existing `strategy/session_liquidity/session_strategy.py`
- Does NOT modify the original strategy
- Converts `Signal` → `AdaptiveSignal` format
- `metadata.liquidity_swept = True`, `metadata.structure_confirmed = True` (preconditions of SA)

### london_breakout_strategy.py
- Pairs: EURUSD, GBPUSD, USDJPY
- Asian range: 00:00–06:00 UTC
- Valid range: 15–50 pips
- Entry: close beyond Asian H/L + retest
- SL: opposite Asian extreme
- TP: 1.5R

### ny_momentum_strategy.py
- Reference: London High / London Low (06:00–09:00 UTC)
- NY window: 11:00–15:00 UTC
- Entry: sweep + close beyond London level + retest
- SL: opposite London extreme
- TP: 2R

---

## Risk Rules

```yaml
per_trade:             0.5%
daily_loss_limit:      1.5%  → halt
max_trades_per_day:    6
max_consecutive_losses: 3    → halt
correlation:           block LONG EURUSD + LONG GBPUSD
```

---

## Demo Procedure

1. Set `DRY_RUN=true` in environment (default)
2. Feed live or historical M15 + H4 OHLCV data to each strategy module
3. Pass resulting `AdaptiveSignal` objects through `trade_router.route_signal()`
4. Monitor `logs/adaptive_engine.log` for APPROVED/REJECTED decisions
5. Collect 30–60 signals minimum before comparing against E6 validated strategy

---

## Log Format

Every signal routed is written to `logs/adaptive_engine.log` as a JSON line:

```json
{
  "ts": "2026-06-24T07:30:00+00:00",
  "module": "trade_router",
  "event": "route_signal",
  "strategy": "london_breakout",
  "pair": "EURUSD",
  "direction": "LONG",
  "session": "london",
  "regime": "RANGING",
  "score": 8,
  "decision": "APPROVED",
  "reason": "",
  "dry_run": true
}
```

---

## Known Limitations

1. **No live data feed** — strategies require caller to supply candles; no MetaAPI integration yet
2. **News filter** — `news_event` defaults to False; no live news source wired
3. **USDJPY pip size** — set to 0.01; confirm broker tick size before enabling
4. **SMC adapter** — if `strategy.session_liquidity` package unavailable, returns empty list silently
5. **No persistence** — risk state resets between process restarts; caller must save/restore state dict
6. **ADX requires 29+ bars** — regime is UNSAFE with fewer bars (2 × period + 1)

---

## Next Recommended Action

1. Run demo/shadow mode against live market data
2. Collect 30–60 signals across all three strategies
3. Compare signal frequency, regime distribution, and score distribution against E6 validated baseline
4. Review correlation between strategies (how often do multiple fire on the same bar?)
5. Only after 30-day clean paper run: propose Phase-1 wiring to MetaAPI
