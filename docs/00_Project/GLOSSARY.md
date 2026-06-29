# SVOS Documentation Glossary

Date: 2026-06-29
Status: Authoritative
Version: 1.0
Updated: 2026-06-29
Owner: Platform Architecture
Authority: Level 1 — Product
Related: DOC_AUTHORITY.md, SYSTEM_ARCHITECTURE.md, CORE_ARCHITECTURE.md

---

## Purpose

This glossary defines every domain term used across the SVOS repository.

When a term has multiple usages in legacy documents, the definition here is
authoritative. Legacy documents must be updated to match this glossary; this
glossary must not be changed to match legacy documents.

---

## Platform Terms

**SVOS** — Strategy Validation Operating System. The research qualification
subsystem responsible for intake, audit, refinement, replay, backtest, and
robustness validation. Does NOT include broker execution, risk qualification,
or deployment.

**EVF** — Execution Validation Framework. The execution qualification
subsystem responsible for virtual execution, broker simulation,
microstructure modeling, cost and latency models, order lifecycle simulation,
and recovery testing.

**RGM** — Risk Governance Module. Capital allocation and risk qualification.
Current status: documented as future work; not yet implemented.

**SMO** — Strategy Monitoring Operations. Drift detection and revalidation.
Current status: partially implemented in `monitoring/`; no formal SMO package.

**ISOP** — Intelligent Strategy Operating Platform. The target full-platform
architecture: SVOS + EVF + RGM + Governance + SMO.

**LifecycleAuthority** — The only application service permitted to authorize
lifecycle stage transitions. Implemented in `svos/governance/service.py`.
No other module may mutate lifecycle state. No direct YAML writes allowed.

**Governing Plan** — The document
`docs/svos/STRATEGY_ENGINEERING_PLATFORM_IMPLEMENTATION_PLAN.md` (date:
2026-06-29). Supersedes all prior scope, roadmap, and objective documents.

---

## Lifecycle Stages (Canonical)

The canonical lifecycle is implemented in `svos/lifecycle/manager.py`.
These are the only valid stage identifiers for code, configuration, and
documentation.

```
DRAFT → INTAKE → AUDIT → REFINEMENT → HISTORICAL_REPLAY
  → STATISTICAL_VALIDATION → ROBUSTNESS_VALIDATION
  → VERIFICATION_READY → VIRTUAL_DEMO → EXECUTION_VALIDATION
  → PAPER_TRADING → LIVE_DEMO → PRODUCTION_CANDIDATE
  → PRODUCTION → MONITORING → REVALIDATION → RETIRED
```

Remediation paths:
- `AUDIT` failure → `REFINEMENT` → `AUDIT`
- `HISTORICAL_REPLAY` failure → `REFINEMENT`
- `STATISTICAL_VALIDATION` failure → `REFINEMENT`
- `ROBUSTNESS_VALIDATION` failure → `REFINEMENT`
- `VIRTUAL_DEMO` failure → `REFINEMENT`
- `REVALIDATION` → `HISTORICAL_REPLAY` (requires research) or `RETIRED`

**DRAFT** — Strategy created but not yet submitted for intake.

**INTAKE** — Strategy under initial intake review. Format, instruments, and
data availability checked.

**AUDIT** — Strategy under rule audit. Ambiguity, contradiction, lookahead
risk, and execution feasibility assessed. Produces a quality gate decision.

**REFINEMENT** — Strategy returned for specification improvement. Can be
entered from AUDIT, HISTORICAL_REPLAY, STATISTICAL_VALIDATION,
ROBUSTNESS_VALIDATION, VIRTUAL_DEMO, or REVALIDATION.

**HISTORICAL_REPLAY** — Logic verification via chronological candle replay.
Tests event sequencing, session logic, and entry/exit timing. Does not
measure profitability.

**STATISTICAL_VALIDATION** — Edge validation via backtesting. Realistic fees
required. Phase-0 gate: n ≥ 50 AND net PF > 1.0 at BOTH standard AND 2×
spread stress. Single-spread PASS is insufficient.

**ROBUSTNESS_VALIDATION** — Walk-forward, Monte Carlo, parameter stability,
and regime analysis. Records stable regions and failure boundaries.

**VERIFICATION_READY** — Research-to-execution handoff. The strategy has
research evidence of an edge. Does NOT mean the strategy is executable,
risk-approved, or demo-approved.

**VIRTUAL_DEMO** — **OFFLINE** historical replay through the same order,
risk, and position-management interfaces intended for the live bot. No broker
connection. No network access. Fully deterministic. Part of SVOS research
qualification. NOT the same as a live broker demo account.

**EXECUTION_VALIDATION** — EVF qualification. Virtual execution, broker
simulation, microstructure modeling, cost/latency stress, and recovery
testing. Strategy code is unchanged; execution environment is simulated.

**PAPER_TRADING** — Simulated trading with real-time market data but no
capital at risk. After EVF qualification.

**LIVE_DEMO** — **ONLINE** real-time observation on a Vantage demo account.
Occurs AFTER Production Approval, not during research. Requires explicit
Live Demo Authorization from governance.

**PRODUCTION_CANDIDATE** — All prior gates passed. Awaiting final production
approval.

**PRODUCTION** — Authorized live deployment. Only possible after Production
Approval Package is validated by the bot at startup.

**MONITORING** — Ongoing performance observation. SMO is responsible.

**REVALIDATION** — Triggered by drift detection. Strategy re-enters research
from `HISTORICAL_REPLAY` or is `RETIRED`.

**RETIRED** — Strategy permanently removed from active qualification.

---

## Evidence Terms

**QUALIFYING_REAL** — Evidence produced by a current, complete, reproducible
run with a valid manifest. The only evidence type that can satisfy a
production approval gate.

**SYNTHETIC** — Evidence produced by test fixtures, generators, or
hypothetical scenarios. Cannot satisfy any qualification gate.

**LEGACY_IMPORTED** — Evidence imported from before the canonical evidence
system existed. Cannot satisfy any qualification gate.

**Approved Strategy Package** — A signed artifact consumed by the Vantage
bot at startup. Contains strategy identity, adapter, parameters, risk
policies, qualification certificate, and lineage. The bot validates this
package before every order.

**Verification Certificate** — The evidence artifact produced at
VERIFICATION_READY. Confirms research qualification is complete.

**Production Approval Package** — The complete evidence bundle produced at
PRODUCTION_CANDIDATE. Contains all stage reports, gate decisions, lineage,
and the signed Approved Strategy Package.

---

## Strategy Terms

**Phase-0 Gate** — The minimum statistical qualification criteria: n ≥ 50
AND net PF > 1.0 at BOTH standard AND 2× spread stress. Source: CLAUDE.md §2
and VERDICT_LOG.md. A single-spread PASS does not satisfy this gate.

**DEFERRED_REVALIDATION** — Current status of ST-A2. Not deleted, not
current, not approved. Cannot satisfy any qualification gate until it
re-enters at INTAKE and passes the full pipeline from zero. See CLAUDE.md §6.

**Trial ID** — A unique identifier for a single backtest run with fixed
parameters. Every parameter change requires a new trial ID. Trial IDs are
never reused. Source: VERDICT_LOG.md.

---

## Database Terms

**JSONL control records** — Current canonical control plane. Located at
`data/svos/`. Append-only. Target: migrated to PostgreSQL after acceptance
gate.

**PostgreSQL control DB** — Target canonical control plane. Alembic
migrations 001–003 applied. Authoritative for evidence and approvals after
cutover from JSONL.

**YAML catalog** — `config/strategy_catalog.yaml`. Read-only compatibility
projection. Never written by active lifecycle code. Never authoritative for
lifecycle state.

---

## AI and Documentation Terms

**Authoritative document** — A document with `Status: Authoritative` in its
header. Only these documents may be treated as prescriptive by AI agents.

**Documentation Authority Hierarchy** — The ordered list in
`DOC_AUTHORITY.md` defining which document wins on conflict. Level 1
(product) beats Level 2 (architecture), etc.

**Lifecycle vocabulary violation** — Use of a legacy phase number (e.g.,
"Phase 3") without explicitly citing the source document's numbering scheme.
Use canonical stage enum names instead.

---

*Terms are listed here because they have multiple conflicting usages in the*
*codebase. New terms should be added here before being used elsewhere.*
