# Stage 1 — Strategy Specification Validation Engine
# Implementation Specification | Recorded 2026-06-29

---

## Purpose

Determine whether a strategy specification is sufficiently complete, objective,
measurable, and internally consistent **before** it proceeds to Historical Replay.

This stage is NOT responsible for determining whether a strategy is profitable.
It is a quality gate only.

---

## Internal Pipeline

```
User Strategy Input
      │
      ▼
1.  Input Validation              — required fields present?
      │
      ▼
2.  Rule Completeness Validation  — every rule answers When/Where/Why/How/Exit/Cancel?
      │
      ▼
3.  Ambiguity Detection           — subjective wording flagged, measurable replacement suggested
      │
      ▼
4.  Logical Consistency           — conflicting rules detected
      │
      ▼
5.  Measurability Validation      — every rule convertible to objective code?
      │
      ▼
6.  Institutional Rule Validation — SMC/market-structure concepts correctly defined?
      │
      ▼
7.  Risk Management Validation    — SL, TP, risk%, daily loss, drawdown, sizing present?
      │
      ▼
8.  Testability Validation        — two independent reviewers get identical trades?
      │
      ▼
9.  AI Specification Improvement  — auto-improve weak wording, never change intent
      │
      ▼
10. Final Readiness Assessment    — aggregate score + readiness decision
```

---

## Validator Interface Contract

Every validator must return the same structure:

```json
{
    "validator": "AmbiguityDetector",
    "score": 82,
    "status": "FAIL",
    "findings": [...],
    "recommendations": [...]
}
```

Status values: `PASS` | `WARN` | `FAIL`

---

## Component Specifications

### 1. Input Validation

Checks that all required fields exist.

Required fields:
- Strategy name, Instrument, Market, Timeframe, Trading session
- Direction (Long / Short / Both)
- Entry rules, Exit rules
- Stop Loss, Take Profit
- Risk model, Position sizing

Output:
```json
{ "score": 95, "status": "PASS", "missing": [] }
```

---

### 2. Rule Completeness Validation

Every rule must answer six questions:

| Question | Meaning |
|---|---|
| When? | Under what time or session condition |
| Where? | At what price level or structure |
| Why? | What market condition makes this valid |
| How? | Exact execution mechanics |
| Exit? | When does the trade close |
| Cancel? | When is the setup invalidated |

Output: incomplete rules list, missing questions per rule, completeness score.

---

### 3. Ambiguity Detection

Reject subjective wording. Suggest measurable replacements.

| Rejected phrase | Reason | Recommended replacement |
|---|---|---|
| Strong trend | Subjective | EMA50 > EMA200 |
| Good momentum | Subjective | RSI(14) > 55 |
| High probability | Unmeasurable | Not a rule — remove |
| Large candle | Relative | Body ≥ 1.5 × ATR(14) |
| Near support | Vague | Within 5 pips of prior swing low |

Output per finding:
```json
{
    "phrase": "Strong trend",
    "reason": "Subjective",
    "recommendation": "EMA50 > EMA200"
}
```

---

### 4. Logical Consistency Validation

Detect contradictions between rules.

Examples:
- "Trade only London" AND "Trade only Asian" → CONFLICT
- "Maximum 2 trades/day" AND "Unlimited entries" → CONFLICT
- "Long only" AND "Enter short on BOS" → CONFLICT

Output: conflict list with severity (HIGH / MEDIUM / LOW) and suggested resolution.

---

### 5. Measurability Validation

Determine whether every rule can be converted into objective code.

| Example | Verdict |
|---|---|
| "Price looks strong" | FAIL — not measurable |
| "ATR(14) > 20" | PASS — measurable |
| "Wait for confirmation" | FAIL — confirmation undefined |
| "BOS close beyond prior swing high by ≥ 1 pip" | PASS — measurable |

Output: measurable rules, non-measurable rules, score.

---

### 6. Institutional Rule Validation

Validates that SMC / market-structure concepts are defined precisely.

Supported concepts:
- Market Structure (BOS, CHoCH)
- Liquidity Sweep
- Order Block
- Fair Value Gap (FVG)
- Premium / Discount zones
- Session Filter

Precision requirement example:

| Rejected | Accepted |
|---|---|
| "Wait for liquidity" | "Price sweeps prior day's high by ≥ X pips before BOS confirmation" |
| "Use Order Block" | "Last bearish candle before displacement move, mitigation ≥ 50%" |
| "FVG entry" | "Enter on first retrace into 3-candle FVG body, valid for ≤ 5 candles" |

Output: Institutional Quality Score per concept.

---

### 7. Risk Management Validation

Verify presence and validity of:

| Control | Required |
|---|---|
| Stop Loss | Yes — defined, measurable |
| Take Profit | Yes — defined in R or pips |
| Risk % per trade | Yes — fixed fractional |
| Maximum daily loss | Yes |
| Maximum drawdown | Yes |
| Maximum open positions | Yes |
| News rules | Recommended |
| Position sizing formula | Yes |

Output: Risk Score, missing controls, warnings.

---

### 8. Testability Validation

Determine whether two independent reviewers (or two AI agents) given the same
chart would execute identical trades.

Key questions:
- Can every entry be identified without judgment?
- Can every exit be identified without judgment?
- Would two reviewers get identical trade lists?
- Can the rules be coded without assumptions?

Output: Testability Score, list of reasons where divergence could occur.

---

### 9. AI Specification Improvement

Automatically improve weak wording without changing the trading idea.

For every recommendation:
```json
{
    "original": "Enter after CHOCH",
    "improved": "Enter on the close of the first M15 candle that closes beyond the CHoCH level within 3 candles of the sweep",
    "reason": "Entry timing was undefined",
    "expected_improvement": "Eliminates 3 ambiguous candle choices, makes replay deterministic"
}
```

Constraint: never modify the strategy concept — only improve precision of expression.

---

### 10. Final Readiness Assessment

Aggregate all validator results into a single decision.

Output:
- Overall Score (0–100)
- PASS / FAIL per validator
- Critical issues (block advancement)
- Warnings (proceed with caution)
- Recommendations
- Readiness Decision

**Readiness Decision values:**

| Decision | Meaning |
|---|---|
| `READY_FOR_REPLAY` | All validators pass — proceed to Stage 2 |
| `REQUIRES_REVISION` | Fixable issues found — return to Stage 1 with feedback |
| `INCOMPLETE` | Required fields missing — cannot evaluate |
| `REJECTED` | Fundamental flaws — strategy concept is not implementable as specified |

---

## Module Architecture

```
strategy_validation/
│
├── models/                         # data classes and schemas
│
├── validators/
│   ├── input_validator.py
│   ├── completeness_validator.py
│   ├── ambiguity_validator.py
│   ├── consistency_validator.py
│   ├── measurability_validator.py
│   ├── institutional_validator.py
│   ├── risk_validator.py
│   └── testability_validator.py
│
├── ai/
│   └── improvement_engine.py       # AI spec improvement, separate from validation
│
├── reports/
│   └── report_generator.py         # JSON → Markdown + HTML, no validation logic
│
├── scoring/
│   └── scoring_engine.py           # aggregates validator scores
│
└── pipeline/
    └── strategy_validation_pipeline.py   # orchestrates all validators in order
```

Architecture rules:
- Each validator is independent — no validator calls another
- Validation logic is separate from reporting logic
- AI recommendations are separate from validation results
- New validators can be added without modifying existing ones
- All outputs are structured JSON first; Markdown/HTML are rendered from JSON

---

## Quality Requirements

| Requirement | Detail |
|---|---|
| Deterministic | Same input always produces same output |
| Reproducible | Results auditable and traceable |
| Unit testable | Each validator independently testable |
| Extensible | New validators added without modifying pipeline |
| Structured output | JSON primary; Markdown + HTML secondary |
| Audit log | Every run produces a traceable log entry |
| No placeholders | All components production-quality |

---

## Deliverables (when built)

1. Complete module architecture
2. Validation pipeline
3. Validator interfaces (base class contract)
4. Scoring engine
5. Report generator (JSON → Markdown + HTML)
6. AI recommendation engine
7. JSON schemas for all validator outputs
8. Unit tests per validator
9. Documentation
10. Example validation reports (PASS, REQUIRES_REVISION, REJECTED)
