# Readiness Checklist — Session SMC Trading Bot

Strategy: **ST-A2** (Session Liquidity + 15M SMC Confirmation)
Instruments: EURUSD, GBPUSD
Broker: VT Markets Standard via MetaAPI

Last updated: 2026-06-28

---

## Demo-Readiness Checklist

### Phase-0 Gate (Backtest)
- [x] Strategy spec pre-registered in VERDICT_LOG.md before backtest
- [x] 5-year holdout backtest complete: n=169 (>= 50 required)
- [x] Net PF at standard spread: 1.151 (> 1.0 required)
- [x] Net PF at 2× spread stress: 1.025 (> 1.0 required)
- [x] ST-A2 verdict: **PASS** (run 20260621T100458-183aaa)
- [x] Result registered in VERDICT_LOG.md

### Governance
- [x] Lifecycle state machine implemented (`session_smc/governance/lifecycle.py`)
- [x] Strategy registry implemented (`session_smc/governance/registry.py`)
- [ ] ST-A2 registered in `data/strategy_registry.json` with state `verification_ready`
- [ ] Lifecycle promoted to `execution_qualified` (execution qualification report attached)
- [ ] Lifecycle promoted to `risk_qualified` (risk qualification report attached)
- [ ] Lifecycle promoted to `demo_approved` (owner sign-off)

### Execution Qualification
- [x] Execution qualification engine implemented (`session_smc/execution/qualification.py`)
- [x] Cost model validated: EURUSD 1.6pip RT, GBPUSD 2.1pip RT
- [x] Scenarios: typical fill, 2× stress, partial fill, reject+retry, timeout, disconnect
- [ ] Qualification run against MetaAPI demo account (live connectivity test)
- [ ] Fill latency confirmed < 500ms (typical), < 2000ms (stress)

### Risk Qualification
- [x] Risk qualification engine implemented (`session_smc/risk/qualification.py`)
- [x] Guard suite: DailyLossGuard, DrawdownGuard, ConsecutiveLossGuard, KillSwitch
- [x] Smoke tests passing (`tests/test_risk_guards.py`)
- [ ] Guards integrated into `bot.py` main loop

### Infrastructure
- [x] Config single source of truth (`session_smc/config.yaml`)
- [x] Structured JSON logger (`session_smc/monitoring/logger.py`)
- [x] Health monitor (`session_smc/monitoring/health.py`)
- [x] Drift detector (`session_smc/monitoring/drift.py`)
- [x] Telegram alerter (`session_smc/monitoring/alerts.py`)
- [x] `scripts/run_bot.py` entrypoint with governance check
- [x] `scripts/operator_health_check.py`
- [x] `Makefile` with install/test/lint/backtest/health targets
- [x] `.github/workflows/ci.yml` lint + test CI
- [ ] MetaAPI demo account credentials in `.env`
- [ ] Telegram bot configured in `.env`
- [ ] `logs/` directory writable

### 30-Day Paper Trade Gate
- [ ] MetaAPI demo account operational
- [ ] Bot running in demo mode for >= 30 days
- [ ] >= 50 demo trades executed
- [ ] No execution bugs (fill errors, incorrect SL/TP, position leaks)
- [ ] Demo P&L consistent with backtest expectation (+/- 20%)

---

## Live-Readiness Checklist

All demo-readiness items above, plus:

### Capital Allocation
- [ ] Account funded with Phase-2 Micro capital ($200–$500)
- [ ] Risk per trade confirmed at 0.5% (Phase-2 rate)
- [ ] Slippage verified within model (< 0.3 pip average)

### Operator Controls
- [ ] `LIVE_TRADING=true` set manually by owner (not agent)
- [ ] Emergency stop procedure documented and tested
- [ ] Kill switch accessible from Telegram alert
- [ ] Drawdown circuit breaker tested in staging

### Monitoring
- [ ] Telegram alerts confirmed working (sent test message)
- [ ] Log rotation configured
- [ ] VPS/server monitoring (uptime, memory, disk)
- [ ] Automatic restart on crash configured (systemd or supervisor)

### Regulatory / Broker
- [ ] VT Markets account KYC complete
- [ ] MetaAPI token has correct permission scope (trade + account read)
- [ ] Understand broker's force-close / margin call rules

---

## Current Status Summary

| Layer | Status |
|---|---|
| Phase-0 backtest gate | PASSED (ST-A2) |
| Governance code | IMPLEMENTED |
| Execution qualification engine | IMPLEMENTED |
| Risk qualification engine | IMPLEMENTED |
| Monitoring layer | IMPLEMENTED |
| Registry populated | PENDING |
| Lifecycle promoted to demo_approved | PENDING |
| Demo account credentials | PENDING |
| 30-day paper trade | PENDING |
| Live trading | BLOCKED |
