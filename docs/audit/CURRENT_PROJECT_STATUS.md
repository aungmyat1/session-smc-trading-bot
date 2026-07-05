# Current Project Status — Comprehensive Audit

Date: 2026-07-04
Status: Read-only audit synthesis — describes observed state, does not authorize any change
Scope: Whole-repository status snapshot, combining direct inspection with the existing
2026-07-01 → 07-03 audit corpus (`CURRENT_ARCHITECTURE.md`, `docs/project_readiness_assessment.md`,
`PROJECT_GAP_ANALYSIS.md`, `ARCHITECTURE_STABILIZATION_ROADMAP.md`,
`docs/architecture/production_svos_rollout_index.md` + linked docs, `docs/audit/*`), verified
against current code including uncommitted changes as of this date.
Companion documents: `OBJECTIVE_GAP_ANALYSIS.md`, `IMPLEMENTATION_MATRIX.md`,
`PRODUCTION_READINESS.md`, `TECHNICAL_DEBT.md`, `ROADMAP.md` (all in this directory).
Authority: informational only — does not supersede `docs/00_Project/DOC_AUTHORITY.md`.

---

## 1. Current Architecture Diagram

```
                    ┌─────────────────────────────────────────────────────────────┐
                    │  VPS 1 — auto-trade-vps (real, confirmed live)               │
                    │  Role: Production/execution host + control-plane Postgres    │
                    │                                                               │
                    │  ┌─────────────────────────────────────────────────────┐    │
                    │  │ ENTRYPOINTS (2 competing)                            │    │
                    │  │  • bot.py — LEGACY_RUNTIME_ENTRYPOINT=True, dormant   │    │
                    │  │  • scripts/run_st_a2_demo.py — LEGACY, still deployed,│    │
                    │  │    stronger recovery/governance wiring than canonical │    │
                    │  │  • scripts/run_portfolio.py — CANONICAL, weaker       │    │
                    │  │    recovery/governance wiring                         │    │
                    │  └──────────────────┬────────────────────────────────────┘    │
                    │                     ▼                                         │
                    │  ┌─────────────────────────────────────────────────────┐    │
                    │  │ production/engine/*  (RuntimeAuthority,               │    │
                    │  │   CanonicalExecutionPipeline, RiskFirewall,           │    │
                    │  │   OrderService/PositionService — built but UNUSED)    │    │
                    │  │ execution/*  (trade_manager.py — the REAL path,       │    │
                    │  │   mt5_connector.py, execution_state.py, demo_risk_    │    │
                    │  │   manager.py — record_result() NEVER CALLED)          │    │
                    │  │ core/portfolio_manager.py (record_close() NEVER      │    │
                    │  │   CALLED — one-per-symbol dedup degrades over a day) │    │
                    │  │ monitoring/ (Telegram alerts, TradeJournal, logs)     │    │
                    │  │ dashboard/  — 3 processes: app.py (Flask, SVOS+EVF+   │    │
                    │  │   legacy+React shell), live_app.py (Flask, own        │    │
                    │  │   systemd unit), status_server.py (FastAPI :8090,    │    │
                    │  │   the one deployed/audited live)                     │    │
                    │  └──────────────────┬────────────────────────────────────┘    │
                    │                     │ in-process import                       │
                    │                     ▼                                         │
                    │  ┌─────────────────────────────────────────────────────┐    │
                    │  │ svos/  — lifecycle, registry, governance, deployment, │    │
                    │  │  reports, api, monitoring, experiments                │    │
                    │  │  + svos/application/ (NEW pipeline.py orchestrator:   │    │
                    │  │    INTAKE→AUDIT→REPLAY→BACKTEST→ROBUSTNESS→          │    │
                    │  │    VIRTUAL_DEMO — no REFINEMENT phase)                │    │
                    │  │  + svos/adapters/llm/ (NEW, uncommitted — DeepSeek    │    │
                    │  │    adapter, disabled by default, NOT wired into       │    │
                    │  │    pipeline.py, zero test coverage)                   │    │
                    │  └──────────────────┬────────────────────────────────────┘    │
                    │                     │                                         │
                    │  ┌──────────────────▼────────────────────────────────────┐    │
                    │  │ Postgres `vmassit` (loopback 127.0.0.1:5432)          │    │
                    │  │ 12 schemas — PRODUCTION + RESEARCH MIXED, one host,   │    │
                    │  │ not yet cut over to VPS 2 per target topology         │    │
                    │  └─────────────────────────────────────────────────────┘    │
                    │                                                               │
                    │  ALSO ON DISK (legacy/duplicate, unretired):                  │
                    │  research/svos/engine.py + research/validation/engine.py     │
                    │  (second SVOS orchestrator, still edited as of 07-02)         │
                    └───────────────────────────┬───────────────────────────────────┘
                                                 │ (Tailscale — documented, not executed
                                                 │  as a data-transfer cutover)
                                                 ▼
                    ┌─────────────────────────────────────────────────────────────┐
                    │  VPS 2 — gcp-vm1 (real, confirmed reachable, underprovisioned)│
                    │  Docker + Postgres (`quant-postgres`), 955 MiB RAM/no swap —  │
                    │  below the 8GB gate for real research workloads.              │
                    │  Postgres port bound 0.0.0.0 on the live host despite a safe  │
                    │  127.0.0.1 default in the committed compose file — unfixed    │
                    │  exposure.                                                    │
                    └─────────────────────────────────────────────────────────────┘

     Broker: MetaAPI Cloud SDK → Vantage MT5 DEMO account only (real connectivity,
     confirmed live candle/balance data). Live-mode code paths exist at the client
     layer but are blocked at the CLI entrypoint, not yet at every layer (ADR-0012,
     open).

     Frontend: "New Dashborad/" — React 19 + Vite + TS SPA, active migration target,
     contains a 156 MB nested duplicate-of-itself directory that should be pruned.

     CI/CD: GitHub Actions — ci.yml (quality/tests/security/docs, 4-job required gate,
     but only ~28% of test files actually run in CI), strategy-release.yml (GCP-KMS
     signed release), deploy-production.yml (workflow_dispatch only, hardcodes
     LIVE_TRADING=false DEMO_ONLY=true into the remote command).
```

---

## 2. Major Systems Inventory

| System | Role | Status |
|---|---|---|
| **System 1 — SVOS** (`svos/`, `research/`, `strategy_audit/`, `strategy_validation/`, `historical_replay/`, `replay/`) | Strategy research, audit, replay, backtest, robustness, virtual demo | Research Ready, partially wired, two orchestrators coexist |
| **System 2 — Execution** (`production/`, `execution/`, `bot.py`, `scripts/run_portfolio.py`, `scripts/run_st_a2_demo.py`) | Demo-only broker execution via MetaAPI/Vantage | Demo Ready, real broker link, risk-feedback loop still open |
| **Dashboard layer** (`dashboard/`, `New Dashborad/`) | Operator visibility + control (emergency stop) | Demo Ready, 3 unconsolidated backends + 1 frontend migration in progress |
| **Data pipeline** (`data/`, `download_dukascopy.py`, `build_timeframes.py`, `extract_features.py`) | Historical FX data ingestion/features | Research Ready, manual-orchestration only |
| **Databases** (`db/control_plane.py`, `research_db/`) | Postgres control plane + DuckDB/Parquet research store | Demo Ready (Postgres), Research Ready (research_db); not node-separated per target topology |
| **CI/CD** (`.github/workflows/*`) | Quality/test/security/docs gates + signed release | Demo Ready, real gates, incomplete test-path coverage |
| **Governance/docs** (`docs/`, `docs/00_Project/DOC_AUTHORITY.md`, `docs/VERDICT_LOG.md`) | Lifecycle vocabulary, precedence, trial history | Research Ready mechanism, existing corpus not yet compliant |
| **LLM/Multi-agent adapter** (`svos/adapters/llm/`, `svos/application/refinement.py`) | Phase-1 AI-assisted strategy enhancement drafts | Research Ready (experimental), standalone, untested, not pipeline-wired |

---

## 3. Executive Summary

**Current maturity position:**

```
Prototype → Research Platform (largely here) → Validation Platform (partially here) → Production Ready
```

The platform is **solidly past prototype**. It has a real lifecycle/registry/governance core
(`svos/lifecycle/manager.py`, `svos/registry/service.py`), a genuine broker integration in demo
mode (MetaAPI/Vantage, confirmed live balance/candle data), a working (if fragmented) replay and
backtest gate matching the current tightened Phase-3 threshold, 152 test files with the full
suite now running clean-ish (1509 passed / 8 failed / 4 skipped — the previously-reported pandas
segfault blocking full-suite pytest is **resolved**, `pandas==2.3.3` not `3.0.4`), and — as of the
July 2 implementation wave — a substantially complete repo-side strategy packaging, signing
(including real GCP KMS), production import, and disabled-runtime staging pipeline that did not
exist as of the July 1 baseline.

It is **not yet a coherent Validation Platform or a trustworthy Production system**, for reasons
that are structural, not cosmetic:

1. **The risk-management feedback loop is still dead code.** `execution/demo_risk_manager.py`'s
   `record_result()` — the only function that updates `daily_loss_pct`/`consecutive_losses` from
   a real closed trade — has zero production callers. `core/portfolio_manager.record_close()` is
   the same story. A losing streak cannot trigger the documented halt logic today. This is the
   single most consequential open P0 (tracked as WS2 in `ARCHITECTURE_STABILIZATION_ROADMAP.md`,
   confirmed still open in this pass, not merely stale documentation).
2. **Two canonical-vs-legacy inversions exist in the execution path.** The "canonical" runner
   (`scripts/run_portfolio.py`) has *weaker* startup-recovery/governance wiring than the "legacy"
   one it's meant to supersede (`scripts/run_st_a2_demo.py`). A new `production/engine/orders.py`
   / `positions.py` idempotency layer was built (commit `e009d5f`) but is not actually used by the
   live loop — the real path is still `execution/trade_manager.py`.
3. **Two parallel SVOS pipeline orchestrators still coexist** (`svos/application/pipeline.py` vs.
   `research/svos/engine.py` + `research/validation/engine.py`) — and the legacy one was edited as
   recently as 07-02, after this exact duplication was first flagged. Neither has been retired.
4. **Documentation and root-report sprawl is severe and ungoverned outside `docs/`.** 643 `.md`
   files repository-wide; 20 root-level status/readiness/gap-analysis reports with zero
   cross-references between the three "audit generations" that produced them; a confirmed
   superseded-but-undeleted pair (`PROJECT_READINESS_SCORECARD.md` vs.
   `UPDATED_PROJECT_READINESS_SCORECARD.md`) that actively risks misleading a future reader.
   `docs/00_Project/DOC_AUTHORITY.md` governs the `docs/` tree well but does not mention root-level
   files at all.
5. **CI enforces real gates but on a narrow path.** Only ~28% of the 152 test files run in CI;
   `tests/svos/test_pipeline.py` (7 failures, a real VIRTUAL_DEMO evidence gap) is explicitly
   `--ignore`'d rather than fixed, and `tests/core` (where an unrelated real failure lives) is
   never run in CI at all.

**No strategy currently holds Production Approval, and none is close** — the tightened Phase-3
gate (`CLAUDE.md` §0.6/§7, effective 2026-07-01: n>200, net PF>1.25 at standard AND 2× stress,
Sharpe>1.2, MaxDD<15%) has zero passing strategies (`docs/VERDICT_LOG.md`: ST-A, ST-A2, EXP05,
T27–T29 all FAIL or DEFERRED_REVALIDATION). Meanwhile `config/strategy_portfolio.yaml` declares
five strategies but only one process (`SMCOrderBlockFVGSession` at lifecycle stage `INTAKE`) is
actually deployed live-demo — a tracked, documented governance gap, not a contradiction to
silently resolve.

**What changed materially since the last full audit (2026-07-01):** the July 2 implementation
wave closed the packaging/signing/import/verification gaps that the 07-01 assessment flagged as
entirely missing (see `docs/architecture/production_svos_rollout_index.md`), and this pass found
the pandas segfault and the robustness-engine signature mismatch both silently fixed as well.
Real remaining gaps are now concentrated in **runtime risk feedback, execution-path
consolidation, and documentation governance** rather than "missing capability."

See `IMPLEMENTATION_MATRIX.md` for the full 38-subsystem breakdown, `PRODUCTION_READINESS.md` for
readiness ratings, `TECHNICAL_DEBT.md` for the sprawl/duplication inventory, and `ROADMAP.md` for
the phased plan to close these gaps.
