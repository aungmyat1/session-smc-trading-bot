# Risk Controls: London Breakout

All risk controls found across the codebase for the London Breakout strategy.
Controls are evaluated across both operational paths (Portfolio Runner and Adaptive
Shadow Runner).

---

## Core Risk Controls

### risk_per_trade

| Attribute | Value |
|-----------|-------|
| Exists? | PARTIAL — three conflicting values |
| Portfolio config value | 0.20% (`config/strategy_portfolio.yaml` line 30) |
| Adaptive engine default | 0.50% (`adaptive/engine/risk_manager.py` DEFAULT_CONFIG line 24; `adaptive/config/adaptive_engine.yaml` line 12) |
| Adapter hardcoded value | 0.25% (`strategies/adapters/london_breakout_adapter.py` line 60, `risk_percent=0.25`) |
| File | Three locations |
| Enforced? | PARTIAL — lot size calculation at `execution/demo_risk_manager.py:calculate_lots()` uses `sl_pips` and `balance`; which `risk_percent` governs actual sizing is not confirmed without reading `demo_risk_manager.py`. The `Signal.risk_percent` field (set to 0.25 by adapter) is the value passed downstream, but it may or may not be used by the lot calculator. |
| Notes | Three separate values exist across three files with no single source of truth. The portfolio YAML (0.20%) and the hardcoded adapter value (0.25%) are inconsistent. This is a HIGH finding. |

---

### max_daily_loss

| Attribute | Value |
|-----------|-------|
| Exists? | YES — multiple layers |
| Adaptive engine (risk_manager) | 1.5% of account (`adaptive/engine/risk_manager.py` line 27; `adaptive/config/adaptive_engine.yaml` line 13) |
| Portfolio runner | 2.0% daily (`config/strategy_portfolio.yaml` line 9) |
| File | risk_manager.py:27, adaptive_engine.yaml:13, strategy_portfolio.yaml:9 |
| Enforced? | YES — `risk_manager.check_risk()` checks `daily_loss_pct < 0.015`; halts state when breached (`record_trade()` sets `halted=True`). PortfolioManager enforces portfolio-level 2.0% via `any_loss_limit_hit()`. |
| Notes | Two separate daily loss limits: 1.5% in adaptive engine path, 2.0% in portfolio path. These are independent checks in different code paths. Both are active for their respective runners. |

---

### max_drawdown

| Attribute | Value |
|-----------|-------|
| Exists? | NOT FOUND in adaptive engine or London Breakout-specific code |
| Portfolio level | PARTIAL — portfolio has weekly (5.0%) and monthly (8.0%) loss limits (`strategy_portfolio.yaml` lines 10-11) |
| Account-level drawdown | NOT FOUND — no peak-equity tracking or max_drawdown kill switch identified in the read files |
| File | strategy_portfolio.yaml lines 10-11 |
| Enforced? | PARTIAL — weekly/monthly loss caps exist in PortfolioManager but no drawdown-from-peak guard was found |
| Notes | CLAUDE.md §4 specifies a 10% max drawdown kill switch for the Strategy 2 bot, but no implementation of this was found in the adaptive engine or portfolio runner code. This is a CRITICAL gap if this strategy operates as an execution layer for Strategy 2. |

---

### max_positions

| Attribute | Value |
|-----------|-------|
| Exists? | YES |
| Portfolio level | 3 total open positions (`config/strategy_portfolio.yaml` line 8) |
| Adaptive engine level | Enforced via open_positions list in risk state; no explicit cap found in `adaptive/engine/risk_manager.py` — correlation guard limits same-direction pairs |
| File | strategy_portfolio.yaml:8 |
| Enforced? | YES — PortfolioManager.evaluate() enforces `max_open_positions=3` in portfolio runner path |
| Notes | Only the portfolio runner enforces a hard position cap. The adaptive shadow runner relies on risk_manager correlation logic only. |

---

### kill_switch

| Attribute | Value |
|-----------|-------|
| Exists? | YES — multiple layers |
| DRY_RUN default | True — prevents any real orders (`adaptive/execution/demo_executor.py` line 23; `adaptive/engine/trade_router.py` line 82) |
| Live mode block | Hard `sys.exit(1)` if mode=live (`scripts/run_portfolio.py` lines 387-393) |
| Daily halt | risk_manager sets `state["halted"]=True` after daily loss or consecutive loss limit (`adaptive/engine/risk_manager.py` lines 155-161) |
| Intra-day halt check | `check_risk()` returns rejected if `state["halted"]==True` (risk_manager.py line 86) |
| NotImplementedError | Live execution path in demo_executor.py raises `NotImplementedError` if `dry_run=False` |
| File | demo_executor.py:59-61, trade_router.py:82, run_portfolio.py:387-393, risk_manager.py:155-161 |
| Enforced? | YES — defense in depth: DRY_RUN env var, mode guard, daily halt, NotImplementedError |
| Notes | The consecutive-loss halt in the adaptive risk manager resets on daily reset (`reset_daily()` clears `halted=False`). The CircuitBreaker has its own cooldown (4h by default) that is per-strategy and shorter-lived. These are separate mechanisms. |

---

### spread_protection

| Attribute | Value |
|-----------|-------|
| Exists? | YES — multiple layers |
| Portfolio runner (pre-fetch) | EURUSD:1.5, GBPUSD:2.0, USDJPY:1.5 pips (`run_portfolio.py` line 125) — symbols with spread above threshold are skipped before any signal generation |
| Signal scorer | EURUSD:1.5, GBPUSD:2.0, USDJPY:2.0 pips (`signal_scorer.py` lines 19-21) — spread check awards/denies 1 scoring point |
| Regime detector | 3.0 pips → UNSAFE regime (`regime_detector.py` line 22) — blocks all signals via REGIME_BLOCKED |
| File | run_portfolio.py:125, signal_scorer.py:19-21, regime_detector.py:22 |
| Enforced? | YES — two hard blocks (portfolio runner skip, UNSAFE regime) and one soft penalty (scorer -1 point) |
| Notes | USDJPY spread limit is inconsistent: 1.5 in portfolio runner vs 2.0 in signal scorer. A USDJPY signal with spread 1.6 pips is blocked at portfolio runner but would pass the scorer check. The portfolio runner check runs first, so the net effect is the stricter 1.5 pips applies for USDJPY in the portfolio path. |

---

## Additional Risk Controls

### max_consecutive_losses

| Attribute | Value |
|-----------|-------|
| Exists? | YES — two layers |
| Adaptive engine | 3 consecutive losses → halt (`risk_manager.py` DEFAULT_CONFIG line 29) |
| CircuitBreaker | 4 consecutive losses → 4-hour cooldown (`circuit_breaker.py` defaults line 29-30) |
| File | risk_manager.py:29, circuit_breaker.py:27-31 |
| Enforced? | YES — both layers are active in their respective paths |
| Notes | CircuitBreaker is initialized without config in portfolio runner (`CircuitBreaker()` at run_portfolio.py:72), so it uses defaults (4 losses, 4h cooldown), not the 3-loss limit from the adaptive risk manager. |

---

### max_trades_per_day

| Attribute | Value |
|-----------|-------|
| Exists? | YES |
| Adaptive engine | 6 per day (`risk_manager.py` DEFAULT_CONFIG line 28; `adaptive_engine.yaml` line 14) |
| Portfolio config | 6 per day (`strategy_portfolio.yaml` line 7) |
| CircuitBreaker default | 4 per day (`circuit_breaker.py` default line 29) |
| File | risk_manager.py:28, adaptive_engine.yaml:14, strategy_portfolio.yaml:7, circuit_breaker.py:29 |
| Enforced? | YES |
| Notes | Three different numbers: 6 (risk_manager/yaml), 6 (portfolio yaml), 4 (circuit breaker default). For LondonBreakout, the circuit breaker uses defaults (4/day) since no strategy-specific config is loaded. |

---

### correlation_guard

| Attribute | Value |
|-----------|-------|
| Exists? | PARTIAL |
| Adaptive engine | Blocks LONG EURUSD + LONG GBPUSD simultaneously (`risk_manager.py` lines 51-62). SHORT+SHORT correlation is NOT blocked (`_SAME_DIRECTION_BLOCKED = {"LONG"}` at line 35). |
| Portfolio config | Full correlation groups: [EURUSD, GBPUSD, EURGBP], [GBPUSD, GBPJPY, EURGBP], [USDJPY, EURJPY, GBPJPY] (`strategy_portfolio.yaml` lines 13-16) |
| File | risk_manager.py:35,51-62, strategy_portfolio.yaml:13-16 |
| Enforced? | PARTIAL — LONG correlation enforced in adaptive path; full group correlation enforced by PortfolioManager in portfolio path |
| Notes | The adaptive engine's correlation guard has an asymmetry bug: SHORT+SHORT pairs are not blocked. Since EURUSD and GBPUSD are strongly correlated in both directions, this is a risk gap in the adaptive shadow runner path. |

---

### news_filter

| Attribute | Value |
|-----------|-------|
| Exists? | STUB ONLY |
| Implementation | Always returns `safe_to_trade=True` with `source="stub"` (`adaptive/filters/news_filter.py` line 44) |
| File | adaptive/filters/news_filter.py:44 |
| Enforced? | NO — stub never blocks trading |
| Notes | CRITICAL gap: London open (06:00–09:00 UTC) coincides with high-impact UK and EUR news events (e.g., CPI, PMI, BOE announcements). The strategy has no protection against trading through major news releases. Score check awards 1 point for "news_clear=True" which is always True. |

---

### weekly / monthly loss limits

| Attribute | Value |
|-----------|-------|
| Exists? | YES (portfolio path only) |
| Weekly | 5.0% (`strategy_portfolio.yaml` line 10) |
| Monthly | 8.0% (`strategy_portfolio.yaml` line 11) |
| File | strategy_portfolio.yaml:10-11 |
| Enforced? | YES — via PortfolioManager.any_loss_limit_hit() in portfolio runner |
| Notes | Not present in adaptive shadow runner path. |

---

## Risk Control Summary Matrix

| Control | Exists? | Value | Adaptive Path | Portfolio Path | Notes |
|---------|---------|-------|---------------|----------------|-------|
| risk_per_trade | PARTIAL | 0.25% (adapter) / 0.20% (yaml) / 0.50% (adaptive) | 0.50% | 0.20% | THREE conflicting values |
| max_daily_loss | YES | 1.5% (adaptive) / 2.0% (portfolio) | 1.5% | 2.0% | Two separate limits |
| max_drawdown | NO | N/A | Not implemented | Not implemented | CRITICAL gap |
| max_positions | PARTIAL | 3 (portfolio) | Correlation only | 3 | Portfolio path only |
| kill_switch | YES | DRY_RUN=true default | YES | YES | Defense in depth |
| spread_protection | YES | 1.5-2.0 pips | Via scorer/regime | Via runner skip | USDJPY inconsistency |
| max_consecutive_losses | YES | 3 (adaptive) / 4 (CB) | 3 losses → halt | 4 losses → cooldown | Different thresholds |
| max_trades_per_day | YES | 6 (adaptive/yaml) / 4 (CB default) | 6 | 4 (CB default) | Different thresholds |
| correlation_guard | PARTIAL | LONG pairs only (adaptive) | LONG only | Full groups | SHORT gap in adaptive |
| news_filter | NO | Stub | Never blocks | Never blocks | CRITICAL stub |
| weekly_loss_limit | PARTIAL | 5.0% | Not implemented | YES | Portfolio path only |
| monthly_loss_limit | PARTIAL | 8.0% | Not implemented | YES | Portfolio path only |
