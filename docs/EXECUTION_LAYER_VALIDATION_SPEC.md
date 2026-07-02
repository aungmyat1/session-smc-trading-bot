# Execution Layer Validation — Design Reference
# Recorded 2026-06-29

Status: Authoritative
Version: 1.0
Updated: 2026-06-29
Owner: Platform
Authority: Level 5 — Phase Specification
Note: EVF is a separate subsystem from SVOS VIRTUAL_DEMO. VIRTUAL_DEMO is
offline research; EVF validates execution quality after research qualification.
Related: SVOS_DESIGN_REFERENCE.md, HISTORICAL_REPLAY.md

Conformance: execution-layer validation is evidence produced within SVOS
Virtual Demo Trading. It is not a third production-like system or an additional
lifecycle stage between Robustness Testing and Virtual Demo Trading. System 2
remains the simple execution engine defined by the Original Truth.

---

## The Core Distinction

A profitable strategy is only **halfway** through the institutional validation process.

The most common mistake: assuming profitable historical replay means ready for live trading.

Professional trading firms treat the **strategy** and the **execution system** as two
separate systems that each require independent validation.

| System | The question it answers |
|---|---|
| Strategy | *When should I trade?* |
| Execution Layer | *Can I actually execute those trades correctly in the real market?* |

These are different questions. A flawless strategy can lose money through a broken
execution layer. An execution layer can be technically correct while the strategy has
no edge. Both must be validated independently before capital is allocated.

---

## Full Institutional Workflow

```
Idea
  │
  ▼
Strategy Design
  │
  ▼
Strategy Audit          (logical correctness)
  │
  ▼
Historical Replay       (event-by-event validation)
  │
  ▼
Backtest                (statistical validation)
  │
  ▼
Statistical Validation  (evidence gate)
  │
  ▼
Robustness Testing      (OOS, walk-forward, Monte Carlo)
  │
  ▼
Virtual Demo Trading    (includes execution-layer validation)
  │
  ▼
Production Approval
```

---

## Execution Layer — 10 Validation Components

### 1. Signal Translation

Verify that every research signal becomes exactly one execution instruction with no
missing or altered parameters.

Research signal:
```
BUY EURUSD | Entry = 1.16230 | SL = 1.16130 | TP = 1.16430 | Risk = 0.30%
```

Bot must submit: correct symbol, correct volume, correct SL, correct TP — exactly.
Any alteration is a signal translation failure.

---

### 2. Position Sizing

Confirm that the risk calculation, lot size, contract size, pip value, and
instrument-specific point calculations are all correct.

Instrument-specific checks:
- EURUSD pip calculation
- XAUUSD point calculation (different contract spec)
- Leverage applied correctly

Verification format:
```
Expected risk: $30.00
Actual loss if SL hit: $29.98
Result: PASS (within tolerance)
```

---

### 3. Broker Mapping

Ensure all broker-specific parameters are correctly mapped:
- Symbol names (broker may use EURUSD vs EURUSDm)
- Trading sessions (broker timezone vs strategy timezone)
- Minimum lot, lot step
- Stop level, freeze level
- Leverage per instrument

A signal that is correct in research may be rejected by the broker due to symbol
mismatch or stop level violation. This must be tested, not assumed.

---

### 4. Order Placement

Test every order type and lifecycle:
- Market order
- Pending order (buy limit, sell limit, buy stop, sell stop)
- Modification (SL/TP changes after fill)
- Cancellation
- Partial fills (if broker supports)
- Retry logic on rejection

---

### 5. Slippage Measurement

Research assumes clean fill at signal price. Live execution differs.

Research assumption: `Entry = 1.16230`
Live execution: `Entry = 1.16237`

Measure and track:
- Average slippage (pips)
- Median slippage
- Worst-case slippage

If slippage exceeds the tolerance assumed in the robustness tests, the execution
layer fails — not the strategy.

---

### 6. Spread Handling

Research may assume 0.8 pip spread. Live may be 2.4 pips at certain times.

Verify:
- Spread filter correctly blocks trades when spread exceeds threshold
- Trade rejection logic fires at the right threshold
- Spread captured at signal time matches what was assumed

---

### 7. Latency Measurement

Every millisecond between signal and fill is measurable risk.

Full latency chain:
```
Signal generated     → 09:30:00.150
Order sent           → 09:30:00.185   (+35ms)
Broker acknowledged  → 09:30:00.240   (+55ms)
Filled               → 09:30:00.252   (+12ms)
Total: 102ms
```

Measure: average latency, worst-case latency, distribution. Compare against the
latency assumptions implicit in the backtest (typically: instant fill).

---

### 8. State Recovery

Simulate operational failures and verify the bot recovers correctly:

| Scenario | Expected behavior |
|---|---|
| Bot restart | Reloads all open positions, restores state |
| Internet loss | Reconnects, no duplicate orders, no missed closes |
| MT5 disconnect | Reconnects, position state reconciled with broker |
| VPS reboot | Full state restored from persistent store |

The bot must never open a duplicate order after recovery, and must never leave a
position unmanaged after reconnect.

---

### 9. Risk Controls

Every protection must be tested deliberately — not assumed to work.

| Control | Test |
|---|---|
| Max daily loss | Trigger it. Confirm all new entries blocked. |
| Max open trades | Exceed the limit. Confirm rejection. |
| Per-symbol exposure | Open maximum. Confirm next attempt blocked. |
| Session filter | Generate signal outside session. Confirm rejected. |
| Emergency stop | Activate. Confirm all activity halts. |

---

### 10. Logging and Audit Trail

Every trade must be fully reconstructable from logs.

Required trace sequence:
```
Signal Generated
  → Rule Evaluation (which rules fired, values)
  → Risk Calculation (lot size derivation)
  → Order Submitted (exact parameters sent to broker)
  → Broker Response (fill price, timestamp)
  → Position Open (confirmed state)
  → Position Closed (close price, P&L)
  → Performance Recorded (running metrics updated)
```

If anything goes wrong, the full sequence must be reconstructable from logs alone —
no gaps, no inferred steps.

---

## What Demo Trading Proves

Demo trading is **not** for discovering whether the strategy has an edge. That is
already established by replay, backtest, and robustness tests before reaching this
stage.

Demo trading validates **operational performance only**:

| Question | Expected answer |
|---|---|
| Are trades being opened correctly? | Yes |
| Is lot sizing accurate? | Yes |
| Are SL/TP placed correctly? | Yes |
| Is spread filtering working? | Yes |
| Is slippage within expectations? | Yes |
| Does the bot recover after restart? | Yes |
| Are logs complete? | Yes |
| Do executed trades match research signals? | ≥ 95–99% match |

The 95–99% match threshold accounts for expected execution differences (slippage,
spread variance) while catching genuine translation errors or logic failures.

---

## Full Validation Checklist Before Capital Allocation

```
Strategy Audit              PASS
Historical Replay           PASS
Backtest                    PASS
Walk Forward                PASS
Monte Carlo                 PASS
Execution Validation        PASS
Demo (4–8 weeks)            PASS
Production Readiness Review PASS

→ Allocate Small Capital
→ Scale Based on Live Performance
```

Every line must be PASS. No partial credit. No "good enough."

---

## What This Makes the Platform

The platform does not answer only: *"Was this strategy profitable?"*

It answers: *"Has every component — from logic to execution — been validated well
enough to justify risking capital?"*

```
Market Data
  │
Feature Engineering
  │
Strategy Definition
  │
Strategy Audit Engine
  │
Historical Replay
  │
Backtesting Engine
  │
Robustness Validation
  │
Execution Validation Engine
  │
Demo Validation
  │
Production Readiness Score
  │
Capital Allocation Decision
```

This is the difference between a **research platform** and a **capital allocation
decision engine**. The final output is not a backtest report — it is a justified
yes or no on whether to risk real money.
