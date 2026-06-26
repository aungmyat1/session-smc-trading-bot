# Risk Controls: ST-A2 (Session Liquidity Reversal)

## Scope

This document covers risk controls as they exist in the ST-A2 signal chain and adapter code.
Separately specified controls (RISK_SPEC.md, EXECUTION_SPEC.md) that are NOT yet implemented
in code are documented with status NOT IMPLEMENTED.

---

## Risk Control Inventory

### 1. Risk Per Trade

| Field | Value |
|---|---|
| Exists | PARTIAL |
| Specified value | 1% of account (RISK_SPEC.md; CLAUDE.md §4) |
| Implemented value | 0.25% (core.Signal.risk_percent hardcoded in st_a2_adapter.py:69) |
| File | strategies/adapters/st_a2_adapter.py |
| Line | 69 |
| Enforced | NO — risk_percent in core.Signal is a field only; no position sizing code is present in the strategy or adapter. The execution layer (not built/confirmed) would use this value. |
| Notes | DISCREPANCY: adapter sets 0.25%, spec requires 1%. This will underprice risk by 4x if the execution layer uses this field directly. No lot sizing calculation exists anywhere in the strategy or adapter modules. |

---

### 2. Max Daily Loss

| Field | Value |
|---|---|
| Exists | NO (in strategy module) |
| Specified value | 3R per day (RISK_SPEC.md) |
| Implemented value | Not implemented |
| File | — |
| Line | — |
| Enforced | NO |
| Notes | Specified in RISK_SPEC.md and EXECUTION_SPEC.md. The strategy module (session_strategy.py) has no concept of daily P&L state. The execution layer (execution/risk_manager.py per RISK_SPEC.md) is referenced but not confirmed present in this audit scope. |

---

### 3. Max Drawdown (Kill Switch)

| Field | Value |
|---|---|
| Exists | NO (in strategy module) |
| Specified value | 10% from peak equity (RISK_SPEC.md) |
| Implemented value | Not implemented in strategy |
| File | core/circuit_breaker.py (exists in repo, not read in this audit) |
| Line | — |
| Enforced | NO (in strategy module); possibly in core/circuit_breaker.py |
| Notes | CLAUDE.md §4 lists kill_switch: true. RISK_SPEC.md specifies 10% peak DD trigger with manual reset via KILL_SWITCH_OVERRIDE=true. State would be in logs/kill_switch.json per RISK_SPEC.md. The strategy module generates signals regardless of kill switch state. |

---

### 4. Max Positions / Concurrent Positions

| Field | Value |
|---|---|
| Exists | PARTIAL |
| Specified value | 1 per symbol (CLAUDE.md §3); 1 per session per day (RISK_SPEC.md) |
| Implemented value | 1 signal per session per calendar day (session_traded set in session_strategy.py) |
| File | strategy/session_liquidity/session_strategy.py |
| Line | 117, 124-125, 183-184 |
| Enforced | YES (in backtest/signal generation) — one signal per session per day is structurally enforced. The strategy will never emit two London signals or two NY signals for the same day. |
| Notes | This control is enforced in signal generation, not in execution. If the execution layer submits an order for a signal and a position is already open, the strategy module will not know. Concurrent protection across symbols (EURUSD and GBPUSD both in same session on same day) is NOT prevented by the strategy; two signals can be emitted, one per symbol. |

---

### 5. Kill Switch

| Field | Value |
|---|---|
| Exists | NO (in strategy module) |
| Specified value | Drawdown >= 10% halts all trading (RISK_SPEC.md) |
| Implemented value | Not in strategy or adapter |
| File | — |
| Line | — |
| Enforced | NO |
| Notes | LIVE_TRADING=False default (CLAUDE.md §0) prevents live order execution until owner flips it. This is an environment-level control, not a strategy-level control. |

---

### 6. Spread Protection

| Field | Value |
|---|---|
| Exists | PARTIAL |
| Specified value | min_sl_pips >= 5.0 ensures SL is wider than any realistic spread; this is the indirect protection. |
| Implemented value | min_sl_pips = 5.0 filter in session_strategy.py |
| File | strategy/session_liquidity/session_strategy.py |
| Line | 178-182 |
| Enforced | YES — signals with risk_pips < 5.0 are rejected before appending. |
| Notes | No explicit live-spread check. The min_sl_pips filter prevents entries where the fee cost would consume a disproportionate fraction of the risk. No check is performed against live spread at execution time. A widened spread (e.g., during news) would not block signal generation. |

---

### 7. Minimum Asian Range Filter (Indirect Risk Control)

| Field | Value |
|---|---|
| Exists | YES |
| Specified value | EURUSD 15 pips, GBPUSD 20 pips |
| Implemented value | Same |
| File | strategy/session_liquidity/session_strategy.py |
| Line | 106-108 |
| Enforced | YES — days below threshold are skipped before any sweep scanning. |
| Notes | Prevents trading on near-flat market days where spread cost is a large fraction of range. Indirect risk control via signal quality gate. |

---

### 8. Displacement Size Gate (Indirect Risk Control)

| Field | Value |
|---|---|
| Exists | YES |
| Specified value | body > 1.2 × ATR(14) AND close in top/bottom quartile |
| Implemented value | Same |
| File | strategy/session_liquidity/displacement_detector.py |
| Line | 168, 179, 191 |
| Enforced | YES — signals only generated on high-conviction displacement candles. |
| Notes | Ensures entry is only taken when price is moving with momentum, reducing false reversals. |

---

### 9. Max SL Width

| Field | Value |
|---|---|
| Exists | NO (in strategy module) |
| Specified value | 50 pips maximum (RISK_SPEC.md) |
| Implemented value | Not implemented |
| File | — |
| Line | — |
| Enforced | NO |
| Notes | RISK_SPEC.md specifies a 50-pip maximum SL. build_signal() and the session_strategy.py post-filter do not check for an upper bound on risk_pips. A wide sweep wick could produce a signal with a 40+ pip SL. |

---

### 10. Consecutive Loss Limit

| Field | Value |
|---|---|
| Exists | NO (in strategy module) |
| Specified value | 5 consecutive losses (RISK_SPEC.md) |
| Implemented value | Not implemented |
| File | — |
| Line | — |
| Enforced | NO |
| Notes | Requires stateful trade outcome tracking. The strategy module is stateless (pure signal generator). |

---

### 11. Weekly Loss Limit

| Field | Value |
|---|---|
| Exists | NO (in strategy module) |
| Specified value | 6R per week (RISK_SPEC.md) |
| Implemented value | Not implemented |
| File | — |
| Line | — |
| Enforced | NO |
| Notes | Same issue as daily loss limit — requires stateful execution tracking. |

---

### 12. Degenerate Geometry Rejection

| Field | Value |
|---|---|
| Exists | YES |
| Specified value | risk <= 0 is invalid |
| Implemented value | Gate 6 in build_signal: if risk <= 0 return None |
| File | strategy/session_liquidity/entry_engine.py |
| Line | 130 |
| Enforced | YES |
| Notes | Prevents signals where entry price equals or exceeds stop loss price. |

---

## Summary Table

| Control | Exists in Code | Enforced | Gap |
|---|---|---|---|
| risk_per_trade | PARTIAL | NO | 0.25% set vs 1% spec |
| max_daily_loss | NO | NO | Not in strategy module |
| max_drawdown / kill_switch | NO | NO | Not in strategy module |
| max_positions (per session) | YES | YES | Cross-symbol not blocked |
| kill_switch (env flag) | PARTIAL | NOT in strategy | LIVE_TRADING=False is env-level |
| spread_protection (indirect) | YES | YES | min_sl_pips=5.0 |
| min_range filter | YES | YES | |
| displacement quality gate | YES | YES | |
| max_sl_pips (50pip cap) | NO | NO | Not implemented |
| consecutive_loss_limit | NO | NO | Not in strategy module |
| weekly_loss_limit | NO | NO | Not in strategy module |
| degenerate_geometry | YES | YES | |
