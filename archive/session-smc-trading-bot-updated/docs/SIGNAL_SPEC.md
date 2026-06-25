# Signal Specification — Session Liquidity + 15M SMC

**Strategy ID:** `SESSION_SMC_A` (Sweep Reversal — Setup A)
**Status:** PENDING Phase-0 gate
**Locked:** TBD — lock before running backtest; any change = new trial

---

## Core Philosophy

> "Wait for smart money to sweep session liquidity, then confirm the reversal
> on 15M with structure (CHoCH + BOS) and momentum (displacement + FVG).
> Enter on the retest — not on the break."

---

## Timeframe Hierarchy

| Role | TF | Purpose |
|------|----|---------|
| Macro bias | 4H | HH+HL bullish / LL+LH bearish (swing_n=3) |
| Bias refine | 1H | Same swing structure, confirms 4H direction |
| Session range | 1H | Session High/Low/Midpoint built in first 2H of session |
| Confirmation | 15M | CHoCH + BOS + displacement after sweep |
| Entry zone | 15M FVG | Limit entry on retrace into displacement gap |

---

## Entry Sequence — Setup A (Sweep Reversal)

ALL conditions are AND-gated. One missing = NO TRADE.

### Pre-filter
- [ ] Session active: London (07:00–10:00 UTC) OR New York (13:00–16:00 UTC)
- [ ] 4H bias non-neutral (HH+HL or LL+LH, swing_n=3)
- [ ] 1H bias agrees with 4H OR is neutral (counter-bias = skip)

### Stage 1 — Session Range (1H)
- [ ] Session High and Low identified from first 2H of session candles
- [ ] Session range ≥ 10 pips (minimum range threshold)
- [ ] Session classified: RANGE (ATR ratio < 0.5) or TREND (ratio > 0.7)

### Stage 2 — Liquidity Sweep (1H)
- [ ] Sell-side sweep (bullish trade): 1H close breaks session Low AND closes back inside range
- [ ] Buy-side sweep (bearish trade): 1H close breaks session High AND closes back inside range
- [ ] Sweep must align with bias: bullish bias → wait for sell-side sweep (equal lows swept)

### Stage 3 — 15M CHoCH (Change of Character)
- [ ] After sweep bar: 15M close breaks the reference swing from the 8 bars before sweep
  - Bullish: 15M close > highest high in 8 bars before sweep
  - Bearish: 15M close < lowest low in 8 bars before sweep

### Stage 4 — 15M BOS (Break of Structure)
- [ ] After CHoCH: 15M close breaks the prior confirmed swing in trade direction
  - Bullish: 15M close > prior 15M swing high (swing_n=3)
  - Bearish: 15M close < prior 15M swing low (swing_n=3)

### Stage 5 — 15M Displacement Candle
- [ ] In sweep→BOS window: at least one 15M candle with range ≥ 1.5×ATR(14) in trade direction
  - Bullish: large bullish body candle
  - Bearish: large bearish body candle

### Stage 6 — 15M FVG Retest (Entry Gate)
- [ ] Displacement candle created a 3-bar FVG:
  - Bullish: high[disp-1] < low[disp+1]
  - Bearish: low[disp-1] > high[disp+1]
- [ ] Current 15M price retraces into this FVG
- [ ] Entry = limit order at FVG midpoint (or market on retest close)

### Stage 7 — Minimum R:R Gate
- [ ] TP1 (4R) distance > 0 from entry
- [ ] Session has ≥ 2 hours remaining (avoid late-session entries)

---

## Execution

| | Value | Source |
|---|---|---|
| **Entry** | Close of 15M bar that retraces into FVG | Stage 6 retest |
| **SL** | Tighter of: sweep wick ± 3pip OR 25% of session range | Stage 2 extreme |
| **TP1 (75%)** | Entry + 4R → move SL to breakeven | Partial lock |
| **TP2 (25%)** | Entry + 5R or nearest session structure | Runner |
| **Session close** | Close remainder at session end if still open | Risk rule |
| **Risk/trade** | 1% of account (config.risk_per_trade = 0.01) | Non-bypassable |

---

## Risk Guards

| Guard | Threshold | Action |
|---|---|---|
| Daily loss | 3R from day-start equity | Halt for the day |
| Max drawdown | 10% from peak | Kill switch |
| Consecutive losses | 5 in a row | Halt until next day |
| Session end | trade still open | Close at market |

---

## Cost Model

| Broker | Spread | Commission | Total RT | Notes |
|---|---|---|---|---|
| VT Markets Standard EURUSD | 0.8 pip | 0.6 pip RT | **1.4 pip** | Standard cost |
| VT Markets Standard GBPUSD | 1.2 pip | 0.6 pip RT | **1.8 pip** | Standard cost |
| Stress test (2×) | 1.6 pip | 1.2 pip RT | **2.8 pip** | Must also pass |

Gate: net PF > 1.0 at BOTH standard AND 2× spread. Single-level pass is insufficient.

---

## What This Is NOT

- Not a prediction system — it reacts to sweep confirmation
- Not proven — Phase-0 gate is the arbiter
- NOT live until Phase-0 AND Phase-1 (30 days paper, 50+ trades) both pass
- NOT based on BTC session logic (session filter failed on BTC T17/T25/T26 — forex is different)

---

## Next Step

Pre-register ST-A in `docs/VERDICT_LOG.md` → implement `scripts/backtest.py`
→ run on 5yr EURUSD+GBPUSD H1/H4 data → log result → decide on ST-B and ST-C.
