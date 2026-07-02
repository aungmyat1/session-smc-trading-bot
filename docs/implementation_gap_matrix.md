# Implementation Gap Matrix

Date: 2026-07-02
Status: Draft — repository implementation gap matrix
Scope: Capture the highest-risk implementation gaps found during the repository consistency audit.

| Component | Current Status | Target State | Primary Gap | Priority |
|---|---|---|---|---|
| SVOS orchestration | Partial, duplicated | One canonical orchestrator | Parallel `svos/application/*` and legacy `research/svos/engine.py` paths | P1 |
| Strategy audit | Implemented twice | Single active Phase-0 engine | Legacy `strategy_audit/` engine coexists with active `strategy_validation/` | P3 |
| Strategy enhancement | Partial integration | Integrated AI enhancement stage | `strategy_validation/ai/*` not wired into the canonical application pipeline | P2 |
| Historical replay | Functional but fragmented | Unified replay engine | Multiple one-off replay scripts and duplicated metrics code | P1 |
| Backtest / validation gate | Functional but duplicated | Canonical, reusable gate library | Multiple PF/metrics implementations across `research/`, `pipeline/`, `svos/` | P1 |
| Robustness testing | Partial | All checks working | Call-site mismatch causes two robustness functions to downgrade to WARN | P1 |
| Virtual demo | Complete | Reuse simulator path | Offline demo uses a separate synthetic path instead of emulator reuse | P3 |
| Artifact packaging | Missing | Strategy package + checksum | No bundle assembler or import-time package verification | P1 |
| Production import path | Partial | Verified import of approved package | `bot.py` lacks artifact and catalog verification | P1 |
| Risk config loading | Partial | Config-driven limits at runtime | Strategy portfolio config not fully loaded; hardcoded defaults remain | P0 |
| Portfolio runner | Present | Deployable multi-strategy portfolio | `run_portfolio.py` exists but is not exercised by documented deployment units | P1 |
| Trade lifecycle | Partial | Full SL/TP/BE/partial-T target | key lifecycle hooks exist but are not wired in live path | P2 |
| Monitoring / alerting | Partial | End-to-end watchdog + heartbeat | Heartbeat/watchdog code not wired to deployed path | P2 |
| Emergency stop | Complete | Single reliable stop | Multiple surfaces duplicate the same state | P3 |
| One-position guard | Partial | Real-time per-symbol enforcement | Guard degrades without close-event propagation | P1 |
| Database topology | Partial | Two-node Postgres separation | Postgres cutover incomplete, schemas still mixed | P1 |
| Deployment topology | Partial | Two-node deployed research/production | Node split exists physically, but deployment metadata and service discovery are incomplete | P2 |
| Documentation traceability | Partial | Formal traceability matrix | Docs reference many components but do not map requirement → module → test → report consistently | P1 |
| Test integration coverage | Missing | Dedicated integration/regression suites | Empty integration/regression directories and no CI gate for full suite | P2 |
| Dashboard architecture | Partial | Unified dashboard deployment | Three independent UI surfaces; no single documented live-trading UI | P2 |
| Report producer mapping | Partial | Documented report pipeline | Report docs exist, but implementation-to-report traceability is sparse | P2 |

## Notes

- Priority definitions:
  - P0 — Critical operational gap that should be addressed immediately.
  - P1 — High-priority platform gap affecting consistency or safety.
  - P2 — Medium-priority implementation or documentation gap.
  - P3 — Lower-priority cleanup or duplication gap.

- This matrix is intentionally implementation-focused. It does not rate every documentation issue, but rather the gaps that affect the repository’s claimed architecture and the actual code.
