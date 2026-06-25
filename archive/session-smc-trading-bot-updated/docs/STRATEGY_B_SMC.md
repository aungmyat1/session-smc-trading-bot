# STRATEGY_B_SMC.md
# Strategy B — Full SMC Confirmation
# v1.0 | PENDING — blocked on Strategy A gate

---

## Status

**LOCKED.** Do not implement until Strategy A passes Phase-0 backtest gate.

Gate: Trades ≥ 100, PF > 1.0 at standard AND 2× spread stress.

---

## Concept

Session range sweep + 15M structural confirmation (CHoCH + BOS + displacement + FVG retest).

**Differentiating element vs T27/T28/ST-1:** the 15M CHoCH + BOS + FVG retest layer.
This has not yet been backtested. All prior failures lacked LTF confirmation.

---

## 11-Phase Signal Chain (AND-gated)

```
Phase 1  Session Definition       London 07–10 UTC | NY 13–16 UTC
Phase 2  HTF Bias (4H + 1H)       HH+HL bullish / LL+LH bearish (swing_n=3)
Phase 3  Session Range Build       High, Low, Midpoint, Range for current session
Phase 4  Session Classification    Range (low ATR) | Trend (strong BOS + displacement)
Phase 5  Liquidity Sweep           Session H/L breached + close back inside range
Phase 6  15M CHoCH                 Close breaks ref swing after sweep (lookback=8)
Phase 7  15M BOS                   Structural break in trade direction post-CHoCH
Phase 8  15M Displacement          ≥ 1.5×ATR(14) candle in trade direction
Phase 9  15M FVG Retest            Entry on retrace into displacement FVG
Phase 10 Risk Management           SL = tighter(25% range | sweep wick + 3pip buffer)
Phase 11 Trade Management          TP1 4R close 75% → SL→BE → TP2 5R+ runner
```

---

## Setup Types

| Setup | Condition | Priority |
|---|---|---|
| A — Sweep Reversal | HTF bias + sweep + 15M CHoCH + BOS | Highest |
| B — Trend Pullback | Trend session + pullback to midpoint + 15M BOS | Medium |
| C — Range Fade | Range session + rejection at extreme + 15M rejection | Lowest |

---

## Key Parameters (LOCKED until backtest)

- swing_n = 3 (4H + 1H bias)
- CHoCH lookback = 8 bars
- Displacement ATR mult = 1.5×
- SL = tighter(25% session range, sweep wick + 3pip)
- TP1 = 4R (close 75%), TP2 = 5R+ runner
- Broker: VT Markets Standard — EURUSD 1.4pip RT, GBPUSD 1.8pip RT

---

## File Layout (target)

```
strategy/smc/           (to be renamed from session_smc/ after Strategy A gate)
  swing_detector.py
  structure_detector.py
  liquidity_detector.py
  poi_detector.py
  confirmation_entry.py
```

---

## Open Trials

| Trial | Setup | Status |
|---|---|---|
| ST-A | Sweep Reversal (Setup A) | PENDING Phase-0 backtest |
| ST-B | Trend Pullback (Setup B) | PENDING ST-A result |
| ST-C | Range Fade (Setup C) | PENDING ST-A result |

---

## Known Failures (do not re-propose)

| Trial | Strategy | Result | Root Cause |
|---|---|---|---|
| T27 | EURUSD session sweep | PF=0.58 FAIL | No LTF confirmation |
| T28 | GBPUSD session sweep | PF=0.95 FAIL 2× | No LTF confirmation |
| T29-EUR | EURUSD BOS-retest | PF=0.83 FAIL | No edge before fees |
| T29-GBP | GBPUSD BOS-retest | 2× stress FAIL | Marginal, fragile |
| ST-1 | Session IB sweep + CHoCH | FAIL | Entry at CHoCH close too far; SL too wide |
