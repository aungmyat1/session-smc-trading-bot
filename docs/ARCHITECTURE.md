# Architecture — Session SMC Trading Bot

Strategy: ST-A2 (Session Liquidity + 15M SMC Confirmation)
Version: Post-readiness refactor, 2026-06-28

---

## Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    Operator / Owner                             │
│  (manual CONFIRM tokens | lifecycle promotion | kill switch)    │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Governance Layer                             │
│  session_smc/governance/                                        │
│                                                                 │
│  LifecycleState machine    StrategyRegistry (JSON)             │
│  research_qualified         data/strategy_registry.json         │
│  → verification_ready       Per-state evidence artifacts        │
│  → execution_qualified      Promotion history                   │
│  → risk_qualified                                               │
│  → demo_approved                                                │
│  → demo_live                                                    │
│  → production_live                                              │
└───────────────┬─────────────────────────────────────────────────┘
                │ lifecycle gate check
                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Signal Generation                            │
│  strategy/session_liquidity/                                    │
│                                                                 │
│  Phase 1: Session Definition (London 07-10, NY 13-16 UTC)      │
│  Phase 2: 4H+1H HTF Bias (HH+HL / LL+LH, swing_n=3)          │
│  Phase 3: Session Range Build (High, Low, Midpoint)            │
│  Phase 4: Session Classification (Range / Trend)               │
│  Phase 5: Liquidity Sweep detection                             │
│  Phase 6: 15M CHoCH                                            │
│  Phase 7: 15M BOS                                              │
│  Phase 8: 15M Displacement (>= 1.2× ATR14)                    │
│  Phase 9: 15M FVG Retest (entry zone)                         │
│  Phase 10: Risk Mgmt (SL = tighter of 25%range | wick+3pip)   │
│  Phase 11: Trade Mgmt (TP1 4R 75%, SL->BE, TP2 5R runner)    │
└───────────────┬─────────────────────────────────────────────────┘
                │ Signal object
                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Risk Qualification Layer                     │
│  session_smc/risk/                                              │
│                                                                 │
│  DailyLossGuard    — halt at 3R daily loss                     │
│  DrawdownGuard     — kill switch at 10% from peak              │
│  ConsecutiveLossGuard — halt at 5 consecutive losses           │
│  KillSwitch        — emergency halt, blocks all writes         │
│                                                                 │
│  All guards are fail-closed (deny on uncertainty)              │
└───────────────┬─────────────────────────────────────────────────┘
                │ guard check (pass/halt)
                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Execution Layer                              │
│  execution/                                                     │
│                                                                 │
│  metaapi_client.py     — MetaAPI Cloud SDK wrapper             │
│  order_manager.py      — order lifecycle (fill, retry, cancel) │
│  position_sizer.py     — 1% risk lot sizing                    │
│  risk_manager.py       — circuit breaker state (bot_state.json)│
│  trade_manager.py      — TP1 partial close, SL->BE, session    │
│                          close                                  │
│                                                                 │
│  Execution Qualification Engine (session_smc/execution/)       │
│  — validates cost model, latency, partial fill, reconnect      │
└───────────────┬─────────────────────────────────────────────────┘
                │ order → MetaAPI
                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Broker: VT Markets                          │
│  MetaAPI Cloud SDK (metaapi-cloud-sdk >= 29)                   │
│                                                                 │
│  EURUSD magic: 21001  |  GBPUSD magic: 21002                  │
│  Cost: 0.8-1.2pip spread + 0.6pip commission RT               │
│  Demo account: LIVE_TRADING=false (default, hardcoded gate)    │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    Monitoring Layer                             │
│  session_smc/monitoring/                                        │
│                                                                 │
│  health.py   — process heartbeat, broker connectivity          │
│  drift.py    — slippage/spread anomaly, performance drift      │
│  alerts.py   — Telegram fire-and-forget                        │
│  logger.py   — structured JSON to logs/bot.jsonl               │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Flow

```
Market Data (MetaAPI historical)
        │
        ▼
  OHLCV candles (M15 + 4H)
        │
        ▼
  session_builder.py ──► session range, classification
        │
        ▼
  bias_filter.py ──────► HTF bias (bullish / bearish / neutral)
        │
        ▼
  sweep_detector.py ───► sweep detected (bool + wick price)
        │
        ▼
  displacement_detector.py ► displacement candle (>= 1.2×ATR)
        │
        ▼
  entry_engine.py ────► Signal(direction, entry, sl, tp1, tp2)
        │
        ▼
  [Risk guards check] ─► HALT if any guard fires
        │
        ▼
  [CONFIRM token required from operator]
        │
        ▼
  order_manager.py ───► MetaAPI order placement
        │
        ▼
  trade_manager.py ───► TP1 partial close, SL->BE, session close
        │
        ▼
  trade_journal.py ───► P&L, R-multiple logging
        │
        ▼
  monitoring/alerts.py ► Telegram notification
```

---

## State Machine Diagram

```
RESEARCH_QUALIFIED
        │  evidence: backtest_report (n>=50, PF_2x>1.0)
        ▼
VERIFICATION_READY
        │  evidence: execution_qualification_report
        ▼
EXECUTION_QUALIFIED
        │  evidence: risk_qualification_report
        ▼
RISK_QUALIFIED
        │  evidence: demo_approval_sign_off (owner)
        ▼
DEMO_APPROVED
        │  evidence: demo_start_confirmation
        ▼
DEMO_LIVE ─────────────────────────────────────► SUSPENDED
        │  evidence: demo_completion_report          │
        ▼                                            │
PRODUCTION_CANDIDATE                            ROLLBACK
        │  evidence: production_approval_sign_off
        ▼
PRODUCTION_APPROVED
        │  evidence: production_start_confirmation
        ▼
PRODUCTION_LIVE ──────────────────────────────► SUSPENDED

Any state → REVALIDATION_REQUIRED (parameter change triggers new trial)
REVALIDATION_REQUIRED → RESEARCH_QUALIFIED (after re-registration)
```

---

## Integration Contracts

### MetaAPI Cloud SDK
- Version: `metaapi-cloud-sdk >= 29`
- Auth: `METAAPI_TOKEN` (env) + `METAAPI_ACCOUNT_ID` (env)
- Pattern: async SDK, never raw REST for signed endpoints
- Magic numbers: EURUSD=21001, GBPUSD=21002
- Demo: default — `LIVE_TRADING=false` (hardcoded gate in `run_bot.py`)

### Telegram
- Auth: `TELEGRAM_BOT_TOKEN` (env) + `TELEGRAM_CHAT_ID` (env)
- Pattern: fire-and-forget, failures logged but never raise
- Events: signal_fired, trade_opened, trade_closed, daily_loss_halt,
  drawdown_kill, session_close_with_open, bot_error

### Strategy Registry
- Storage: `data/strategy_registry.json` (JSON lines, atomic write via .tmp)
- Access: `StrategyRegistry` class (thread-safe single-writer)
- Backup: commit registry JSON to git after each lifecycle promotion

---

## Key Directories

```
session_smc/
  governance/    lifecycle.py + registry.py — state machine + JSON store
  execution/     qualification.py — execution scenario validation
  risk/          qualification.py + guards.py — risk gate enforcement
  monitoring/    health.py, drift.py, alerts.py, logger.py
  config.yaml    single source of truth for all constants

strategy/session_liquidity/   signal chain (ST-A2, PASSED Phase-0)
execution/                    MetaAPI client, order/trade/risk managers
scripts/
  run_bot.py                  main CLI entrypoint
  run_backtest.py             Phase-0 gate CLI
  operator_health_check.py    operator health CLI
tests/
  test_governance.py          governance smoke tests
  test_risk_guards.py         risk guard smoke tests
docs/
  VERDICT_LOG.md              trial registry (ST-A2 PASS recorded)
  READINESS_CHECKLIST.md      demo + live readiness tracker
  ARCHITECTURE.md             this file
```
