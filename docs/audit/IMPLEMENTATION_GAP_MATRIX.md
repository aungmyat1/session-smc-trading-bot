# Implementation Gap Matrix

## Overview

This matrix enumerates the required platform capabilities, marks their implementation status, and identifies coverage for tests, documentation, dashboard visibility, and deploy readiness.

Legend:
- ✅ Implemented
- ⚠️ Partial / fragmented
- ❌ Missing

## Capability Matrix

| Capability | Status | Tested | Documented | Dashboard | Priority |
|---|---|---|---|---|---|
| Strategy intake API / spec validation | ✅ | ✅ | ✅ | ⚠️ | High |
| Audit stage engine | ✅ | ✅ | ✅ | ⚠️ | High |
| Historical replay validation | ✅ | ✅ | ✅ | ⚠️ | High |
| Backtest gate evaluation | ✅ | ✅ | ✅ | ⚠️ | High |
| Robustness validation | ✅ | ✅ | ✅ | ⚠️ | High |
| Virtual demo simulation | ✅ | ✅ | ✅ | ⚠️ | High |
| Approval package builder | ✅ | ✅ | ✅ | ❌ | High |
| Strategy lifecycle registry | ✅ | ✅ | ✅ | ⚠️ | High |
| Strategy catalog / portfolio YAML | ✅ | ⚠️ | ✅ | ✅ | Medium |
| Strategy promotion / governance control | ⚠️ | ⚠️ | ⚠️ | ⚠️ | High |
| Report indexing and artifact store | ✅ | ⚠️ | ✅ | ✅ | Medium |
| Dashboard control-plane API | ✅ | ⚠️ | ⚠️ | ✅ | Medium |
| Emergency stop / control state | ✅ | ⚠️ | ⚠️ | ✅ | Medium |
| Postgres control plane deployment | ✅ | ⚠️ | ✅ | ❌ | Medium |
| Demo runtime runner | ⚠️ | ⚠️ | ⚠️ | ⚠️ | High |
| Strategy portfolio live execution | ⚠️ | ❌ | ⚠️ | ⚠️ | High |
| Data ingestion and historical dataset management | ⚠️ | ⚠️ | ⚠️ | ❌ | Medium |
| Approval signature validation | ✅ | ✅ | ✅ | ❌ | Medium |
| Pipeline orchestration service | ✅ | ✅ | ✅ | ⚠️ | High |
| CV/ALPHA separation of research vs production nodes | ⚠️ | ❌ | ✅ | ❌ | Medium |
| Policy gate enforcement (confirm tokens) | ⚠️ | ❌ | ⚠️ | ⚠️ | High |
| Live trade disable safety guard | ✅ | ✅ | ✅ | ❌ | High |
| Report generation endpoints | ✅ | ⚠️ | ⚠️ | ✅ | Medium |
| Runbook / docs drift checks | ⚠️ | ❌ | ⚠️ | ❌ | Low |

## Notes

- `Strategy promotion / governance control` is partially implemented in `svos/governance` and `svos/lifecycle`, but dashboard and actual catalog-driven promotion logic are not fully integrated.
- `Demo runtime runner` is fragmented between `scripts/run_st_a2_demo.py` and `scripts/run_portfolio.py`. The portfolio runner uses YAML configuration but falls back to hardcoded paths and strategy logic.
- `Strategy portfolio live execution` appears in `config/strategy_portfolio.yaml`, but there is no confirmed fully integrated deployment path from YAML to a running demo with the governance registry.
- `Policy gate enforcement` is present in dashboard APIs and control state, but the `CONFIRM` token flow is not consistently wired through the actual execution and SVOS promotion subsystems.
- `CV/ALPHA separation` is documented in `docs/svos/DEPLOYMENT_TOPOLOGY.md` and `deploy/gcp-vm1/docker-compose.yml`, yet the repository retains a monolithic runnable layout.
- `Runbook / docs drift checks` are partly addressed by repo scripts, but the broken link and doc header issues in `docs/` indicate this is not a completed readiness control.
