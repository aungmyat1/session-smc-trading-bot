# Live Capital Scaling Plan
# Research-09 — Staged Deployment from Demo to Scale
# Date: 2026-06-23 | Policy document — no code

---

## Purpose

Define the staged capital deployment plan from demo to live trading. Each stage
has explicit entry conditions, position-sizing rules, risk limits, monitoring
requirements, and rollback triggers. No stage may be skipped. LIVE_TRADING=True
may only be set by the owner — never by the agent.

**Current state:** Stage 1 (Demo). OPS-01 stability run in progress through 2026-06-28.

---

## Stage 1 — Demo Account (Current)

| Field | Value |
|---|---|
| **Account** | VT Markets Demo — VantageMarkets-Demo |
| **Capital** | $1,000 (paper) |
| **Risk per trade** | 1% of account ($10/trade) |
| **LIVE_TRADING** | `false` |
| **Status** | ACTIVE — OPS-01 in progress |

### Entry conditions (all met ✅)
- [x] Phase-0 backtest PASS (ST-A2: PF_2x=1.025, n=169)
- [x] MetaAPI connection validated (DEP-02)
- [x] Execution layer tested (66/66 tests)
- [x] Health check 9/9 PASS

### Objectives
- Validate signal chain fires correctly on live 15M OHLCV data
- Confirm order placement, SL, TP, and session-close execution have no bugs
- Run 7-day OPS-01 stability gate (no manual restart)
- Collect n ≥ 30 paper trades for win-rate and PF sanity check

### Risk limits
- Max daily loss: 3R ($30)
- Max consecutive losses: 5
- Max drawdown: 10% ($100) — kill switch
- Weekly loss cap: 6R ($60)

### Rollback / halt conditions
- More than 2 unhandled exceptions in 24 hours → halt and investigate
- MetaAPI sync failure persisting > 24 hours → halt, file bug report
- Signal fires but order is not placed (execution bug) → halt immediately
- HEARTBEAT gap > 10 minutes without auto-recovery → manual restart + investigation

### Promotion gate to Stage 2
- [ ] OPS-01 7-day run complete (no restart) — 2026-06-28
- [ ] n ≥ 30 paper trades completed (low frequency: may take 30–90 days at ~3/month)
- [ ] Zero critical execution failures (wrong SL, wrong TP, double-entry, missed close)
- [ ] MetaAPI uptime ≥ 90% of session hours
- [ ] Owner manual review of all trade logs

---

## Stage 2 — $100 Live

| Field | Value |
|---|---|
| **Account** | VT Markets Standard — Live account |
| **Capital** | $100 |
| **Risk per trade** | 0.5% ($0.50/trade) |
| **LIVE_TRADING** | `true` — set by owner only after Stage 1 gate |
| **Min lot** | 0.01 (micro lot — minimum position size for VT Markets) |
| **Status** | BLOCKED — pending Stage 1 promotion gate |

### Purpose
Validate execution in live market conditions: real spread, real slippage, real order
rejection. Micro position size ($0.50 risk) limits financial exposure while producing
real execution data that demo cannot provide.

### Entry conditions (none met yet)
- [ ] Stage 1 promotion gate cleared
- [ ] Live VT Markets account funded ($100)
- [ ] MetaAPI account created for live account (separate account ID from demo)
- [ ] `.env` updated with live account ID and LIVE_TRADING=true (owner action)
- [ ] Slippage monitoring confirmed working (execution_analyzer.py)

### Objectives
- Measure real slippage vs demo (expected: 0.1–0.5 pip on EURUSD, higher at news)
- Confirm real spread matches VT Markets quoted (0.8 pip EURUSD / 1.2 pip GBPUSD)
- Validate partial-close execution (TP1: 75% close, SL→BE)
- Confirm Telegram alerts fire on order fill (not just signal)

### Risk limits
- Max daily loss: 3R ($1.50)
- Max consecutive losses: 5 → halt
- Max drawdown: 20% of stage capital ($20) → kill switch
- Max weekly loss: 5R ($2.50)
- No manual parameter changes during this stage — every observation is data

### Rollback / stop-trading conditions
- Any order fills at price > 1 pip from signal price → halt, investigate broker latency
- Spread at entry > 2× quoted spread on 2+ trades → alert, monitor for widening pattern
- 3 consecutive SL hits where SL was not placed correctly → critical bug, halt immediately
- Account equity < $80 (20% drawdown from $100) → kill switch, stop all trading

### Promotion gate to Stage 3
- [ ] n ≥ 20 live trades at Stage 2 (at 0.5% risk, low exposure)
- [ ] Slippage average < 0.5 pip (within execution model assumptions)
- [ ] No critical execution failures (SL/TP placed correctly on all trades)
- [ ] Real spread matches expected on ≥ 90% of fills
- [ ] Net R at Stage 2 is not catastrophically negative (> −10R over n ≥ 20)

---

## Stage 3 — $500 Live

| Field | Value |
|---|---|
| **Account** | VT Markets Standard — Live account (same as Stage 2) |
| **Capital** | Add $400 (total $500, less Stage 2 losses/gains) |
| **Risk per trade** | 1% ($5.00/trade) |
| **Lot size** | 0.05 micro lots typical (varies by SL pip distance and equity) |
| **Status** | BLOCKED — pending Stage 2 gate |

### Purpose
Validate performance at meaningful position sizes. At $5 risk per trade, a 5R win
is $25 — large enough to detect real slippage impact, but small enough that a 10%
drawdown ($50) is recoverable.

### Entry conditions
- [ ] Stage 2 promotion gate cleared
- [ ] Owner decision to add $400 to live account
- [ ] No open positions at time of capital addition
- [ ] Position sizer updated for new equity (automatic — reads from MetaAPI)

### Objectives
- Validate that PF in live conditions approaches the backtest result (ST-A2: 1.025–1.151)
- Confirm drawdown patterns match expectations (max ~19R at standard conditions)
- Collect n ≥ 30 live trades at 1% risk

### Risk limits
- Max daily loss: 3R ($15)
- Max consecutive losses: 5 → halt for current day
- Max drawdown: 10% of equity ($50) → kill switch
- Max weekly loss: 6R ($30)

### Monitoring additions
- Weekly review of symbol breakdown (EURUSD vs GBPUSD win rates vs backtest)
- Session breakdown monitoring (London win rate alert if < 20% over 15+ trades)
- Quarterly check: if live PF trails backtest PF by > 30%, file as ST-A3 candidate

### Rollback / stop-trading conditions
- Drawdown reaches 10% ($50) → kill switch, full review before restart
- London win rate < 15% over 20+ London trades → halt London trades, report
- EURUSD win rate < 20% over 20+ EURUSD trades → halt EURUSD, report
- n consecutive losses > 7 → halt all trading, 48-hour review
- Any sign of strategy degradation (10-trade rolling PF < 0.70) → alert

### Promotion gate to Stage 4
- [ ] n ≥ 50 live trades at Stage 3 completed
- [ ] Net PF at Stage 3 > 0.80 (below backtest expectation, but demonstrates partial edge)
- [ ] No critical execution failures at any point in Stage 3
- [ ] No kill-switch triggered by drawdown
- [ ] Owner review and written approval

---

## Stage 4 — $1,000 Live

| Field | Value |
|---|---|
| **Account** | VT Markets Standard — Live account |
| **Capital** | $1,000 |
| **Risk per trade** | 1% ($10/trade) |
| **Lot size** | 0.1 micro lots typical |
| **Status** | BLOCKED — pending Stage 3 gate |

### Purpose
Reach the capital level where the strategy's expected value translates to meaningful
returns. At $10 risk / 5R TP = $50 per full trade, the strategy generates ~$150/year
in expected value at ST-A2 PF_std (positive, but below fee-adjusted minimum wage).

Stage 4 is where the strategy is evaluated for long-term viability and whether
Strategy B (SMC Reversal) should be onboarded to increase portfolio frequency and
expected return.

### Entry conditions
- [ ] Stage 3 promotion gate cleared
- [ ] Owner written decision
- [ ] Equity bridge from Stage 3 (add funds to reach $1,000 net of losses/gains)

### Risk limits
- Max daily loss: 3R ($30)
- Max consecutive losses: 5 → halt for current day
- Max drawdown: 10% ($100) → kill switch, full review
- Max weekly loss: 6R ($60)

### Objectives
- Produce a statistically meaningful live PF over n ≥ 50 trades
- Provide data for Strategy B (SMC) deployment decision
- Establish execution benchmark for comparison with future strategies

---

## Stage 5 — Scale (Owner Decision Only)

Scaling beyond $1,000 requires:

1. **100 live trades** across all stages (Stage 2 + 3 + 4 combined), with no critical
   execution failures at any point.
2. **Live PF > 1.0** (net, after real spreads and commissions) on the most recent 50 trades.
3. **No critical execution failures** — defined as: wrong SL distance, missed TP1 partial
   close, duplicate position opened, session-close rule not firing.
4. **Owner written approval** for each capital increment.

Scale increments: $1,000 → $2,500 → $5,000 → $10,000. Each increment requires 50 new
live trades at the new equity level without triggering a kill switch.

At $10,000 capital with 1% risk per trade, a position is $100 risk with standard lot
sizing. Maximum drawdown of 10% is $1,000 — the entire Stage 4 capital. No automated
increment beyond $10,000 without a formal portfolio review.

---

## Universal Risk Controls (All Stages)

These controls are enforced in code (`execution/risk_manager.py`) and cannot be
disabled by the agent:

| Control | Value | Override |
|---|---|---|
| Risk per trade | 1% of equity (0.5% at Stage 2) | Never — hardcoded |
| Max daily loss | 3R → halt today | Owner restart only |
| Max consecutive losses | 5 → halt until next UTC day | Auto-reset at midnight |
| Max drawdown | 10% from peak → kill switch | Owner restart only |
| LIVE_TRADING flag | False until owner sets it | Owner only |
| Max open trades per symbol | 1 | Never — architectural |
| Session close rule | Close all at session end | Disabled only for Strategy C |

---

## Stop-Trading Conditions (Permanent)

The following conditions trigger permanent stop-trading until resolved by owner:

1. **Execution bug confirmed** — SL/TP not placed correctly on any trade.
2. **MetaAPI account credentials revoked** — broker disabled account.
3. **Negative equity** — account equity < $0 at any stage.
4. **Strategy invalidation signal** — new market structure evidence that ST-A2's
   Phase-0 assumptions no longer hold (e.g. VT Markets changes spread model,
   session hours change structurally).
5. **Kill switch triggered twice in 30 days** — indicates a regime the strategy
   cannot handle. Full strategic review before any restart.

---

## Capital Plan Summary

| Stage | Capital | Risk/Trade | Frequency | Purpose |
|---|---|---|---|---|
| 1 — Demo | $1,000 (paper) | 1% / $10 (paper) | ~3/month | Execution validation |
| 2 — Live | $100 | 0.5% / $0.50 | ~3/month | Real market validation |
| 3 — Small | $500 | 1% / $5 | ~3/month | Meaningful PF measurement |
| 4 — Standard | $1,000 | 1% / $10 | ~3/month | Full strategy evaluation |
| 5 — Scale | $1,000+ | 1% / variable | ~3/month + B | Portfolio growth |

**Expected annual R at ST-A2 backtest PF (169 trades / 4.9yr = 34.5/yr):**
- Stage 3: 34.5 × avg_R(0.108) × $5 = ~$19/year (net, before compounding)
- Stage 4: 34.5 × 0.108 × $10 = ~$37/year
- Stage 5 at $5,000: ~$186/year

These are expected values, not guarantees. Actual returns depend on live vs
backtest PF convergence. The primary goal of Stages 2–4 is validation, not profit.

---

*This document is policy only. No code was modified. LIVE_TRADING remains false.*
*All stage transitions require owner decision and manual action.*
