# Risk Controls: NY Momentum

For each control: Exists? (YES/NO/PARTIAL) | Value | File | Enforced? | Notes

---

## Per-Trade Risk Controls

### risk_per_trade

| Attribute | Detail |
|---|---|
| Exists? | PARTIAL |
| Value (adapter) | `0.25` (hardcoded in `Signal.risk_percent`) |
| Value (engine config) | `0.005` (0.5% in `adaptive_engine.yaml` and `risk_manager.DEFAULT_CONFIG`) |
| File (adapter) | `strategies/adapters/ny_momentum_adapter.py` : line 61 |
| File (config) | `adaptive/config/adaptive_engine.yaml` : line 13 |
| File (risk_manager) | `adaptive/engine/risk_manager.py` : line 24 |
| Enforced? | NO — the `risk_percent` field on `Signal` is set to 0.25 but is never read by any downstream execution layer to compute lot size in the current codebase. The adaptive engine risk_manager does not use `risk_percent` to size positions; it only checks counts and daily loss. Paper execution does not compute lot sizes at all. |
| Notes | Three different risk-per-trade values exist: 0.25% (adapter), 0.5% (config/risk_manager default). The paper/demo execution layer ignores all of them. In the `PortfolioManager` tier system, NYMomentum is `tier2` with `RISK_TIERS["tier2"] = 0.20` (20%); this appears to be a fraction of account, not a percentage, and is extremely large — likely intended as 0.20% but coded as a direct multiplier. This value is returned by `get_risk_pct()` but nothing calls that method in the shadow runner. |

---

### stop_loss

| Attribute | Detail |
|---|---|
| Exists? | YES |
| Value | LONG: `london_low - 1 pip`; SHORT: `london_high + 1 pip` |
| File | `adaptive/strategies/ny_momentum_strategy.py` : lines 119, 147 |
| Enforced? | YES — SL price is set in the signal and used by `PaperExecution.update()` to trigger a simulated close |
| Notes | SL is always the opposite London extreme. For a 50-pip London range, SL is ~50 pips from entry. This is a full-range stop and may be disproportionately large. There is no maximum SL size check. SL geometry is validated by `SignalRouter` (BUY: sl < entry; SELL: sl > entry) but not by the adaptive engine's `trade_router`. |

---

### take_profit

| Attribute | Detail |
|---|---|
| Exists? | YES |
| Value | 2R (`TP_RR = 2.0`); TP = entry ± risk × 2.0 |
| File | `adaptive/strategies/ny_momentum_strategy.py` : lines 36, 122, 150 |
| Enforced? | YES — TP price is set in signal and used by `PaperExecution.update()` |
| Notes | Fixed 2R only. No partial close, no trailing stop, no breakeven move. Once in a trade, outcome is binary: full 2R win or full 1R loss. |

---

## Session / Time Controls

### session_close_rule

| Attribute | Detail |
|---|---|
| Exists? | NO |
| Value | N/A |
| File | N/A |
| Enforced? | NO — `PaperExecution.close_all()` exists but is never called from `run_shadow.py`. Open trades are never force-closed at NY session end (15:00 UTC). |
| Notes | This is a gap: a trade opened at 14:45 could remain open and be updated by M15 candles from the Asian or London session of the next day. |

---

## Daily Loss Controls

### max_daily_loss

| Attribute | Detail |
|---|---|
| Exists? | PARTIAL |
| Value | 1.5% of account (config + risk_manager default) |
| File | `adaptive/config/adaptive_engine.yaml` : line 14; `adaptive/engine/risk_manager.py` : line 25 |
| Enforced? | PARTIAL — `check_risk()` checks `state["daily_loss_pct"] < 0.015` and rejects signals if exceeded. However, `record_trade()` in risk_manager is never called from `run_shadow.py`, so `state["daily_loss_pct"]` is never updated from trade P&L. The check exists but the counter feeding it is always 0. |
| Notes | The PortfolioManager has a separate `daily_loss_limit_pct = 2.0%` but PortfolioManager is also not used in the shadow runner. Two independent daily loss limits exist in the codebase that are never reconciled. |

---

### max_drawdown

| Attribute | Detail |
|---|---|
| Exists? | NO |
| Value | N/A — no drawdown-from-peak tracking |
| File | N/A |
| Enforced? | NO |
| Notes | The project's `CLAUDE.md §4` specifies `max_drawdown: 10%` as a kill switch from peak, but no code in the adaptive engine or shadow runner tracks peak equity or enforces a drawdown limit. The `PortfolioManager` tracks monthly P&L (8% limit) but not drawdown from peak. |

---

## Position Controls

### max_positions

| Attribute | Detail |
|---|---|
| Exists? | PARTIAL |
| Value | Enforced indirectly via correlation guard (blocks LONG on EURUSD + GBPUSD simultaneously) |
| File | `adaptive/engine/risk_manager.py` : lines 50–62 |
| Enforced? | PARTIAL — The correlation guard exists and is checked. However: (1) it only blocks LONG/LONG, not SHORT/SHORT (`_SAME_DIRECTION_BLOCKED = {"LONG"}`); (2) it requires explicit `register_open_position()` calls to populate `state["open_positions"]`, which are made in `run_shadow.py` after approval (line 206). |
| Notes | There is no explicit `max_open_positions` cap in the adaptive engine. The `PortfolioManager._DEFAULT_CONFIG["portfolio"]["max_open_positions"] = 3` exists but `PortfolioManager` is not used in the shadow runner. |

---

### max_trades_per_day

| Attribute | Detail |
|---|---|
| Exists? | YES |
| Value | 6 per day (config + risk_manager default) |
| File | `adaptive/config/adaptive_engine.yaml` : line 15; `adaptive/engine/risk_manager.py` : line 26 |
| Enforced? | PARTIAL — `check_risk()` checks `state["trades_today"] < 6`. However `record_trade()` is never called from `run_shadow.py`, so `state["trades_today"]` is never incremented from actual trade completions. It remains 0 permanently. Effectively not enforced. |
| Notes | N/A |

---

## Consecutive Loss Controls

### max_consecutive_losses

| Attribute | Detail |
|---|---|
| Exists? | YES |
| Value | 3 (config + risk_manager default) |
| File | `adaptive/config/adaptive_engine.yaml` : line 16; `adaptive/engine/risk_manager.py` : line 27 |
| Enforced? | PARTIAL — Check exists in `check_risk()`. Same problem: `record_trade()` is never called, so `state["consecutive_losses"]` is always 0. The check exists but the counter is never incremented. |
| Notes | N/A |

---

## Kill Switch

### kill_switch / DRY_RUN

| Attribute | Detail |
|---|---|
| Exists? | YES |
| Value | `DRY_RUN = True` by default (env var `DRY_RUN`; defaults to `"true"`) |
| File | `adaptive/execution/demo_executor.py` : line 23; `adaptive/engine/trade_router.py` : line 82 |
| Enforced? | YES — `route_signal()` never reaches live execution (line 126 returns `REJECTED "LIVE_TRADING_NOT_ENABLED"` when `dry_run=False`). `DemoExecutor.execute()` raises `NotImplementedError` when `dry_run=False`. The shadow runner hardcodes `dry_run=True` (line 201 of `run_shadow.py`). |
| Notes | Live execution requires: (a) `DRY_RUN=false` in environment AND (b) CONFIRM-LIVE-ON token per CLAUDE.md §6 — the CONFIRM token pathway is not yet wired into the code. |

---

## Spread Protection

### spread_protection

| Attribute | Detail |
|---|---|
| Exists? | PARTIAL |
| Value (hard block) | 3.0 pips → UNSAFE regime, blocks all signals |
| Value (scoring) | EURUSD 1.5 pips, GBPUSD/USDJPY 2.0 pips → loses 1 scoring point |
| File (hard block) | `adaptive/engine/regime_detector.py` : line 22 |
| File (scoring) | `adaptive/engine/signal_scorer.py` : lines 18–22 |
| Enforced? | PARTIAL — Spread-based regime block is enforced. Spread scoring is enforced. However, spread is only a soft filter in scoring (costs 1 point; signal can still reach score 7 without it if other criteria pass). The 3.0-pip hard block catches only extreme spreads. |
| Notes | Spread data comes from `feed.get_current_spread(symbol)` → `ForexData.get_current_price()["spread_pips"]`. If the broker API returns 0.0 (default fallback), the spread filter never fires. |

---

## Circuit Breaker

### circuit_breaker

| Attribute | Detail |
|---|---|
| Exists? | YES (code) — PARTIAL (wiring) |
| Value | Defaults: max 6 signals/hr, max 4 trades/day, max 4 consecutive losses → 4h cooldown |
| File | `core/circuit_breaker.py` : lines 26–31 |
| Enforced? | NO — `CircuitBreaker` is defined and has per-strategy config support, but it is not instantiated or called anywhere in `run_shadow.py` or `adaptive/engine/trade_router.py`. It is dead code relative to the NY Momentum execution path. |
| Notes | No NY Momentum-specific circuit breaker configuration exists in any YAML file. |

---

## Summary Table

| Control | Exists? | Enforced in shadow runner? |
|---|---|---|
| risk_per_trade | PARTIAL | NO (field set but not used for sizing) |
| stop_loss | YES | YES (paper execution) |
| take_profit (2R) | YES | YES (paper execution) |
| session close rule | NO | NO |
| max_daily_loss | PARTIAL | NO (counter never updated) |
| max_drawdown | NO | NO |
| max_positions | PARTIAL | PARTIAL (correlation guard, LONG only) |
| max_trades_per_day | YES | NO (counter never updated) |
| max_consecutive_losses | YES | NO (counter never updated) |
| kill_switch (DRY_RUN) | YES | YES |
| spread_protection (hard) | YES | YES (3-pip UNSAFE block) |
| spread_protection (soft) | YES | YES (scoring -1 point) |
| circuit_breaker | YES (code) | NO (not wired) |
| Phase-0 gate | Defined in CLAUDE.md | Not enforced by code |
