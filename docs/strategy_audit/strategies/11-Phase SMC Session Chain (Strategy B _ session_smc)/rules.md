# Rules — 11-Phase SMC Session Chain (Strategy B / session_smc)

Rules listed in execution order as implemented in `generate_signal_A()`.

---

## Rule 0-A: Minimum Bar Count Guard

| Field | Value |
|---|---|
| Purpose | Prevent attempting signal detection when session window is too short |
| Inputs | `n = len(session_candles)`, `range_bars` (default 8) |
| Output | `return None` if `n < range_bars + 6` (i.e. n < 14 at defaults) |
| Code location | `confirmation_entry.py:generate_signal_A:117` |
| Failure modes | Too few M15 bars provided by caller. Rule fails silently (returns None). No logged error. |

---

## Rule 0-B: D2 Daily Context Build

| Field | Value |
|---|---|
| Purpose | Build previous-day H/L, midpoint, and daily swing structure from H4 bars |
| Inputs | `candles_4h`, `session_candles[0]["time"]` (session open time), `swing_n` |
| Output | `d2_ctx` dict with keys `pdh`, `pdl`, `daily_mid`, `structure`, or None |
| Code location | `confirmation_entry.py:generate_signal_A:123` → `daily_bias.py:build_daily_context:61` |
| Failure modes | Returns None if fewer than 2 closed daily bars exist (new data feed). When None, all D2 gates (A/B/C) are skipped. This is a silent bypass — no warning logged. |

---

## Rule 1: HTF Bias (4H + 1H Swing Structure)

| Field | Value |
|---|---|
| Purpose | Trade only when higher-timeframe trend is defined (avoid ranging markets) |
| Inputs | `candles_4h`, `candles_1h`, `swing_n=3` |
| Output | `bias` = 'bullish' | 'bearish' | 'neutral'. Returns None if neutral. |
| Code location | `confirmation_entry.py:generate_signal_A:126–128` → `structure_detector.py:htf_bias:17–37` → `swing_detector.py:classify_structure:93–127` |
| Failure modes | 1) Insufficient H4/H1 history (< 7 bars for swing_n=3) → `classify_structure` returns 'neutral' → `htf_bias` returns 'neutral' → signal fails. 2) Mixed structure (4H bullish + 1H bearish) → 'neutral' → fail. 3) If H1 bars not available, caller may pass M15 proxy — lower fidelity, may differ from true H1 structure. |

---

## Rule 2: D2 Gate A — Daily Structure Alignment

| Field | Value |
|---|---|
| Purpose | Block trades when daily structure directly contradicts 4H+1H bias |
| Inputs | `d2_ctx["structure"]` (daily swing), `bias` (4H+1H), `d2_structure_gate` config flag |
| Output | Returns None if daily structure is defined (not neutral) and opposes bias |
| Code location | `confirmation_entry.py:generate_signal_A:131–134` |
| Failure modes | 1) Gate defaults True but empirical results show it filters 50–100% of signals with degraded PF (VERDICT_LOG TRIAL_ST_A2_D1_001). 2) If `d2_ctx` is None (insufficient history), gate is silently skipped. |

---

## Rule 3: Session Range Build

| Field | Value |
|---|---|
| Purpose | Establish session H/L reference for sweep detection |
| Inputs | `session_candles`, `range_bars=8`, `min_range_pips=10.0` |
| Output | `sess_range` dict with `high`, `low`, `midpoint`, `range_pips`, or None |
| Code location | `confirmation_entry.py:generate_signal_A:149–151` → `liquidity_detector.py:build_session_range:19–50` |
| Failure modes | 1) Fewer than 8 session bars present → None. 2) Range < 10 pips (low-volatility session) → None. PIP hardcoded 0.0001 — incorrect for JPY pairs. |

---

## Rule 4: Session Classification (informational only)

| Field | Value |
|---|---|
| Purpose | Classify session as RANGE / TREND / MIXED for diagnostic purposes |
| Inputs | `session_candles`, `sess_range`, `atr_period=14` |
| Output | Classification string ('RANGE' | 'TREND' | 'MIXED') assigned to `_sess_class` but discarded |
| Code location | `confirmation_entry.py:generate_signal_A:155` → `liquidity_detector.py:classify_session:55–80` |
| Failure modes | No gate — result is silently discarded. Diagnostic value is lost. ATR is re-computed here separately from the ATR computed at line 158 — duplicate computation. |

---

## Rule 5: D2 Gate B — Price Location (Premium/Discount)

| Field | Value |
|---|---|
| Purpose | Ensure session opens in the zone that supports the trade direction |
| Inputs | `session_candles[0]["open"]` (session bar 0 open price), `d2_ctx["pdh"]`, `d2_ctx["pdl"]`, `d2_location_gate` flag |
| Output | Returns None if bullish trade but open is in premium (above PDH/PDL midpoint), or bearish trade but open is in discount |
| Code location | `confirmation_entry.py:generate_signal_A:140–146` → `daily_bias.py:classify_location:112–127` |
| Failure modes | 1) Uses `session_candles[0]["open"]` — the very first bar of the session, not the current bar. In a 20-bar session, this price may be many hours old relative to the sweep. 2) Gate defaults True but empirically removes 50% of signals without demonstrated PF improvement. |

---

## Rule 6: ATR Pre-computation

| Field | Value |
|---|---|
| Purpose | Pre-compute ATR(14) values on session bars for displacement detection |
| Inputs | `session_candles`, `atr_period=14` |
| Output | `atr_vals` list (floats, NaN for first `period` bars) |
| Code location | `confirmation_entry.py:generate_signal_A:158` → `structure_detector.py:atr:42–73` |
| Failure modes | ATR uses Wilder's method; seed at index `period` uses simple mean of TR[1..period]. Values at indices 0..period-1 are NaN and are skipped in displacement detection. Early-session sweeps (bars 8–13) may have NaN ATR, causing displacement detection to skip those bars. |

---

## Rule 7: Liquidity Sweep Detection

| Field | Value |
|---|---|
| Purpose | Detect session-level liquidity grab (stop hunt) aligned with trade bias |
| Inputs | `session_candles`, `sess_range`, `bias`, `from_idx=sweep_start_bar` (default 8) |
| Output | `sweep` dict with `index`, `sweep_price`, `wick_extreme`, `direction`, or None |
| Code location | `confirmation_entry.py:generate_signal_A:161–165` → `liquidity_detector.py:detect_sweep:85–128` |
| Failure modes | 1) No sweep occurs in session window → None. 2) Sweep found but bias-direction test prevents acceptance (already handled — detect_sweep only looks for sweeps aligned with bias parameter). 3) First sweep found wins — if multiple sweeps occur, later ones are ignored (returns earliest). |

---

## Rule 8: D2 Gate C — POI Proximity

| Field | Value |
|---|---|
| Purpose | Ensure swept session level is near a significant daily liquidity level (PDH/PDL) |
| Inputs | `sweep["sweep_price"]`, `d2_ctx["pdl"]` or `d2_ctx["pdh"]`, `d2_poi_pips=30.0` |
| Output | Returns None if abs(swept_level - PDL or PDH) > d2_poi_pips * PIP |
| Code location | `confirmation_entry.py:generate_signal_A:169–177` |
| Failure modes | 1) ST-D2-6M found 68.8% signal removal at 30 pip threshold — extremely restrictive. 2) VERDICT_LOG recommends raising to 50 pip for next trial. 3) Gate defaults True despite no validated evidence it improves PF. |

---

## Rule 9: CHoCH — Change of Character Detection

| Field | Value |
|---|---|
| Purpose | Confirm structural shift in 15M price action after the sweep |
| Inputs | `session_candles`, `sweep_idx`, `bias`, `choch_lookback=8` |
| Output | `choch` dict with `index`, `reference`, or None |
| Code location | `confirmation_entry.py:generate_signal_A:180–183` → `structure_detector.py:detect_choch:78–114` |
| Failure modes | 1) Reference level computed from up to 8 bars before sweep — if sweep is at bar 8, window is bars 0..7 (full range period). 2) If sweep occurs late in session, few bars remain for CHoCH to fire. 3) Window truncated to 0 bars if sweep_idx=0 (edge case: empty window → no reference → returns None). |

---

## Rule 10: BOS Level Derivation

| Field | Value |
|---|---|
| Purpose | Identify the prior structural level that must be broken to confirm momentum |
| Inputs | `session_candles`, `swing_n=3`, `before_idx=sweep_idx` |
| Output | `bos_swing` dict or None; `bos_level` float or None |
| Code location | `confirmation_entry.py:generate_signal_A:187–192` → `swing_detector.py:last_swing_high/last_swing_low:56–88` |
| Failure modes | 1) If sweep occurs at bar 8–10, there may be as few as 5–8 bars of session history; swing_n=3 requires 7 bars minimum (2n+1=7). If no confirmed swing exists, bos_level=None → BOS detection fails → signal fails. 2) BOS level uses session-only bars — no cross-session prior swings. Early sessions will often fail Phase 7. This is documented in ST_B_RESEARCH_PLAN.md §E.4. |

---

## Rule 11: BOS — Break of Structure Detection

| Field | Value |
|---|---|
| Purpose | Confirm structural break in trade direction after CHoCH |
| Inputs | `session_candles`, `choch_idx`, `bias`, `bos_level` (None → immediate fail) |
| Output | `bos` dict with `index`, `level`, or None |
| Code location | `confirmation_entry.py:generate_signal_A:194–197` → `structure_detector.py:detect_bos:119–149` |
| Failure modes | 1) bos_level is None (from Rule 10 failure) → returns None immediately. 2) BOS level is the prior swing, not a percentage or pip distance — if prior swing is very close to entry (consolidation), BOS fires quickly. If very far, BOS never fires within session window. 3) No guard against BOS firing on the same bar as CHoCH — theoretically possible. |

---

## Rule 12: Displacement Detection

| Field | Value |
|---|---|
| Purpose | Confirm an impulsive, momentum-driven move in the trade direction |
| Inputs | `session_candles`, `sweep_idx` (start), `bos_idx` (end), `bias`, `atr_vals`, `atr_mult=1.5` |
| Output | `disp` dict with `index`, `high`, `low`, `open`, `close`, or None |
| Code location | `confirmation_entry.py:generate_signal_A:200–205` → `structure_detector.py:detect_displacement:154–198` |
| Failure modes | 1) ATR is NaN for the first `atr_period` bars — these bars are skipped. If all bars in [sweep_idx, bos_idx] have NaN ATR, returns None. 2) Window [sweep_idx, bos_idx] may be 0–2 bars wide if CHoCH and BOS fire rapidly — small window reduces displacement candidates. 3) NaN check uses float identity (`atr_val != atr_val`) — correct but non-obvious. |

---

## Rule 13: Displacement Bar Boundary Check

| Field | Value |
|---|---|
| Purpose | Ensure FVG has a valid next bar to inspect |
| Inputs | `displacement_idx` (di), `n = len(session_candles)` |
| Output | Returns None if `di + 1 >= n` (displacement is the last bar) |
| Code location | `confirmation_entry.py:generate_signal_A:208–209` |
| Failure modes | Silent None return. Late-session displacements (last bar) are rejected. |

---

## Rule 14: FVG Detection

| Field | Value |
|---|---|
| Purpose | Find a price imbalance (3-bar gap) created by the displacement candle |
| Inputs | `session_candles`, `displacement_idx`, `bias` |
| Output | `fvg` dict with `top`, `bottom`, `midpoint`, `displacement_idx`, or None |
| Code location | `confirmation_entry.py:generate_signal_A:212–214` → `poi_detector.py:find_fvg:36–78` |
| Failure modes | 1) Requires `displacement_idx >= 1` (needs d-1 bar). If displacement fires at session bar 0, fails — but session bar 0 is the range window start, so displacement cannot fire before bar 8 in practice. 2) Wicks may overlap even when body is large — many displacement candles will not produce a true FVG (gap vs overlap). This is the primary driver of low trade count (ST_B_RESEARCH_PLAN.md §E.2). |

---

## Rule 15: FVG Retest Detection

| Field | Value |
|---|---|
| Purpose | Wait for price to pull back into the FVG zone and hold (entry confirmation) |
| Inputs | `session_candles`, `fvg`, `bias`, `from_idx=displacement_idx+2` |
| Output | `retest_idx` (int) or None |
| Code location | `confirmation_entry.py:generate_signal_A:218–220` → `poi_detector.py:check_fvg_retest:81–117` |
| Failure modes | 1) FVG invalidated if close exits opposite edge — returns None immediately on first invalidating bar. 2) No retest within session window → None. 3) Session time constraint is severe: if displacement fires at bar 15 of a 20-bar session, only 3 bars remain for retest — very low probability. This is the tightest gate (ST_B_RESEARCH_PLAN.md §E.3). 4) Retest detection checks `bar.low <= fvg.top` for bullish; price must enter the zone from above (pullback). If price never pulls back (strong continuation), returns None. |

---

## Rule 16: Phase 11 — Minimum Bars Remaining Gate

| Field | Value |
|---|---|
| Purpose | Reject entry signals too close to session end (insufficient trade time) |
| Inputs | `n`, `retest_idx`, `min_bars_remaining=2` |
| Output | Returns None if `n - 1 - retest_idx < min_bars_remaining` |
| Code location | `confirmation_entry.py:generate_signal_A:223–225` |
| Failure modes | Very tight gate (2 bars = 30 min at 15M). Late-session FVG retests are rejected. |

---

## Rule 17: Stop Loss Computation

| Field | Value |
|---|---|
| Purpose | Compute risk-controlled SL from two methods; use tighter (less risky) |
| Inputs | `entry`, `sess_range`, `wick_extreme`, `sl_buffer_pips=3.0`, `sl_range_pct=0.25` |
| Output | `sl` price, `sl_pips` distance |
| Code location | `confirmation_entry.py:generate_signal_A:228–253` |
| Failure modes | 1) Degenerate SL check: if `sl >= entry` (long) or `sl <= entry` (short) → return None. Can occur if wick_extreme is above entry (data quality issue). 2) Both SL candidates computed independently; tighter = closer to entry = smaller SL distance. 3) `sl_range_pct * range_size` may produce a very tight SL in narrow-range sessions (near Phase 3 minimum of 10 pip × 25% = 2.5 pip) — no min_sl_pips gate inside this rule. |

---

## Rule 18: TP Computation

| Field | Value |
|---|---|
| Purpose | Set profit targets from R-multiple of SL distance |
| Inputs | `entry`, `sl_pips`, `tp1_r=4.0`, `tp2_r=5.0` |
| Output | `tp1`, `tp2` price levels |
| Code location | `confirmation_entry.py:generate_signal_A:241–253` |
| Failure modes | Both TPs are computed from the same SL distance. No minimum TP distance check. TP1 and TP2 may be identical if tp1_r == tp2_r (not currently the case at defaults 4.0 / 5.0). |

---

## Rule 19: Signal Construction and Return

| Field | Value |
|---|---|
| Purpose | Package all computed fields into a Signal dataclass |
| Inputs | All previously computed fields |
| Output | `Signal` dataclass instance |
| Code location | `confirmation_entry.py:generate_signal_A:255–273` |
| Failure modes | Returns the signal for the EARLIEST valid sequence found (not the latest). Comment at line 108 says "most recent complete sequence" but the implementation returns the first one encountered (no re-scan for a later valid sequence). Potential minor inconsistency with the docstring. |
