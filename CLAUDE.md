# Strategy Engineering Platform — Claude Instructions
# v2.0 | read every session

---

## §0 — HARD RULES (violation = stop and ask)

1. **Never enable live trading** until a strategy holds a valid Production Approval package
   AND the VT Markets bot has passed its own execution gate.
   `LIVE_TRADING=false` and `DEMO_ONLY=true` until the owner flips them manually.

2. **Never tune parameters mid-trial.** Every parameter change = a new trial with a new
   trial ID pre-registered in `docs/VERDICT_LOG.md`. This pattern destroyed the
   ag-auto-trade graveyard. Do not repeat it.

3. **Net-of-fees only.** A backtest result without spread + commission applied is not a
   result. VT Markets Standard: EURUSD ~0.8–1.2 pip, GBPUSD ~1.2–1.8 pip RT.
   Robust PASS = net PF > 1.25 AND Sharpe > 1.2 AND MaxDD < 15% at BOTH standard AND
   2× spread stress (see §0.6 for the full gate).

4. **Never commit secrets.** MetaAPI tokens, VT Markets credentials, and Telegram tokens
   live in `.env` (gitignored). Never in code.

5. **Read `docs/` before writing new code.** The governing implementation plan is
   `docs/svos/STRATEGY_ENGINEERING_PLATFORM_IMPLEMENTATION_PLAN.md`. The strategy
   verdict history is `docs/VERDICT_LOG.md`. Check both before proposing anything.

6. **Phase gates are mandatory.** No stage advances without the required evidence:
   n > 200 AND net PF > 1.25 at BOTH standard AND 2× spread stress AND Sharpe > 1.2
   AND MaxDD < 15% for Phase-3 (Statistical Validation). No Virtual Demo without this
   PASS. No Production Approval without Virtual Demo PASS AND a 30+ day stable demo
   with n ≥ 50 trades and no critical execution failures (see
   `docs/STRATEGY_PORTFOLIO_ROADMAP.md` deployment constraint).
   Superseded 2026-07-01: the prior gate (n ≥ 50, net PF > 1.0) still governs any
   evidence recorded before this date (e.g. ST-A2's PF_2x=1.025, n=169) — that
   evidence does not retroactively satisfy the new gate and must be re-earned on
   revalidation.

7. **One position per symbol.** No concurrency within a pair.

8. **Minimize total token usage.** Keep responses concise, read only the files needed,
   avoid duplicate analysis/tool calls, and prefer the smallest action that completes
   the task safely.

---

## §1 — PROJECT OBJECTIVE

This is not just a trading bot — it is a two-system quantitative trading platform:

```
             ┌───────────────────────────┐
             │       SVOS (research)      │   gcp-vm1
             │  Strategy Validation OS    │
             └─────────────┬──────────────┘
                            │  Validated Strategy Artifact
                            ▼
             ┌───────────────────────────┐
             │  Production Execution      │   auto-trade-vps
             │  (VT Markets Forex Bot)       │
             └─────────────┬──────────────┘
                            ▼
                    Broker Execution (MetaAPI / VT Markets)
```

**Governing principle: research never trades.** SVOS discovers, backtests, and
validates strategies. Production loads and executes only an approved strategy
package. Canonical architecture: `docs/svos/CORE_ARCHITECTURE.md` (lifecycle/registry),
`docs/svos/DEPLOYMENT_TOPOLOGY.md` (two-node infra boundary — SVOS on `gcp-vm1`,
execution on `auto-trade-vps`). Do not duplicate those diagrams here; this section
is the summary view only — see `docs/00_Project/DOC_AUTHORITY.md` before trusting any
architecture claim that conflicts with them.

SVOS pipeline:

```
Strategy Input
  → Specification & Versioning
  → Strategy Audit & Refinement
  → Historical Replay
  → Backtest & Statistical Validation
  → Robustness Validation
  → Offline Virtual Demo
  → Production Approval
  → Approved Strategy Package
  → Simple VT Markets Forex Bot
  → Monitoring & Revalidation
```

**Input:** any systematic Forex strategy with an objective specification.
**Output:** a versioned, evidence-backed Production Approval package — or an honest FAIL
with findings and a remediation route.

The trading bot is downstream. It loads only a valid Approved Strategy Package. It does
not audit, backtest, optimize, or approve strategies. Broker credentials are unavailable
to research, reporting, and dashboard processes.

**No strategy holds Production Approval.** But do not confuse this with "nothing is
running": `config/strategy_portfolio.yaml` currently runs FIVE strategies in tiered
demo/shadow execution — ST-A2 (demo, tier1), LondonBreakout (demo, tier2), NYMomentum
(demo, tier2), AdaptiveSMC (shadow, tier3), VWAPMeanReversion (shadow, tier3). This is a
tracked governance gap, not evidence of approval: these strategies run ahead of formal
SVOS lifecycle registration (see `docs/VERDICT_LOG.md` 2026-07-01 entry). ST-A2's SVOS
lifecycle stage is still `DEFERRED_REVALIDATION` (§6) — the config running it in demo does
not change that. `LIVE_TRADING=false` / `DEMO_ONLY=true` remain enforced regardless.
`docs/STRATEGY_PORTFOLIO_ROADMAP.md` (the sequential A→D ladder, dated 2026-06-23) predates
this five-strategy config and is now stale on which strategies are actually deployed —
treat the roadmap's gating logic as intent, not as a description of current deployment.

---

## §2 — CANONICAL PIPELINE (7 phases)

Every strategy passes through all phases in order. No skipping. Each phase produces a
PASS / FAIL / FIX verdict. FIX loops back with a revised spec — it does not skip forward.

```
Phase 0  Strategy Audit
         Intake validation (format, instruments, data availability) +
         logic review (completeness, ambiguity, contradictions,
         lookahead risk, execution feasibility).
         Output: PASS / FAIL / FIX

Phase 1  Strategy Enhancement
         AI suggestions + rule optimization on the audited spec.
         Human accepts the revised spec before it becomes the version
         that enters Phase 2. No enhancement runs on a failed audit.
         Output: accepted revised spec or unchanged spec

Phase 2  Historical Replay
         Chronological candle replay, zero future access.
         Every trade inspectable — entry, SL, TP, state transitions,
         feature availability all recorded.
         Output: PASS / FAIL / FIX

Phase 3  Backtesting
         Statistical validation on the replay-approved spec and frozen dataset.
         Realistic fees applied (spread + commission). No fees = not a result.
         Gate: n > 200 AND net PF > 1.25 at standard AND 2× spread stress
         AND Sharpe > 1.2 AND MaxDD < 15%.
         Output: PASS / FAIL / FIX

Phase 4  Robustness Tests
         Walk-forward | Monte Carlo | Parameter Stability
         Regime Analysis | Execution Cost sensitivity.
         Records stable regions and failure boundaries, not just a score.
         Output: PASS / FAIL / FIX

Phase 5  Offline Virtual Demo
         Historical replay through the same order, risk, and position-management
         interfaces intended for the live bot. No broker connection. No network.
         Fully deterministic. Drift detection: compares virtual execution vs
         backtest expectations. Part of SVOS research qualification.
         NOT the same as a live VT Markets demo account (that is post-approval only).
         Output: PASS / FAIL

Phase 6  Production Approval  [RECORD ONLY — do not build]
         This is SVOS (Strategy Validation and Operational System).
         Live capital deployment after all prior phases hold current PASS.
         Scope: understand and document only. Do not implement toward this.
```

**Implementation ceiling: Phase 5.** Build Phases 0–5 and the VT Markets bot that runs
under a Phase 5 virtual demo. Phase 6 is out of scope until explicitly unlocked.

---

## §3 — LIFECYCLE STAGES

The canonical lifecycle lives in `svos/lifecycle/manager.py`. Stages map directly to
the §2 pipeline phases:

```
DRAFT → INTAKE → AUDIT → REFINEMENT → HISTORICAL_REPLAY
→ STATISTICAL_VALIDATION → ROBUSTNESS_VALIDATION
→ VERIFICATION_READY → VIRTUAL_DEMO → EXECUTION_VALIDATION
→ PAPER_TRADING → LIVE_DEMO → PRODUCTION_CANDIDATE
→ PRODUCTION → MONITORING → REVALIDATION → RETIRED
```

Note: LIVE_DEMO (online VT Markets demo) is post-approval, not Phase 5.
Phase 5 VIRTUAL_DEMO is OFFLINE — no broker, no network.

Failure at any phase loops back to REFINEMENT (for Phases 0–4) or blocks (Phase 5).
`svos/lifecycle/manager.py` is the exclusive mutation authority. No script, runner, or
catalog update may change strategy stage by writing YAML directly.

---

## §4 — WRITE ACTIONS REQUIRE CONFIRM TOKEN

Any order placement, strategy promotion, or live configuration change requires an
exact-match CONFIRM token. Agent must never self-execute. Always propose, wait for token.

| Token | Action |
|---|---|
| `CONFIRM-LONG-EURUSD` | Place long market entry on EURUSD |
| `CONFIRM-SHORT-EURUSD` | Place short market entry on EURUSD |
| `CONFIRM-LONG-GBPUSD` | Place long market entry on GBPUSD |
| `CONFIRM-SHORT-GBPUSD` | Place short market entry on GBPUSD |
| `CONFIRM-CLOSE-EURUSD` | Close open EURUSD position at market |
| `CONFIRM-CLOSE-GBPUSD` | Close open GBPUSD position at market |
| `CONFIRM-LIVE-ON` | Enable live trading (owner only, after all gates pass) |

---

## §5 — BROKER / AUTH

- Broker: **VT Markets** (MT5 demo account for the active System 2 demo path)
- Connection: **MetaAPI Cloud SDK** (`metaapi-cloud-sdk>=29`)
- Demo: `VTMARKETS_DEMO_METAAPI_ID` or legacy `METAAPI_ACCOUNT_ID` (from `.env`)
- Live: not configured for agent use; `LIVE_TRADING=false` remains mandatory
- Historical data: Dukascopy public feed via `scripts/fetch_data.py`
- Telegram alerts: `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` (from `.env`)
- Magic number: flat `21099` for the demo execution path (`config/demo.yaml`, `execution/trade_manager.py`)
- Live-traded pairs: EURUSD, GBPUSD, XAUUSD (`scripts/run_st_a2_demo.py`)
- Config ceiling: `config/demo.yaml` also lists USDJPY as an allowed pair, but it is not currently traded by the deployed ST-A2 demo runner.
- Never use raw REST for signed endpoints — always use the SDK.

### Broker Identity Correction

The active demo account is a VT Markets MT5 demo account connected through MetaAPI.
It is not a Vantage account.

Authoritative path:

```text
System 2 -> MetaAPI ExecutionAdapter -> VT Markets MT5 demo
```

Requirements:

- Replace Vantage assumptions in current broker/cost work with VT Markets.
- Verify broker/server/account-environment metadata through read-only MetaAPI
  account information before collecting measurements.
- Never write VT Markets measurements into the existing `vantage_measured` profile.
- Leave `vantage_measured` inactive and unchanged.
- If a new candidate profile is needed later, use `vtmarkets_demo_measured`,
  subject to the existing config schema and naming conventions.
- Mark all output explicitly as DEMO-account evidence.
- Do not claim that demo costs represent VT Markets live-account costs.
- If an existing report incorrectly labels this account as Vantage, preserve the
  raw observations but regenerate the report with correct broker provenance and
  flag the old report as `BROKER_IDENTITY_MISMATCH`.
- Resolve XAUUSD using the VT Markets account's actual MetaAPI symbol
  specifications. Do not guess names such as XAUUSD.a, XAUUSDm or GOLD.
- Preserve XAUUSD as the canonical project symbol and store any exact broker
  symbol separately in the broker-symbol mapping.

---

## §6 — ST-A2 STATE

ST-A2 (Session Liquidity Reversal) SVOS lifecycle status: **DEFERRED_REVALIDATION**

- `approved: false` | `current: false` | no registry-authorized deployment target
- All code, datasets, reports, and backtest findings are preserved as legacy research.
- ST-A2 cannot satisfy any qualification gate until it re-enters at Intake and passes
  the full pipeline from zero with current evidence (new gate — see §0.6).
- Do not treat any ST-A2 path, report, or metric as platform evidence.
- **Separately:** `config/strategy_portfolio.yaml` runs ST-A2 in live-demo (tier1,
  `enabled: true`, `execution_mode: demo`) today. This is a real, tracked governance
  gap between the SVOS registry (DEFERRED_REVALIDATION) and the running config (demo
  live) — not a contradiction to silently resolve by editing one or the other. See §1
  and `docs/VERDICT_LOG.md` 2026-07-01 entry.

Known completed trials (immutable — do not re-run):
- **ST-A**: FAIL — passes standard spread but fails 2× stress
- **ST-A2**: PASS Phase-0 (PF_2x=1.025, n=169) but deferred before demo — revalidate later
- **EXP05**: FAIL — no variant clears PF_2x > 1.25 AND WR ≥ 40% AND n ≥ 100 AND DD < 15R

---

## §7 — TRIAL REGISTRATION

Every strategy trial or parameter change = a new row in `docs/VERDICT_LOG.md`.
Pre-register the spec BEFORE running the backtest.
Never re-run on the same trial ID after a parameter change.

Gate (Phase-3, effective 2026-07-01): n > 200 AND net PF > 1.25 AND Sharpe > 1.2
AND MaxDD < 15% at BOTH standard AND 2× spread stress. Single-spread PASS is
insufficient (ST-A failed 2×, T29-GBP failed 2×). Trials recorded before this date
under the old n≥50/PF>1.0 gate remain in the log as historical record but do not
satisfy the current gate.

---

## §8 — KNOWN PRIOR FAILURES (do not re-propose)

| Trial | Strategy | Result | Root cause |
|---|---|---|---|
| T27 | EURUSD session-box sweep only | net PF=0.58 FAIL | No LTF confirmation — sweep alone has no edge |
| T28 | GBPUSD session-box sweep only | net PF=0.95 FAIL | Same; fails 2× stress |
| T29-EUR | EURUSD BOS-retest continuation | gross PF=0.83 FAIL | No raw edge before fees |
| T29-GBP | GBPUSD BOS-retest continuation | 2× stress FAIL | Marginal at standard, fragile |
| ST-1 | Session IB sweep + CHoCH (entry at close) | FAIL | Entry too late; SL too wide |
| ST-A | Sweep Reversal — no min SL filter | 2× stress FAIL | GBPUSD London drag |
| EXP05-A–E | ST-A2 pre-demo optimization variants | FAIL | No variant clears all 4 gates |

---

## §9 — GOVERNANCE AGENT OPERATING MODE

Adopted 2026-07-04. Applies to every non-trivial task in this repo. This section
supersedes any pasted or externally-sourced "governance agent" prompt — do not
re-adopt a competing phase list or role definition mid-session; update this
section instead.

**Milestone vocabulary note:** this section deliberately does NOT define its own
phase numbers. Use the canonical lifecycle enum in `svos/lifecycle/manager.py`
(`DRAFT → INTAKE → AUDIT → REFINEMENT → HISTORICAL_REPLAY →
STATISTICAL_VALIDATION → ROBUSTNESS_VALIDATION → VERIFICATION_READY →
VIRTUAL_DEMO → EXECUTION_VALIDATION → PAPER_TRADING → LIVE_DEMO →
PRODUCTION_CANDIDATE → PRODUCTION → MONITORING → REVALIDATION → RETIRED`) or the
§2/§3 Phase 0–6 summary view. Per `docs/00_Project/DOC_AUTHORITY.md`, a third
numbering scheme is an authority conflict, not a style choice — if you're
tempted to introduce one, stop and reconcile against DOC_AUTHORITY.md instead.

### Role

Before writing code, act as program manager, chief architect, tech lead, QA
lead, release manager, and docs lead — not just an implementer. Priority order:
protect the roadmap and architecture first, ship code second.

### Before implementing anything, determine

- Which system owns this: SVOS (research, `gcp-vm1`) or Production Execution
  (`auto-trade-vps`)? Research never trades; execution never optimizes/backtests/
  qualifies (§1).
- Which lifecycle stage/phase owns it (see vocabulary note above).
- Which ADR (`docs/svos/ADR-*.md`) governs it, if any.
- Does it duplicate an existing module, pipeline, orchestrator, or config
  system? (This repo has a known duplication debt — two parallel SVOS
  orchestrators per [[project-readiness-audit-2026-07-01]] memory — don't add a
  third.)
- Does it belong to a future milestone beyond the current implementation
  ceiling (Phase 5 / VIRTUAL_DEMO per §2)? If so, reject or flag as
  out-of-scope rather than building toward it.

If any answer is unclear, stop and ask rather than guessing.

### Scope validation checklist

What problem does this solve · why is it required · which system owns it ·
which stage/ADR governs it · what existing code depends on it · what future
work depends on it · what acceptance criteria will it satisfy.

### Architecture/dependency checks

Look for duplicate modules, services, pipelines, dashboards, or config systems;
circular imports; layering violations; unnecessary abstraction. Recommend
consolidation over addition when duplication exists — see
`docs/AUDIT_IMPLEMENTATION_PLAN_2026-07-01.md` for known instances.

### Roadmap alignment score (report when doing non-trivial work)

100 = required by current stage · 90 = strongly supports it · 70 = useful but
should wait · 50 = future stage · 30 = low priority · 10 = drift · 0 = reject.

### Reporting format for non-trivial implementations

Keep it short — this repo's §0.8 token-efficiency rule wins over exhaustive
report boilerplate. Cover only what changed:

```
Status: <done/blocked/partial>
Stage/system: <lifecycle stage> / <SVOS|Execution|shared>
Alignment score: <0-100> — <one line why>
Completed: <bullets>
Remaining/blocked: <bullets, or "none">
Risks: <architecture/testing/deployment — only if non-trivial>
Docs touched: <files, or "none needed">
```

Skip the full report for small, unambiguous fixes — use judgment, don't
ceremony every diff.

### Hard rules (additive to §0, do not restate/renumber §0)

- Never build toward Phase 6 / PRODUCTION_APPROVAL / live trading (already
  covered by §0.1 — this just reaffirms it applies to governance-mode work too).
- Never introduce a second implementation of something that already exists
  (orchestrator, lifecycle mutator, config loader) — consolidate instead.
- Never claim a task complete without verification (tests run, import checked,
  or explicitly stated as unverified with why).
- Never invent a new phase/milestone taxonomy — see vocabulary note above.
