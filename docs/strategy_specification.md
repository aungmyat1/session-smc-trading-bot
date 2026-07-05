# Strategy Specification Guide

**Document:** How to write a qualifying SMC strategy specification
**Last updated:** 2026-06-30

---

## Purpose

A strategy specification is the input to the qualification pipeline. It must be precise enough that two independent engineers can implement identical code from it. Ambiguous specs fail Phase 0 automatically.

---

## Required Sections

Every strategy specification must include all of the following sections. Missing a section is an automatic FAIL at Phase 0 intake.

### 1. Market Structure

- **Trend bias timeframe:** Which HTF defines direction (e.g., H4)
- **Bias condition:** Specific structural condition (HH-HL = bullish, LH-LL = bearish)
- **BOS definition:** Confirmation candle, minimum displacement in pips, swing lookback rule
- **CHoCH definition:** Distinct from BOS; marks trend reversal context

### 2. Liquidity

- **Liquidity pool types:** Equal highs/lows, session highs/lows, swing points
- **Sweep definition:** Wick extension distance, close-back requirement, timeframe
- **EQH/EQL tolerance:** Maximum pip distance between qualifying levels
- **Session liquidity:** UTC boundaries for each session's high/low

### 3. Price Delivery

- **FVG definition:** 3-candle pattern, minimum gap size, mitigation rule (50% or full)
- **Order block definition:** Last opposing candle, boundary (high/low vs body), validity period
- **Premium/Discount:** Range reference (HTF swing), 50% threshold
- **Mitigation/Invalidation:** What constitutes a mitigated or invalidated POI

### 4. Entry Rules

- **Trigger:** The precise LTF condition that triggers an entry (e.g., M15 candle close above OB high)
- **Confirmation:** Optional secondary confirmation (BOS, CHoCH, FVG entry)
- **Confluence:** Required combination of conditions (at least 2 POIs from different categories)

### 5. Session Rules

- **Trading hours:** UTC windows for valid entry (kill zones)
- **Invalid hours:** Hours when no new entries are allowed
- **News filter:** ±30 min blackout around Tier-1 economic events (source required)
- **Day filter:** No new entries after 20:00 UTC Friday

### 6. Risk Management

See `docs/risk_management.md` for full details. Required:
- Risk percent per trade (% of current balance)
- SL placement rule (structural reference + buffer in pips)
- Minimum/maximum SL in pips
- TP targets (R-multiple or structural level)
- Daily loss limit in % or R
- Maximum concurrent positions per symbol

### 7. Exit Rules

- When to manually close before TP is hit
- Break-even rule (if any)
- Trailing stop conditions (if any)

---

## Specification Format

Specifications are stored in `config/strategy_catalog.yaml` under `strategies.{id}.specification`. The specification is a free-form text block, but each required section above must be addressed.

Example skeleton:

```yaml
strategies:
  ST-NEW:
    version: "1.0"
    status: draft
    approved: false
    current: false
    owner: quant
    description: "Short description"
    symbols: [EURUSD, GBPUSD]
    timeframes: [M15, H4]
    specification: |
      ## Market Structure
      H4 defines trend bias. Bullish = H4 prints HH-HL. BOS confirmed on M15 candle
      close above swing high by ≥5 pip margin. CHoCH = first bearish BOS after sweep.

      ## Liquidity
      ...
```

---

## Common Phase 0 Failure Modes

| Failure | Root Cause |
|---------|-----------|
| "Trade with the trend" | No HTF timeframe or structural condition defined |
| "Enter at OB" | OB boundaries, validity, and mitigation not defined |
| No session hours | Kill zones not specified in UTC |
| "Risk 1%" | Position size formula missing; lot calculation undefined |
| No daily loss limit | Hard gates require explicit limit |
| BOS = CHoCH | Interchangeable use of distinct concepts |

---

## Validation Against Strategy Matrix

Every specification is cross-referenced against `strategy_validation_matrix.yaml`. Each rule in the matrix maps to a required spec element. The Phase 0 audit evaluates all 22+ rules and returns a scored report.
