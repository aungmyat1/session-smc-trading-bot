# Strategy Spec: SMC Session Liquidity-Sweep (SMC-LSS)

**Status:** Draft for code-agent implementation — not yet gate-validated, not yet added to `strategy_portfolio.yaml` runtime.
**Class name suggestion:** `SMCLiquiditySweepAdapter`
**Instruments:** EURUSD, GBPUSD, XAUUSD (same as existing adapters)
**Timeframes required:** 1D, 1H, 5M
**Constraints inherited from `CLAUDE.md`:** no self-execution of live trades, no mid-trial parameter tuning, net-of-fees measurement only, one position per symbol.

---

## 1. Concept Summary

Three-phase top-down model:

1. **Phase A — Trade Idea Generation** (runs once per session/day): establish HTF directional bias and mark liquidity/POI. This is *context*, not a signal.
2. **Phase E — Conditional Trigger** (runs continuously intra-session): three independent "if" branches that watch for price interacting with the Phase-A context. Any one firing hands off to the 5M chart.
3. **Phase M — Execution Model** (runs on 5M once a branch fires): confirms a lower-timeframe structural event, then defines Entry / SL / TP.

This maps cleanly onto a state machine per symbol per session:

```
IDLE -> BIAS_SET -> POI_ARMED -> TRIGGER_WATCH -> M_CONFIRMED -> IN_TRADE -> IDLE
```

---

## 2. Phase A — Trade Idea Generation (daily prep, 1D/1H)

Run once at session start (e.g. at NY midnight rollover) per symbol.

| Step | Input TF | Logic | Output |
|------|----------|-------|--------|
| **A1 — Compass points** | 1D | Identify last significant HTF swing high/low (external liquidity) and last daily gap. This defines the reference frame; intraday order flow is not weighted here. | `htf_bias_ref = {ext_high, ext_low, last_gap}` |
| **A2 — Next target / directional bias** | 1D | If price is trading away from `ext_high`/`ext_low` toward the opposite side, bias = trend continuation. Counter-trend bias is only valid if there is an explicit HTF reason (e.g. confirmed reversal structure) — do not counter-trend by default. | `bias ∈ {bullish, bearish}`, `next_target` |
| **A3 — Liquidity levels** | 1H | Mark: Daily High (PDH), Daily Low (PDL), NY midnight open (NYMN), daily gap boundaries. Must be drawn/refreshed before every session. | `liquidity_levels = {PDH, PDL, NYMN, gap_hi, gap_lo}` |
| **A4 — Optimal POI** | 1H | Candidate POI = an order block / gap that satisfies **both**: (a) aligned with a liquidity zone from A3, and (b) has price-action confirmation (rejection wick, displacement). A gap alone without liquidity-zone confluence is **not** a valid POI — reject it. | `poi = {zone_hi, zone_lo, type}` |
| **A5 — Spread-adjusted alert** | — | Buy setup: alert at `poi.price - spread`. Sell setup: alert at `poi.price + spread`. Spread must be pulled from a live/rolling average-spread reference per instrument, not a fixed constant. | `alert_price` |

**Config shape (extends `strategy_portfolio.yaml` schema):**
```yaml
smc_lss:
  enabled: false          # hard-blocked until gate-validated
  timeframes: ["1D", "1H", "5M"]
  session_anchor: "NY_MIDNIGHT"
  liquidity_refresh: "per_session"
  poi_requires_liquidity_confluence: true   # enforce A4 rule strictly
  spread_source: "rolling_avg_spread"       # see Average-Spread reference in section 5
```

---

## 3. Phase E — Conditional Trigger (intraday, watches 1D/1H context against live price)

Three mutually independent branches. Any can fire; each routes to its own Phase-M model on 5M. Treat as `OR` of three watchers, not sequential.

| Branch | IF condition (on 1H/1D context) | THEN |
|--------|----------------------------------|------|
| **E1** | Price fills the 1D daily gap and reacts (rejects) at/near it | Go to 5M → **M1** |
| **E2** | Price reacts at the 1H POI (from A4) | Go to 5M → **M2** |
| **E3** | Price sweeps a marked liquidity level (PDH/PDL/1H external liquidity) | Go to 5M → **M3** |

Each branch should be implemented as its own watcher/callback so they can fire independently and be independently disabled for testing (useful for your walk-forward/robustness harness).

---

## 4. Phase M — Execution Models (5M confirmation + Entry/SL/TP)

### M1 — Character Change with Inducement (fires after E1)
- **Confirm:** a Change of Character (CHoCH) on 5M, with an inducement (liquidity grab) preceding it — i.e. don't act on the first CHoCH, wait for the induced one.
- **Entry:** from the last pullback or the last gap following the CHoCH.
- **SL:** placed beyond that same pullback/gap.
- **TP1:** 3R. **TP2:** nearest 1H external liquidity. **TP3:** next swing point.

### M2 — Supply/Demand Shift (fires after E2)
- **Confirm:** a shift from demand to supply (or vice versa) on 5M — i.e. the order-flow structure that broke through the POI, not just a touch.
- **Entry:** plot to the last order-flow leg; enter from the current gap/OB formed by that shift.
- **SL:** beyond that current gap/OB.
- **TP1/TP2/TP3:** same as M1 (3R / 1H external liquidity / swing point).

### M3 — Sweep & Drop/Pump (fires after E3)
- **Confirm:** liquidity sweep followed by a decisive drop/pump (displacement away from the sweep).
- **Entry:** wait for a 50% retracement of the impulse leg; enter at 50% of the *inverted* gap created by the sweep.
- **Risk:** explicitly reduced size on this path (the spec calls this out — treat M3 as higher-risk/lower-confidence than M1/M2 and size accordingly, e.g. 0.5x normal risk unit).
- **SL:** from the 50%-entry level, with reduced risk.
- **TP1/TP2/TP3:** same scheme.

**Common TP framework across all three models:**
```
TP1 = entry ± 3R
TP2 = nearest 1H external liquidity level
TP3 = next HTF swing point
```

---

## 5. Spread / "Breathing Room" Rules

- Every entry, SL, and alert level must be spread-adjusted:
  - Buy setups: `entry = level - spread`, protective levels shifted accordingly.
  - Sell setups: `entry = level + spread`.
- Maintain a rolling average-spread reference per instrument (the source material references a maintained `Average-Spread` reference table — implement as a small rolling-average service reading live bid/ask from MetaAPI, refreshed periodically, not a static config value).
- Distinguish **Tentative levels (T-)** computed from analysis vs **Actual levels (A-)** used for real order placement — i.e. compute raw technical levels first, then derive the spread-adjusted actual levels as a separate step. This separation is worth preserving in code (two explicit fields per level: `t_price` and `a_price`) so backtests can audit whether spread adjustment changed outcomes.

---

## 6. Suggested Implementation Shape

```
class SMCLiquiditySweepAdapter(StrategyAdapter):
    def on_session_start(self, symbol):
        # Phase A: A1-A5
        self.bias = self._compute_bias_1d(symbol)          # A1, A2
        self.liquidity = self._mark_liquidity_1h(symbol)    # A3
        self.poi = self._find_poi_1h(symbol, self.liquidity)# A4 (must satisfy confluence)
        self.alert_price = self._spread_adjusted_alert(self.poi)  # A5

    def on_new_bar_1h(self, symbol, bar):
        # Phase E watchers — independent, any may fire
        if self._e1_gap_fill_react(symbol, bar):
            self.armed_model = "M1"
        elif self._e2_poi_react(symbol, bar):
            self.armed_model = "M2"
        elif self._e3_liquidity_sweep(symbol, bar):
            self.armed_model = "M3"

    def on_new_bar_5m(self, symbol, bar):
        if self.armed_model == "M1":
            self._run_m1_choch_inducement(symbol, bar)
        elif self.armed_model == "M2":
            self._run_m2_supply_demand_shift(symbol, bar)
        elif self.armed_model == "M3":
            self._run_m3_sweep_drop_pump(symbol, bar)

    def _emit_signal(self, entry, sl, tp1, tp2, tp3, risk_multiplier=1.0):
        # route through existing SignalRouter / PortfolioManager
        # respects: one position per symbol, net-of-fees sizing,
        # no self-execution — signal only, execution stays gated by SVOS
        ...
```

Integration notes:
- Route emitted signals through `PortfolioManager`/`SignalRouter` exactly like `AdaptiveSMCAdapter` — do not add a parallel execution path (you already flagged three duplicated risk-logic stacks; don't create a fourth).
- This strategy should go through the same ST-A2-style end-to-end demo/shadow validation before being wired live, given the pipeline has never been demonstrated end-to-end outside ST-A2.
- Add `poi_requires_liquidity_confluence` and `m3_risk_multiplier` as explicit gate-checked config fields, not hardcoded constants, so the robustness harness can vary them.
- Log which branch (E1/E2/E3) and which model (M1/M2/M3) produced each signal — you'll want this broken out in the backtest export (Markdown/CSV pipeline) to see which of the three paths is actually carrying edge.

---

## 7. Open Items Before This Touches Live/Demo

- [ ] Formal definition of "inducement" and "CHoCH" for M1 (needs precise, testable rules, not just visual pattern-matching)
- [ ] Formal definition of "supply/demand shift" for M2
- [ ] Confirm 3R / 1H-external-liquidity / swing-point TP hierarchy against your existing per-strategy gate thresholds
- [ ] Wire `m3_risk_multiplier` into existing risk-per-strategy config alongside the other five strategies
- [ ] Backtest each of E1/E2/E3 branches independently before combining, to see which contribute positive expectancy
