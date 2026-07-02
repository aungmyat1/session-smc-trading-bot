# Strategy Research and Validating System — Design Reference
# Recorded 2026-06-29 | Do not modify — this is the canonical design intent

Status: Authoritative
Version: 1.0
Updated: 2026-06-29
Owner: Platform Architecture
Authority: Level 5 — Pipeline Reference
Note: Phase numbers in this document are illustrative summaries.
Use canonical stage enum names (see DOC_AUTHORITY.md §Canonical Lifecycle Vocabulary).
Related: SYSTEM_ARCHITECTURE.md, CORE_ARCHITECTURE.md, STAGE1_AUDIT_SPEC.md

---

## Stage Summary Table

| Stage | Primary Purpose | Key Question | Typical Output |
|---|---|---|---|
| **1. Strategy Audit** | Validate the strategy specification | *Can this strategy be implemented objectively?* | Objective, complete rule set with ambiguities removed |
| **2. Historical Replay** | Validate rule behavior | *Does the strategy behave as intended on historical charts?* | Correct signal generation and behavioral accuracy |
| **3. Backtest** | Validate statistical edge | *Has the strategy been profitable after realistic trading costs?* | Performance metrics: Profit Factor, Expectancy, Drawdown |
| **4. Statistical Validation** | Validate the backtest evidence | *Is the measured edge statistically sufficient under the defined gates?* | PASS/FAIL evidence decision |
| **5. Robustness Tests** | Validate generalization | *Does the edge persist under different parameters and market conditions?* | Stability and robustness assessment |
| **6. Virtual Demo Trading** | Validate execution | *Can the complete trading system execute the strategy reliably in live-like conditions?* | Execution accuracy, latency, slippage, operational reliability |
| **7. Production Approval** | Validate deployment readiness | *Is there sufficient evidence to release an approved package?* | Formal approval and versioned strategy package |

Each stage answers exactly one question. If the answer is not clearly yes, the
strategy does not advance.

### Why this order

The sequence progressively reduces uncertainty. Each stage eliminates a specific
class of risk before the next, more expensive stage runs:

| Stage | Risk eliminated |
|---|---|
| Strategy Audit | Design risk — the specification is ambiguous or unimplementable |
| Historical Replay | Behavioral risk — the rules don't fire as written on real charts |
| Backtest | Performance risk — no statistical edge after realistic costs |
| Statistical Validation | Evidence risk — backtest results do not clear the required gates |
| Robustness Tests | Overfitting risk — the edge doesn't generalize across conditions |
| Virtual Demo Trading | Execution risk — the system breaks under live operational conditions |
| Production Approval | Deployment risk — insufficient evidence to commit real capital |

A strategy that reaches Stage 7 has had seven independent risk classes eliminated.
That is the only basis on which capital commitment is justified.

---

## Why SVOS, Not Just a Backtester

Professional quantitative firms do not take a strategy directly to backtesting.
They run a research pipeline where each stage must pass before the strategy is
allowed to move forward. This platform mirrors that: a **Strategy Validation
Operating System (SVOS)** that treats strategy validation as an operating
discipline, not a one-shot script. SVOS means **Strategy Research and Validating
System**.

The central principle: **a strategy is not advanced because it completed a step;
it is advanced only after it has satisfied objective quality gates, with every
revision versioned, justified, and reproducible.**

---

## Overall Workflow

```
New Strategy
      │
      ▼
Phase 0 ─ Strategy Audit           (Logic Verification)          PASS / FAIL / FIX
      │
      ▼
Phase 1 ─ Strategy Enhancement     (AI Suggestions + Rule Opt)
      │
      ▼
Phase 2 ─ Historical Replay        (Every trade inspected)        PASS / FAIL / FIX
      │
      ▼
Phase 3 ─ Backtest                 (Performance Measurement)      PASS / FAIL / FIX
      │
      ▼
Phase 4 ─ Statistical Validation   (Evidence Gate)                PASS / FAIL / FIX
      │
      ▼
Phase 5 ─ Robustness Tests         (Walk Forward, Monte Carlo,
           Parameter Stability, Regime Analysis, Execution Cost)   PASS / FAIL / FIX
      │
      ▼
Phase 6 ─ Virtual Demo Trading     (Execution Validation,
           Drift Detection)                                         PASS / FAIL
      │
      ▼
Phase 7 ─ Production Approval      (Package Approval)             [RECORD ONLY]
```

---

## Closed-Loop Iterative Workflow

Every failure generates actionable feedback and sends the strategy back to the
appropriate stage — not to the beginning, to the relevant fix point. Every
revision is versioned.

```
New Strategy
      │
      ▼
Strategy Audit
      ├── FAIL → AI edits specification → Audit again
      ▼
Historical Replay
      ├── FAIL → Refine rules → Replay again
      ▼
Backtest
      ├── FAIL → Improve logic or filters → Backtest again
      ▼
Robustness Tests
      ├── FAIL → Adjust parameters or simplify rules → Retest
      ▼
Demo Trading
      ├── FAIL → Analyze live drift → Return to research
      ▼
Production Approval
```

---

## Phase 0 — Strategy Audit

**This is the most important phase.** The system must understand the strategy
before testing it.

### Input formats accepted

- Markdown
- PDF
- Word document
- Plain text
- Screenshots

### Step 1 — Rule Extraction

Raw input is converted into a structured, machine-readable rule engine.

Example raw input:
```
London Session
Liquidity Sweep
15M CHOCH
FVG
Order Block
RR 1:2
Risk 0.3%
```

Extracted structure:
```
Session:     London
Entry:       CHOCH after Sweep
Confirmation: FVG
Filter:      HTF Bias
Stop:        Below Sweep
Target:      2R
```

### Step 2 — Rule Audit

The AI inspects the extracted rules for common flaws.

**Example — ambiguous entry timing:**
```
Rule: "Enter after CHOCH"

Question: Which candle?
  - Immediate (entry candle)?
  - Next candle?
  - Within 3 candles?
  - Unlimited?

Severity: HIGH   Status: FAIL
```

**Example — undefined structure:**
```
Rule: "Use Order Block"

Question: Which candle qualifies?
  - Last bullish candle before move?
  - Last bearish candle?
  - Engulfing candle?
  - Highest-volume candle?
  - What mitigation percentage?

Severity: HIGH   Status: FAIL
```

### Audit Summary Output

```
Ambiguous rules:        17
Missing parameters:      8
Contradictions:          3
Undefined filters:       5
Execution conflicts:     2

Overall: NOT READY
```

Only after the rulebook is complete does the strategy move forward.

---

## Phase 1 — Strategy Enhancement (AI Strategy Editor)

The AI acts as a quant reviewer. It asks targeted questions to resolve every
ambiguity found in Phase 0 and optionally suggest optimizations.

### Example Q&A format

```
You use BOS.
Should BOS require a close beyond the level?
  → Yes / No

Should FVG remain valid after N candles?
  → Unlimited / Until mitigated / After N candles

How many sweeps are allowed before invalidation?
  → 1 / 2 / Unlimited
```

The output is a **complete, unambiguous specification**. Every parameter has a
value. Every rule has a defined condition. This spec is locked (versioned) before
Phase 2 begins.

---

## Phase 2 — Historical Replay

**This is manual verification.** Every signal is replayed chronologically.

### Replay format

```
2025-02-15  09:05
  Sweep ↓
  CHOCH ↓
  FVG   ↓
  Entry ↓
  TP
```

### Per-trade validation questions

```
Was the sweep valid?          YES / NO
Did CHOCH occur?              YES / NO
Was FVG valid?                YES / NO
Entry correct?                YES / NO
```

If any check fails:
```
Rule issue found.
Return to Strategy Editor (Phase 1).
```

The purpose is to catch discrepancies between the written spec and what the
engine actually executes — before running thousands of simulated trades.

---

## Phase 3 — Backtest Validation

Automation begins here. The engine evaluates:

- Win Rate
- Profit Factor
- Expectancy
- Drawdown (max and average)
- Trade frequency
- Average RR
- Risk-adjusted return

Gate (minimum): `n ≥ 50` AND `net PF > 1.0` at **standard** AND **2× spread stress**.

If results do not meet thresholds, the system reports the **weakest areas
specifically** rather than just failing. The strategy is not discarded — it gets
a targeted remediation route.

---

## Phase 4 — Robustness Audit

Good backtests can still be misleading. Institutional firms stress-test
systematically across multiple dimensions.

### Spread sensitivity
```
+1 pip  | +2 pip  | +3 pip  | +5 pip
```

### Slippage sensitivity
```
0 pip  | 0.2 pip  | 0.5 pip  | 1 pip
```

### Parameter stability (example: sweep threshold)
```
0.10  |  0.12  |  0.15  |  0.18  |  0.20
```

### Walk-forward
```
2022  |  2023  |  2024  |  2025
```

### Monte Carlo
```
5,000 simulations — random trade order sampling
```

If the strategy only works under perfect conditions, it fails. The system records
**stable regions** and **failure boundaries**, not just an aggregate score.

---

## Phase 5 — Demo Validation

Connect to MT5 (Vantage demo account). Track live execution vs research
expectations.

### Drift metrics monitored

```
Expected PF:        1.45    Actual PF:        1.42    Diff: 2%
Expected Win Rate:  53%     Actual Win Rate:  51%
Expected Spread:    0.7     Actual Spread:    0.9
```

The system monitors whether live behavior matches the research model. Significant
drift triggers a return to research. A PASS here means the strategy behaves in
live conditions as the backtest predicted.

---

## Phase 6 — Production Gate  [RECORD ONLY — do not build]

The system produces a final approval checklist:

```
Strategy:       ST-A2

Rule Audit:     PASS
Replay:         PASS
Backtest:       PASS
Walk Forward:   PASS
Monte Carlo:    PASS
Execution:      PASS
Demo:           PASS

Approved:       YES
```

Only after all gates hold does the strategy move to live capital.
This is SVOS in its complete institutional form. Not in scope for current build.

---

## Suggested Module Architecture

```
strategy_validation_os/
│
├── strategy_intake/
│   ├── parser.py               # multi-format input → raw text
│   ├── rule_extractor.py       # raw text → structured rules
│   ├── ambiguity_detector.py   # flag unclear rules
│   ├── contradiction_checker.py
│   └── specification_builder.py # final machine-readable spec
│
├── strategy_editor/
│   ├── ai_reviewer.py          # Q&A loop to resolve ambiguities
│   ├── optimization_suggestions.py
│   └── version_manager.py      # every accepted revision = new version
│
├── historical_replay/
│   ├── replay_engine.py
│   ├── replay_validator.py     # per-trade human verification
│   └── replay_report.py
│
├── backtesting/
│   ├── simulator.py
│   ├── performance_metrics.py
│   └── statistical_report.py
│
├── robustness/
│   ├── walk_forward.py
│   ├── monte_carlo.py
│   ├── parameter_sensitivity.py
│   ├── regime_analysis.py
│   └── execution_costs.py
│
├── demo_validation/
│   ├── live_monitor.py
│   ├── drift_detector.py
│   └── broker_comparison.py
│
├── governance/
│   ├── approval_engine.py
│   ├── stage_gates.py
│   ├── audit_log.py
│   └── strategy_registry.py
│
├── reports/
│   ├── html_report.py
│   ├── pdf_report.py
│   ├── dashboard.py
│   └── executive_summary.py
│
└── config/
    ├── thresholds.yaml
    ├── governance.yaml
    └── strategy_templates/
```

---

## Key Design Principles (carry into every implementation decision)

1. **Understand before testing.** No strategy reaches Phase 2 with an ambiguous rule.

2. **Every failure is actionable.** FAIL does not mean discard — it means return to
   the specific stage with specific remediation. The system names the weakest area.

3. **Every revision is versioned.** A spec change = a new version. You cannot
   re-run a trial under a new spec and call it the same trial.

4. **Phase gates are hard.** Partial passes do not exist. The gate either clears
   or the strategy returns.

5. **Live behavior must match research.** Phase 5 exists to catch the gap between
   backtest assumptions and actual MT5 execution — spread, slippage, fill timing.

6. **Closed loop, not linear.** The workflow is a feedback system. A strategy may
   cycle through Phases 0–4 multiple times before reaching Phase 5.
