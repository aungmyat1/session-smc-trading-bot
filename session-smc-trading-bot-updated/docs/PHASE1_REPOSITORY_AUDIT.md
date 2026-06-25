# PHASE 1 — REPOSITORY AUDIT
# Session SMC Trading Bot (Updated) vs Current Production Bot
**Date:** 2026-06-25 | **Auditor:** Quant Systems Auditor

---

## 1. DIRECTORY STRUCTURE COMPARISON

### Files present in CURRENT bot but MISSING from UPDATED bot (pre-fix)

| Path | Type | Status |
|------|------|--------|
| `data/__init__.py` | Python | ❌ MISSING (added by fix) |
| `data/session_filter.py` | Python | ❌ MISSING (added by fix) |
| `data/forex_data.py` | Python | ❌ MISSING (added by fix) |
| `data/historical/` | CSV data dir | ❌ MISSING (symlinked by fix) |
| `adaptive/data/__init__.py` | Python | ❌ MISSING (added by fix) |
| `adaptive/data/market_feed.py` | Python | ❌ MISSING (added by fix) |
| `scripts/run_portfolio.py` | Script | ❌ MISSING (not needed for ST-A2 demo) |
| `tests/portfolio/` | Test dir | ❌ MISSING (low priority) |
| `data/adaptive_state.json` | Runtime state | ❌ MISSING (generated at runtime) |
| `data/trade_journal.db` | SQLite DB | ❌ MISSING (generated at runtime) |

### Files present in UPDATED bot but NOT in CURRENT bot

| Path | Type | Purpose |
|------|------|---------|
| `execution/mt5_connector.py` | Python | New MT5 connection layer via MetaAPI |
| `execution/vantage_demo_executor.py` | Python | Vantage-specific demo order executor |
| `execution/demo_risk_manager.py` | Python | Demo-phase risk limits (tighter) |
| `core/signal.py` | Python | Canonical Signal dataclass |
| `core/base_strategy.py` | Python | Abstract base for all strategy adapters |
| `core/portfolio_manager.py` | Python | Multi-strategy risk + mode routing |
| `core/signal_router.py` | Python | Demo/shadow signal split |
| `strategies/adapters/*.py` | Python (5 files) | Adapter layer per strategy |
| `strategies/shadow_tracker.py` | Python | Shadow-only signal journal |
| `config/demo.yaml` | YAML | ST-A2 demo phase safety config |
| `config/strategy_portfolio.yaml` | YAML | Multi-strategy portfolio config |

### Files identical between both bots

| Path | Status |
|------|--------|
| `config/config.json` | ✅ IDENTICAL |
| `config/pairs.json` | ✅ IDENTICAL |
| `config/costs.json` | ✅ IDENTICAL |
| `requirements.txt` | ✅ IDENTICAL |
| `session_smc/*.py` (all) | ✅ IDENTICAL |
| `strategy/session_liquidity/*.py` | ✅ IDENTICAL |
| `simulator/forward_test.py` | ✅ IDENTICAL |
| `monitoring/telegram.py` | ✅ IDENTICAL |
| `CLAUDE.md` | ✅ IDENTICAL |
| `Dockerfile` | ✅ IDENTICAL |

---

## 2. CONFIGURATION FILE COMPARISON

### config/config.json — IDENTICAL
- Pairs: EURUSD, GBPUSD
- Magic numbers: 21001 (EURUSD), 21002 (GBPUSD)
- Risk: 0.5% per trade
- Sessions: London 07-10, NY 13-16

### config/demo.yaml — UPDATED (key changes)
| Setting | Current Bot | Updated Bot |
|---------|-------------|-------------|
| `mode` | portfolio demo | ST-A2 Vantage demo |
| `magic_number` | 21099 | 21099 (same) |
| `max_trades_per_day` | 6 | 2 |
| `max_open_positions` | 3 | 1 |
| `daily_loss_limit_pct` | 2.0 | 1.5 |
| `max_consecutive_losses` | 4 | 3 |
| `trade_journal_db` | portfolio_demo_trades | st_a2_demo_trades |
| Pairs | EURUSD, GBPUSD, USDJPY | EURUSD, XAUUSD |

### config/strategy_portfolio.yaml — UPDATED (semantic changes)
- Field renamed: `execution_mode` → `mode`
- Correlation group simplified: 3 groups → 1 group [EURUSD, GBPUSD]
- VWAPBreakout min_confidence: 0.70 → 0.65
- Risk % now config-driven (not hardcoded in adapter)

---

## 3. IMPORT ANALYSIS

### Pre-fix broken imports

```
bot.py:84        from data.session_filter import get_active_session  → ImportError
adaptive/run_shadow.py:65  from data.forex_data import ForexData      → ImportError
adaptive/run_shadow.py:66  from adaptive.data.market_feed import MarketFeed → ImportError
tests/test_session_filter.py:7  from data.session_filter import ...   → ImportError
```

### Post-fix import status (all modules tested)

```
OK  bot
OK  data.session_filter
OK  data.forex_data
OK  adaptive.data.market_feed
OK  execution.metaapi_client
OK  execution.order_manager
OK  execution.risk_manager
OK  execution.mt5_connector
OK  execution.vantage_demo_executor
OK  monitoring.telegram
OK  strategy.session_liquidity.session_strategy
OK  session_smc.structure_detector
OK  session_smc.confirmation_entry
OK  simulator.forward_test
OK  core.signal
OK  core.portfolio_manager
OK  core.signal_router
OK  strategies.adapters.st_a2_adapter (all 5)
--- 0 import errors ---
```

---

## 4. DEPENDENCY COMPARISON

### Python packages — requirements.txt IDENTICAL
Both bots require: `metaapi-cloud-sdk>=29`, `python-telegram-bot`, `python-dotenv`,
`pandas`, `numpy`, `pyyaml`, `aiohttp`, `requests`, `pytest`, `pytest-asyncio`

### Runtime dependencies
| Dependency | Current Bot | Updated Bot |
|------------|-------------|-------------|
| MetaAPI account | `METAAPI_ACCOUNT_ID` | `VANTAGE_DEMO_METAAPI_ID` (should be) |
| data/ module | Present | ❌ Missing → **Fixed** |
| adaptive/data/ | Present | ❌ Missing → **Fixed** |
| Historical CSVs | data/historical/ | data/historical/ (symlinked) |

---

## VERDICT

| Check | Result |
|-------|--------|
| Directory structure | ✅ PASS (after deployment fix) |
| Python imports | ✅ PASS (after deployment fix) |
| Config files | ✅ PASS |
| Requirements | ✅ PASS |
| Strategy logic | ✅ UNCHANGED (no modifications) |

**Deployment fix applied:** Copied `data/` and `adaptive/data/` modules from production bot.
Historical data symlinked (no duplication). Strategy logic untouched.
