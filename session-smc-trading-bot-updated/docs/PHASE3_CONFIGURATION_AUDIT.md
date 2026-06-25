# PHASE 3 — CONFIGURATION AUDIT
# Session SMC Trading Bot (Updated)
**Date:** 2026-06-25

---

## 1. ENVIRONMENT VARIABLE INVENTORY

### Required at runtime

| Variable | Used In | Safe Default | Status |
|----------|---------|-------------|--------|
| `METAAPI_TOKEN` | bot.py, mt5_connector.py | `""` (fails gracefully with RuntimeError) | ✅ In .env |
| `METAAPI_ACCOUNT_ID` | bot.py line 72 | `""` | ⚠️ **CONFLICT** — see Phase 4 |
| `VANTAGE_DEMO_METAAPI_ID` | mt5_connector.py (mode=demo) | `""` | ✅ In .env |
| `VANTAGE-LIVE-METAAPI-ID` | mt5_connector.py (mode=live) | `""` | ✅ In .env |
| `TELEGRAM_BOT_TOKEN` | monitoring/telegram.py | `""` (alerts silently skipped) | ✅ In .env |
| `TELEGRAM_CHAT_ID` | monitoring/telegram.py | `""` | ✅ In .env |
| `LIVE_TRADING` | bot.py, mt5_executor.py | `"false"` ✓ | ✅ In .env |
| `DEMO_ONLY` | vantage_demo_executor.py | `"true"` ✓ | ✅ In .env |

### All env vars accessed with safe `.get()` / default fallbacks
No bare `os.environ["KEY"]` calls found in the hot path. All use `os.getenv(KEY, default)` or `os.environ.get(KEY, default)`. **No env-var KeyError risk.**

---

## 2. CONFIG FILE AUDIT

### config/config.json — VALID

```json
{
  "pairs": ["EURUSD", "GBPUSD"],
  "poll_interval_seconds": 60,
  "sessions": {"london": {"start":"07:00","end":"10:00"}, "newyork": {"start":"13:00","end":"16:00"}},
  "risk": {"risk_per_trade_pct": 0.5, "max_open_trades": 2, "max_consecutive_losses": 5},
  "magic_numbers": {"EURUSD": 21001, "GBPUSD": 21002},
  "spread_pips": {"EURUSD": 0.8, "GBPUSD": 1.2},
  "pip_value_per_lot": {"EURUSD": 10.0, "GBPUSD": 10.0}
}
```

**KeyError risks in execution/risk_manager.py:**
```python
r = config["risk"]                    # direct access — KeyError if "risk" missing
self.pip_value_per_lot = config["pip_value_per_lot"]  # same
```
**Risk level:** LOW — config.json is present and has both keys. Only fails if file is corrupt.

### config/demo.yaml — VALID (Phase 1 demo settings)

| Key | Value | Assessment |
|-----|-------|-----------|
| `execution.mode` | `demo` | ✅ Correct for demo phase |
| `execution.demo_only` | `true` | ✅ Redundant guard (belt + suspenders) |
| `execution.magic_number` | `21099` | ✅ Isolated from production (21001/21002) |
| `trading.allowed_pairs` | `[EURUSD, XAUUSD]` | ⚠️ XAUUSD has no historical data — replay will be EURUSD only |
| `trading.max_spread_pips.EURUSD` | `1.5` | ✅ Appropriate for Vantage demo |
| `trading.max_spread_pips.XAUUSD` | `3.0` | ✅ Appropriate for gold |
| `risk.risk_per_trade_pct` | `0.25` | ✅ Conservative (vs 0.5% in config.json) |
| `risk.max_trades_per_day` | `2` | ✅ Phase 1 conservative |
| `risk.max_open_positions` | `1` | ✅ Single position during validation |
| `risk.daily_loss_limit_pct` | `1.5` | ✅ Tight halt threshold |
| `risk.max_consecutive_losses` | `3` | ✅ Early halt on loss streak |
| `logging.demo_journal` | `logs/st_a2_demo_trades.jsonl` | ✅ Bot-specific filename |
| `circuit_breaker.max_signals_per_hour` | `4` | ✅ Prevents signal burst |

### config/strategy_portfolio.yaml — VALID

| Strategy | Mode | Risk % | Assessment |
|----------|------|--------|-----------|
| ST-A2 | demo | 0.30% | ✅ Core validated strategy, correct mode |
| LondonBreakout | demo | 0.20% | ✅ Conditionally validated |
| NYMomentum | demo | 0.20% | ✅ Conditionally validated |
| AdaptiveSMC | shadow | 0.10% | ✅ Observe-only, correct mode |
| VWAPBreakout | shadow | 0.10% | ✅ Observe-only, correct mode |

---

## 3. SYMBOL CONFIGURATION

| Symbol | config.json | demo.yaml | strategy_portfolio.yaml | Historical Data |
|--------|------------|-----------|------------------------|-----------------|
| EURUSD | ✅ | ✅ | ✅ | ✅ 2021–2026 |
| GBPUSD | ✅ | ❌ (excluded) | ✅ | ✅ 2023–2026 |
| USDJPY | ❌ | ❌ | ✅ (LB/NY only) | ❌ No data |
| XAUUSD | ❌ | ✅ | ❌ | ❌ No data |

**Mismatch:** demo.yaml includes XAUUSD but no historical data exists. Bot will skip XAUUSD
in replay. In live demo, XAUUSD price feed works but no historical signal validation.

---

## 4. RISK CONFIGURATION CROSS-CHECK

| Parameter | config.json | demo.yaml | CLAUDE.md §4 |
|-----------|------------|-----------|-------------|
| Risk per trade | 0.5% | 0.25% | 1% (Phase 3+) |
| Max daily loss | 3R | 1.5% | 3R |
| Max drawdown | — | — | 10% |
| Max consec losses | 5 | 3 | 5 |
| Kill switch | — | disabled_behaviors | true |

**Assessment:** demo.yaml is MORE conservative than CLAUDE.md §4 defaults. This is appropriate
for Phase 1 validation. No over-leverage risk.

---

## 5. KEYERROR RISK REGISTER

| Location | Access Pattern | Keys | Risk |
|----------|---------------|------|------|
| `execution/risk_manager.py` | `config["risk"]` | `risk` | LOW — key exists in config.json |
| `execution/risk_manager.py` | `config["pip_value_per_lot"]` | `pip_value_per_lot` | LOW — key exists |
| `bot.py` | `config["pairs"]` | `pairs` | LOW — key exists |
| `bot.py` | `config.get("magic_numbers", {})` | safe | ✅ |
| `execution/order_manager.py` | `config.get(...)` throughout | all safe | ✅ |

**Recommendation:** Wrap `config["risk"]` in risk_manager.py with `.get("risk", {})` as hardening,
but this is NOT a deployment blocker.

---

## VERDICT

| Check | Result |
|-------|--------|
| Required env vars covered | ✅ PASS |
| Config files present and valid | ✅ PASS |
| KeyError risks | ✅ PASS (low risk, config is complete) |
| Risk parameters safe for demo | ✅ PASS (conservative) |
| Symbol / data consistency | ⚠️ PARTIAL — XAUUSD configured but no data |
| Session times correct | ✅ PASS |
