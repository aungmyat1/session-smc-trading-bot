# Strategy: NY Momentum

## Version / Status

- **File:** `adaptive/strategies/ny_momentum_strategy.py`
- **Adapter:** `strategies/adapters/ny_momentum_adapter.py`
- **Config section:** `adaptive/config/adaptive_engine.yaml` → `ny_momentum:`
- **Engine version:** Adaptive Session Engine v1
- **Status:** UNVALIDATED — demo/shadow mode only. `LIVE_TRADING = False`. No Phase-0 backtest registered.
- **Validation tier:** `tier2` (conditionally validated per `core/portfolio_manager.py` — this label is aspirational; no backtest record exists in `docs/VERDICT_LOG.md` as of audit date)

---

## Description

NY Momentum captures New York session expansion off London session reference levels. The strategy identifies the high and low established during the London session (06:00–09:00 UTC), then watches during the New York session (11:00–15:00 UTC) for price to sweep beyond one of those levels with a confirming close. It then waits for price to retest the swept level and enters in the direction of the sweep.

The strategy produces `AdaptiveSignal` objects. It has no broker interaction; execution is handled by the adapter and downstream engine layers.

---

## Trading Philosophy

London session builds reference highs and lows representing liquidity resting above/below prior structure. The New York session frequently expands beyond London range to sweep that liquidity, then reverses or continues in the sweep direction. The strategy bets that a confirmed close beyond the London level — followed by a retest of that level — represents a genuine expansion move rather than a false spike. The entry on the retest reduces price risk relative to entering at the sweep extreme.

---

## Market / Timeframe / Session / Direction

| Attribute | Value |
|---|---|
| Instruments | EURUSD, GBPUSD, USDJPY (per config); XAUUSD pip size defined in adapter |
| Timeframe | M15 exclusively |
| Reference session | London: 06:00–09:00 UTC (inclusive hours) |
| Trade session | New York: 11:00–15:00 UTC (inclusive hours) |
| Direction | LONG (sweep of London High) or SHORT (sweep of London Low) |
| Order type | MARKET |

---

## Signal Chain (phase-by-phase, in execution order)

**Phase 1 — London Level Build**
Scan all M15 candles whose UTC hour falls within [6, 9] inclusive. Compute `london_high = max(high)` and `london_low = min(low)` across those bars. If no London bars are present, return empty (no signal possible).

**Phase 2 — NY Session Gate**
For each M15 candle, check whether the candle's UTC hour falls within [11, 15] inclusive. Candles outside this window are skipped entirely.

**Phase 3 — Sweep Detection (LONG)**
Condition: `high > london_high + 1 pip` AND `close > london_high`. Both must be true on the same candle. Once triggered, set `swept_long = True` and `awaiting_retest_long = True`. This flag is one-shot per session; once set it does not re-arm.

**Phase 4 — Sweep Detection (SHORT)**
Condition: `low < london_low - 1 pip` AND `close < london_low`. Both must be true on the same candle. One-shot per session.

**Phase 5 — Retest Detection (LONG)**
On subsequent candles (while `awaiting_retest_long`): retest zone is `[london_high - 1 pip, london_high + 2 pip]`. Condition: `low` or `close` falls within that zone. Entry triggers immediately on detection.

**Phase 6 — Retest Detection (SHORT)**
On subsequent candles (while `awaiting_retest_short`): retest zone is `[london_low - 2 pip, london_low + 1 pip]`. Condition: `high` or `close` falls within that zone. Entry triggers immediately on detection.

**Phase 7 — Signal Construction**
Compute entry, SL, TP (see Entry Rules and Exit Rules). Construct `AdaptiveSignal` and append to output list. Clear the awaiting-retest flag.

---

## Entry Rules

- **Entry price:** `close` of the retest candle (market entry at the current close price)
- **LONG entry condition:** low or close of retest candle is within `[london_high - 1 pip, london_high + 2 pip]`
- **SHORT entry condition:** high or close of retest candle is within `[london_low - 2 pip, london_low + 1 pip]`
- **Order type:** MARKET (set in adapter, `Signal.order_type = "MARKET"`)
- **Minimum candle requirement (adapter):** M15 input list must have at least 30 candles; otherwise adapter returns None

---

## Confirmation Rules

The following are required for a signal to be constructed (all AND-gated within the strategy):

1. London levels must be computable (at least one M15 bar in [06:00–09:00 UTC])
2. NY candle must be in session window [11:00–15:00 UTC]
3. Sweep must be confirmed by a close beyond the London level (not just a wick)
4. Sweep buffer of 1 pip must be exceeded (not just touching the level)
5. Risk must be positive (`risk > 0`) before the signal is appended

The adapter adds no additional confirmation logic beyond a minimum bar count (30).

The downstream engine adds further gates before routing:
- Regime filter: strategy must be in an allowed regime (TRENDING or BREAKOUT)
- Signal score >= 7 (out of 10): requires HTF bias alignment (+2), liquidity event (+2), structure confirmation (+2), active session (+1), spread acceptable (+1), volatility acceptable (+1), news clear (+1)
- Risk checks: not halted, daily loss < 1.5%, trades today < 6, consecutive losses < 3, no correlated position

Note: `metadata` always sets `liquidity_swept: True` and `structure_confirmed: True` unconditionally for every signal this strategy generates, guaranteeing 4 of the 10 scoring points without independent verification.

---

## Exit Rules (TP / SL / BE / Trailing / Partial)

**Stop Loss:**
- LONG: `sl = london_low - 1 pip` (1 pip below London Low)
- SHORT: `sl = london_high + 1 pip` (1 pip above London High)
- The SL uses the opposite London extreme, making it a full-range stop

**Take Profit:**
- TP = `entry + risk * 2.0` (LONG) / `entry - risk * 2.0` (SHORT)
- Fixed 2R target (`TP_RR = 2.0` in strategy; `tp_rr: 2.0` in config)
- No partial close, no breakeven move, no trailing stop
- Paper execution closes at TP price exactly when `price >= tp` (LONG) or `price <= tp` (SHORT)

**Breakeven / Partial / Trailing:** Not implemented. No such logic exists in the strategy, adapter, or paper execution layer.

**Session-end close:** The shadow runner's paper execution does not implement automatic session-end closure. `PaperExecution.close_all()` exists but is never called from `run_shadow.py`.

---

## Filters (Spread / Volatility / Session / News)

Filters are applied downstream in the engine, not inside the strategy itself.

| Filter | Where enforced | Value | Notes |
|---|---|---|---|
| Spread max (EURUSD) | `signal_scorer.py` + `adaptive_engine.yaml` | 1.5 pips | Contributes 1 scoring point |
| Spread max (GBPUSD) | `signal_scorer.py` + `adaptive_engine.yaml` | 2.0 pips | Contributes 1 scoring point |
| Spread max (USDJPY) | `signal_scorer.py` + `adaptive_engine.yaml` | 2.0 pips | Contributes 1 scoring point |
| Spread unsafe ceiling | `regime_detector.py` | 3.0 pips | Hard block → UNSAFE regime |
| ATR% max | `signal_scorer.py` + `adaptive_engine.yaml` | 0.8% of price | Contributes 1 scoring point |
| ATR% min | `signal_scorer.py` + `adaptive_engine.yaml` | 0.1% of price | Contributes 1 scoring point |
| Session window | `signal_scorer.py` | new_york: 11–15 UTC | Contributes 1 scoring point |
| News filter | `news_filter.py` | Stub — always passes | Live feed not wired; contributes 1 scoring point unconditionally |
| HTF bias | `signal_scorer.py` / `run_shadow.py` | H4 close vs 20-bar mean ±0.1% | Contributes 2 scoring points |
| Regime | `trade_router.py` | TRENDING or BREAKOUT only | Hard block for ny_momentum |
| Min score | `signal_scorer.py` + `adaptive_engine.yaml` | 7 / 10 | Hard gate |

---

## Kill Switch / Safety

| Control | Source | Value | Notes |
|---|---|---|---|
| DRY_RUN default | `demo_executor.py`, env var | True | All execution is simulated unless DRY_RUN=false |
| LIVE_TRADING gate | `CLAUDE.md §6` | Requires CONFIRM-LIVE-ON token | Owner-only; agent must never self-execute |
| Daily loss halt | `risk_manager.py` | 1.5% of account | Sets `halted=True`, blocks all further signals |
| Consecutive loss halt | `risk_manager.py` | 3 losses | Sets `halted=True` |
| Max trades per day | `risk_manager.py` + config | 6 | Hard cap |
| Correlated position block | `risk_manager.py` | EURUSD + GBPUSD LONG/LONG | Prevents simultaneous long on both |
| Regime block | `trade_router.py` | UNSAFE | Hard block regardless of score |
| UNSAFE on low data | `regime_detector.py` | < 29 candles (2*14+1) | Returns UNSAFE, blocks routing |
| Circuit breaker | `circuit_breaker.py` | max 6 signals/hr, 4 trades/day, 4 losses → 4h cooldown | Defaults; no NY Momentum-specific config found |

---

## Known Limitations

1. **No Phase-0 backtest completed.** The `tier2` label in `portfolio_manager.py` is not backed by a registered trial in `docs/VERDICT_LOG.md`.
2. **SL is always the full London range.** For a wide London range (e.g., 50 pips), the SL is proportionally large, which may make 2R targets unreachable within the NY session.
3. **No session-end forced closure.** Open paper trades are not closed at NY session end (15:00 UTC). `close_all()` is never called in `run_shadow.py`.
4. **No HTF bias filter inside the strategy.** HTF alignment is only scored (+2 points) downstream, not enforced as a hard gate within `generate_signals()`.
5. **`structure_confirmed` and `liquidity_swept` are always True.** These metadata flags are hardcoded on every emitted signal, inflating the signal score by 4 points unconditionally, regardless of actual structure.
6. **No break-even, partial close, or trailing stop.** The exit model is all-or-nothing at fixed SL or 2R TP.
7. **Retest zone is asymmetric.** LONG retest zone is `[lh-1pip, lh+2pip]`; SHORT retest zone is `[ll-2pip, ll+1pip]`. The asymmetry is unexplained.
8. **One-shot sweep flag per session.** Only the first sweep per session generates a trade opportunity. Subsequent sweeps of the same level are ignored.
9. **News filter is a stub.** `NewsFilter` always returns `safe_to_trade=True`. The 1 scoring point for news clearance is always awarded.
10. **XAUUSD pip size defined in adapter but not in strategy.** The strategy's `_PIP_SIZE` dict does not include XAUUSD; the adapter's `_PIP` dict does. If XAUUSD were passed to `generate_signals()`, it would use the fallback `0.0001` pip size (incorrect for gold).
11. **Signal timestamp uses candle time, not wall-clock.** The `AdaptiveSignal.timestamp` is the candle's own time field; the `Signal` created by the adapter uses `datetime.now(timezone.utc)` — these will differ when candles are replayed or delayed.

---

## Dependencies (modules, external)

**Internal modules:**
- `adaptive/strategies/__init__.py` — `AdaptiveSignal` dataclass
- `adaptive/engine/trade_router.py` — regime filter + score + risk pipeline
- `adaptive/engine/regime_detector.py` — ADX/ATR regime classification
- `adaptive/engine/signal_scorer.py` — 10-point scoring rubric
- `adaptive/engine/risk_manager.py` — daily/consecutive/correlation guards
- `adaptive/filters/news_filter.py` — news stub (always safe)
- `adaptive/simulation/paper_execution.py` — paper trade lifecycle
- `adaptive/journal/trade_journal.py` — JSONL signal/trade logging
- `adaptive/state/state_store.py` — persisted risk state (JSON file)
- `adaptive/data/market_feed.py` — candle fetch wrapper over ForexData
- `core/base_strategy.py` — `BaseStrategy` ABC
- `core/signal.py` — `Signal` dataclass (adapter output)
- `core/signal_router.py` — TTL/geometry/conflict validation
- `core/portfolio_manager.py` — multi-strategy coordination
- `core/circuit_breaker.py` — per-strategy rate limiting
- `data/forex_data.py` — MetaAPI candle fetcher (referenced by MarketFeed)
- `data/session_filter.py` — active session detector
- `execution/mt5_executor.py` — MetaAPI connection (shadow runner)

**External dependencies:**
- `metaapi-cloud-sdk` (>=29) — broker data and order execution
- `python-dotenv` — `.env` loading (optional, graceful fallback)
- Standard library only within the strategy itself (`datetime`, `__future__`)
