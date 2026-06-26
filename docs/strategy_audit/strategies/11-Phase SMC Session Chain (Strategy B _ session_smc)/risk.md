# Risk Controls — 11-Phase SMC Session Chain (Strategy B / session_smc)

Audit of all risk controls. Two distinct scopes are covered:
1. **Signal-level controls** — implemented inside `session_smc/` modules.
2. **Account-level controls** — implemented in `execution/` modules and config files.
   These are NOT called by `session_smc/` and require an execution adapter to apply.

---

## Signal-Level Risk Controls (inside session_smc/)

### risk_per_trade

| Field | Value |
|---|---|
| Exists? | PARTIAL |
| Value | Not enforced in session_smc/. Specified as 1% in CLAUDE.md §4 and RISK_SPEC.md. |
| File | Specified: `RISK_SPEC.md`, `CLAUDE.md §4`. Implemented: `execution/risk_manager.py:118–127`, `execution/position_sizer.py:42–114`. |
| Enforced? | NO — `session_smc/` generates signals only (entry, sl, tp1, tp2). No lot sizing. |
| Notes | `Signal.sl_pips` is available for external lot sizing. Caller must apply `risk_per_trade` via `execution/position_sizer.py:calculate_lots()`. |

---

### Stop Loss Placement

| Field | Value |
|---|---|
| Exists? | YES |
| Value | Tighter of: (a) sweep wick extreme ± `sl_buffer_pips` (default 3.0 pip) or (b) entry ± 25% of session range |
| File | `confirmation_entry.py:228–253` |
| Enforced? | YES — degenerate SL (on wrong side of entry) triggers `return None` |
| Notes | No minimum SL pip distance enforced inside the module. See `min_sl_pips` below. |

---

### min_sl_pips

| Field | Value |
|---|---|
| Exists? | NO (absent from DEFAULT_CONFIG) |
| Value | ST-A2 uses 5.0 pip minimum (in strategy/session_liquidity/config.yaml and scripts). |
| File | ABSENT from `session_smc/confirmation_entry.py:DEFAULT_CONFIG`. Present in `strategy/session_liquidity/config.yaml:6`. |
| Enforced? | NO — signals with sl_pips < 5.0 will be emitted by the module. |
| Notes | ST_B_RESEARCH_PLAN.md §E.5 explicitly flags this as a known gap. The backtest runner should apply an external floor of 5.0 pip post-signal. Risk: at SL = 2.5 pip (minimum from 10-pip range at 25%), spread cost (~1.4 pip) is 56% of 1R — economically untenable. |

---

### max_sl_pips

| Field | Value |
|---|---|
| Exists? | NO (inside session_smc/) |
| Value | RISK_SPEC.md specifies 50 pip max; `execution/position_sizer.py:_MAX_SL_PIPS = 50.0`. |
| File | `execution/position_sizer.py:19` |
| Enforced? | NO — not checked inside `session_smc/` signal chain. |
| Notes | Wide SLs can result from large session ranges (e.g. 200-pip GBPUSD volatile day × 25% = 50 pip range SL). Session range minimum of 10 pip and sl_range_pct=0.25 could theoretically produce any SL width — no upper cap in the module. |

---

### Session End Close Rule

| Field | Value |
|---|---|
| Exists? | PARTIAL |
| Value | `min_bars_remaining >= 2` gate (Phase 11) prevents entries in the last 2 bars of session. |
| File | `confirmation_entry.py:223–225` |
| Enforced? | PARTIAL — prevents very late entry. Actual session-end market close of open positions must be implemented by execution layer. |
| Notes | SIGNAL_SPEC.md specifies "close remainder at session end." This logic is in `scripts/backtest.py:_simulate_trade()` (simulated) but not in any live execution adapter for this chain. |

---

### One Position Per Symbol

| Field | Value |
|---|---|
| Exists? | PARTIAL |
| Value | `generate_signal_A` returns at most ONE signal per call (first valid sequence found). |
| File | `confirmation_entry.py:108-109` (docstring), design of function |
| Enforced? | PARTIAL — function returns one signal, but multiple sessions per day (London + NY) could each produce one signal. Caller must enforce one-per-session-per-day rule. |
| Notes | Backtest enforces this by advancing `i += SESSION_BARS` after each signal. |

---

## Account-Level Risk Controls (execution/ layer — NOT connected to session_smc/)

These controls exist in `execution/risk_manager.py` and `execution/demo_risk_manager.py`.
They are not invoked by any code in `session_smc/` and require an execution adapter.

### max_daily_loss

| Field | Value |
|---|---|
| Exists? | YES (execution layer only) |
| Value | 3R per day (RISK_SPEC.md, CLAUDE.md §4). Configurable via `risk.max_daily_loss_r` in config. |
| File | `execution/risk_manager.py:67`, `RISK_SPEC.md`, `CLAUDE.md §4` |
| Enforced? | YES in execution layer. NOT enforced for session_smc/ standalone. |
| Notes | State persisted to `logs/bot_state.json`. Auto-resets at next UTC day. |

---

### max_drawdown (Kill Switch)

| Field | Value |
|---|---|
| Exists? | YES (execution layer only) |
| Value | 10% from peak equity (RISK_SPEC.md, CLAUDE.md §4). |
| File | `RISK_SPEC.md`, `CLAUDE.md §4`. Implementation: `execution/risk_manager.py` + `logs/kill_switch.json`. |
| Enforced? | YES in execution layer. NOT enforced in session_smc/. |
| Notes | Manual reset required: `KILL_SWITCH_OVERRIDE=true` in `.env`. |

---

### max_consecutive_losses

| Field | Value |
|---|---|
| Exists? | YES (execution layer only) |
| Value | 5 consecutive losses → halt until next trading day (RISK_SPEC.md). |
| File | `execution/risk_manager.py:69`, `RISK_SPEC.md` |
| Enforced? | YES in execution layer. NOT enforced in session_smc/. |
| Notes | Counter resets on first win or daily reset. |

---

### max_open_positions

| Field | Value |
|---|---|
| Exists? | YES (config level only) |
| Value | `max_open_positions: 3` in `config/demo.yaml:24`. `max_open_trades` in `execution/risk_manager.py`. |
| File | `config/demo.yaml:24`, `execution/risk_manager.py:66` |
| Enforced? | YES in execution layer via `can_open_position()`. NOT enforced in session_smc/. |
| Notes | Portfolio-level: 3 uncorrelated positions simultaneously. Per-pair: 1. |

---

### max_spread_pips

| Field | Value |
|---|---|
| Exists? | YES (config level only) |
| Value | EURUSD: 1.5 pip, GBPUSD: 2.0 pip (`config/demo.yaml:22–25`) |
| File | `config/demo.yaml:22–25` |
| Enforced? | NO — not checked inside session_smc/ signal chain. Enforcement requires execution adapter with live spread check. |
| Notes | session_smc/ has no spread awareness. |

---

### weekly_loss_limit

| Field | Value |
|---|---|
| Exists? | YES (execution layer only) |
| Value | 6R per week (RISK_SPEC.md). `config/demo.yaml` uses 5.0% weekly. |
| File | `execution/risk_manager.py:68`, `RISK_SPEC.md`, `config/demo.yaml:27` |
| Enforced? | YES in execution layer. NOT in session_smc/. |
| Notes | Minor inconsistency between RISK_SPEC.md (6R) and demo.yaml (5.0% — percentage-based). |

---

### max_trades_per_day

| Field | Value |
|---|---|
| Exists? | YES (config level only) |
| Value | 6 total per day (3 London + 3 NY) in `config/demo.yaml:20`. |
| File | `config/demo.yaml:20`, `config/strategy_portfolio.yaml:6` |
| Enforced? | NO — not in session_smc/. Enforced in `core/portfolio_manager.py` (execution layer). |
| Notes | For ST-B standalone operation, caller must track daily count. |

---

## Summary Table

| Control | Exists? | Value | File | Enforced in session_smc/? | Enforced in execution/? |
|---|---|---|---|---|---|
| risk_per_trade | PARTIAL | 1% account | RISK_SPEC.md / execution/ | NO | YES |
| SL placement | YES | wick±3pip OR 25% range (tighter) | confirmation_entry.py:228–253 | YES | N/A |
| min_sl_pips | NO | absent from DEFAULT_CONFIG | — | NO | YES (position_sizer.py) |
| max_sl_pips | NO | absent from session_smc | execution/position_sizer.py | NO | YES |
| max_daily_loss | YES | 3R | execution/risk_manager.py | NO | YES |
| max_drawdown | YES | 10% from peak | execution/risk_manager.py | NO | YES |
| max_consecutive_losses | YES | 5 | execution/risk_manager.py | NO | YES |
| max_open_positions | YES | 3 total / 1 per pair | config/demo.yaml | NO | YES |
| max_spread_pips | YES | 1.5/2.0 pip | config/demo.yaml | NO | NO (requires live spread check) |
| session_end_close | PARTIAL | Phase 11: min 2 bars remaining | confirmation_entry.py:223 | PARTIAL | NOT IMPLEMENTED for this chain |
| one_signal_per_session | PARTIAL | first valid sequence returned | confirmation_entry.py design | PARTIAL | Backtest only |
| weekly_loss_limit | YES | 6R | execution/risk_manager.py | NO | YES |
| max_trades_per_day | YES | 6 | config/demo.yaml | NO | YES (portfolio_manager) |
| kill_switch | YES | 10% DD, manual reset | execution/ + .env | NO | YES |

---

## Critical Risk Gap

The `session_smc/` module has NO execution adapter. The risk controls in `execution/`
are only applied if the signal is passed through an adapter (like `strategies/adapters/st_a2_adapter.py`
for ST-A2). For ST-B, no such adapter exists. Until one is written, all account-level
controls (daily loss, drawdown, position limits, spread check) are unenforced.
