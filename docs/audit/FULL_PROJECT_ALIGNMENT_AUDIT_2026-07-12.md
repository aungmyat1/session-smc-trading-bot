# Full Project Alignment Audit

Date: 2026-07-12
Date requested: 2026-07-12
Audit snapshot: 2026-07-13 UTC
Reviewed/Updated: 2026-07-13
Owner: Platform Owner
Author: Codex independent principal auditor/program manager
Status: Audit and planning only. No code/runtime fix implemented.
Authority: Level 8 evidence. Does not supersede `docs/00_Project/DOC_AUTHORITY.md`.

## 1. Executive Verdict

The repository is directionally aligned with the owner's objective, but it is not ready for broker-demo qualification or live-capital authorization.

System 2 must be finished first, with live trading disabled. The highest-risk blocker is not strategy logic; it is authority drift: the catalog says no strategy is approved/current, while demo configuration still permits ST-A2 execution, and the currently stopped runtime has recent evidence of branch/config drift. The fastest safe path is to stabilize one disabled/demo System 2 runtime path, close the broker identity/cost documentation drift, prove package-first startup and recovery with synthetic or fixture packages, then resume System 1 strategy qualification.

Current verdict: **NO LIVE TRADING, NO PR #44 WHOLESALE MERGE, NO STRATEGY QUALIFICATION CLAIMS.** Proceed only with targeted System 2 stabilization and governance alignment.

## 2. Verified Commit and Runtime Snapshot

Repository:

| Item | Verified value |
|---|---|
| Branch | `audit/p0-vtmarkets-alignment-20260713-clean` (clean replacement branch created from `origin/main`) |
| Worktree | clean branch reconstruction; commit 1 contains this report only, commit 2 contains broker metadata alignment only |
| Local HEAD | `98e7cda8f7bff5af948c73b34b83489110727f65` |
| `origin/main` | `6955d27c5e679d680a27c344069a38694bc41f5d` |
| Expected GitHub main head | verified: `6955d27` |
| Merge base | `6955d27c5e679d680a27c344069a38694bc41f5d` |
| Clean-branch base relationship before reconstruction commits | `0 ahead / 0 behind` at `6955d27` |
| Preserved source commit | `98e7cda refactor: Update references from Vantage to VT Markets in documentation and code` on backup/source branch `audit/p0-vtmarkets-alignment-20260713` |
| `3c91bd1` status | commit object is not an ancestor of local `HEAD` or `origin/main`; the same System 2 Gap Closure/RCA work is represented on `origin/main` by merged/squashed commit `6955d27` |
| Open PRs | one open PR: #44, `claude/st-b1-strategy-engine`, merge state `BEHIND`, updated 2026-07-13T06:32:51Z, CI green, CodeRabbit comments still actionable |

Runtime:

| Item | Verified value |
|---|---|
| `smc-demo-runner.service` | `inactive`, `disabled` |
| Root disk | `/dev/root` 48G total, 43G used, 5.1G free, 90% used |
| Memory | 3.8Gi total, 718Mi free at sample time |
| Broker/runtime access | only local read-only service status was available in this pass |
| Broker writes | none performed |

## 3. Objective Alignment Score

| Subsystem | Score | Reason |
|---|---:|---|
| System 2 safety posture | 65/100 | Live disabled and demo-only defaults exist, but runner is stopped and config/governance authority is still unresolved. |
| System 2 deterministic execution | 55/100 | Good pieces exist: `TradeManager`, duplicate suppression, startup recovery, `CanonicalExecutionPipeline`; they are split across deployed/legacy/canonical paths. |
| Strategy package handoff | 60/100 | ADR-0002/0003/0004 define the right target; actual runners still include compatibility and YAML/adapters paths. |
| Broker identity/cost alignment | 50/100 | `config/broker_symbol_mapping.yaml` correctly maps VT Markets demo and XAUUSD to `XAUUSD-VIP`; many active docs/config comments still say Vantage. |
| System 1/SVOS qualification | 45/100 | Lifecycle authority exists and Production Approval is blocked by design; current strategy evidence is legacy or blocked. |
| CI/security | 60/100 | PR #44 CI is green and required gate exists; local scanner tools unavailable and repo still contains broad examples/log docs requiring redacted review. |
| Runtime operations | 35/100 | Service stopped/disabled; disk at 90%; health-check failures downstream of stopped runner are documented. |

## 4. Authority Conflict Matrix

| Conflict | Higher authority / evidence | Conflicting lower or active surface | Decision needed |
|---|---|---|---|
| VT Markets vs Vantage | `AGENTS.md`, `CLAUDE.md`, `docs/VERDICT_LOG.md`, `config/broker_symbol_mapping.yaml` identify VT Markets MT5 demo through MetaAPI. | `docs/svos/STRATEGY_ENGINEERING_PLATFORM_IMPLEMENTATION_PLAN.md`, `SYSTEM2_MASTER_PLAN.md`, `config/demo.yaml`, `config/costs.json`, `VANTAGE_DEMO_CONNECTION_CHECKLIST.md`, class/file names still use Vantage. | Rename docs/config terminology carefully after caller map; do not rename compatibility env vars until all callers are mapped. |
| Production Approval vs Demo Execution Authorization | Root objective says real-capital only after strategy qualification, execution qualification, broker-demo evidence, explicit owner authorization. | Catalog has no current/approved strategy, yet `strategy_portfolio.yaml` enables ST-A2 demo as a tracked exception. | Owner must choose whether ST-A2 demo carve-out remains valid or whether all broker-demo execution requires separate Demo Execution Authorization. |
| Offline Virtual Demo vs online broker demo | `AGENTS.md` and current repo instructions define Phase 5 Virtual Demo as offline/no broker. | Several older docs use "Virtual Demo" for live broker-demo or paper observation. | Standardize terms: Offline Virtual Demo, Broker Demo, Paper Trading, Live Capital. |
| Current gate | `AGENTS.md` and `docs/VERDICT_LOG.md` effective 2026-07-01 gate: n > 200, PF > 1.25, Sharpe > 1.2, MaxDD < 15% at standard and 2x. | Implementation plan still states n >= 50/PF > 1.0 in Stage 4; older specs and reports repeat prior gate. | Align active docs to current gate, preserving older verdict rows as historical. |
| ST-A2 lifecycle vs demo enabled | `config/strategy_catalog.yaml`: ST-A2 `DEFERRED_REVALIDATION`, `approved: false`, `deployment_target: null`. | `config/strategy_portfolio.yaml`: ST-A2 `enabled: true`, `execution_mode: demo`. | Keep as explicit exception only if owner authorizes; otherwise block broker-demo execution until Demo Execution Authorization exists. |
| One runner vs alternatives | ADR-0003 says `RuntimeAuthority` is single runtime authority; current instructions call `scripts/run_st_a2_demo.py` intended deployed runner. | `scripts/run_portfolio.py`, `run_d2_e3_demo.py`, `bot.py`, adaptive/demo paths remain executable or semi-executable. | Choose one System 2 command path for readiness; block or demote all others. |
| Healthy runtime vs outage evidence | Local `systemctl`: inactive/disabled; RCA says stopped/disabled with broker credential/server blocker and disk pressure. | Older status docs claim demo running or healthy. | Runtime claims must be timestamped and treated stale unless reverified. |

## 5. Actual System 1 and System 2 Architecture

System 1 (SVOS/research):

- Owns strategy intake, audit, replay, backtest/statistical validation, robustness, offline Virtual Demo, evidence, lifecycle transitions, and package approval records.
- Key implementation: `svos/lifecycle/manager.py`, `svos/lifecycle/authority.py`, `svos/application/*`, `svos/registry/service.py`.
- Production Approval is intentionally unreachable during platform construction: `svos/lifecycle/manager.py` removes `VIRTUAL_DEMO -> PRODUCTION_APPROVAL`, and `svos/lifecycle/authority.py` blocks Production Approval transitions.

System 2 (execution):

- Target authority is ADR-0002/0003/0004: signed `strategy-package/v2`, `RuntimeAuthority`, `CanonicalExecutionPipeline`.
- Actual broker-write stack is still centered on `scripts/run_st_a2_demo.py` -> `execution/trade_manager.py` -> `execution/vantage_demo_executor.py` -> `execution/mt5_connector.py` -> MetaAPI.
- `DEMO_ONLY=true` blocks writes inside `VantageDemoExecutor`; `LIVE_TRADING` remains blocked by policy and runner behavior.
- The runtime service is currently stopped/disabled, so no controlled-readiness evidence is current.

Real order-path checks:

| Required property | Current finding |
|---|---|
| One execution authority | Partial. Target authority exists, but legacy/canonical paths coexist. |
| Fail-closed package verification | Partial. ADR path exists; ST-A2 runner still loads strategy/config directly. |
| Risk firewall before every order | Partial. Risk checks exist in runner/pipeline, but duplicate paths require consolidation. |
| Emergency stop before/during execution | Present in deployed runner lineage; must be proven in the final canonical path. |
| Account and per-symbol limits | Present in portfolio/risk layers; needs broker-truth validation. |
| Deterministic idempotency keys | Present in `execution_state.py` / `TradeManager` duplicate suppression. |
| Durable intent before broker write | Present in `TradeManager.create_record()` before `_place_order_with_retry()`. |
| Startup/periodic reconciliation | Present in `startup_recovery.py` and `run_st_a2_demo.py`; must be part of canonical runtime acceptance. |
| Close-result feedback | Implemented in runner lineage; still needs controlled runtime evidence. |
| No bypass path | Not yet. Multiple scripts and execution abstractions remain. |

## 6. Duplicate, Dead, and Bypass Inventory

| Component | Classification | Broker write capable | Recommendation |
|---|---|---:|---|
| `scripts/run_st_a2_demo.py` | Intended deployed compatibility runner | Yes when `DEMO_ONLY=false` | Keep as current recovery target only until canonical System 2 path absorbs its proven safety wiring. |
| `scripts/run_portfolio.py` | Canonical-ish but historically undeployed/alternative | Yes when wired | Do not deploy until package-first startup, emergency stop, recovery, and risk feedback match or exceed ST-A2 runner. |
| `scripts/run_d2_e3_demo.py` | Research/demo-specific runner | Yes when demo flag permits | Block for System 2 readiness; research-only until owner decision. |
| `bot.py` | Legacy broker bot | Likely yes | Keep blocked/dead unless a separate retirement review proves no callers. |
| `execution/order_manager.py`, `trade_manager.py`, `vantage_demo_executor.py` | Multiple execution contracts | Yes | Normalize after System 2 critical path; do not redesign first. |
| `production/engine/*` | Target canonical execution/pipeline | Adapter-dependent | Promote only through package-first runtime acceptance. |
| `adaptive/*` demo/shadow stack | Experimental shared/research surface | Some paths | Keep shadow/research-only; no broker authorization. |
| Dashboard mutation routes | Mixed operational control | Can affect runtime state | Require uniform auth and CONFIRM tokens before broker-demo readiness. |

## 7. Broker and Cost-Model Alignment

Verified:

- `config/broker_symbol_mapping.yaml` exists.
- Provider is MetaAPI.
- VT Markets demo mapping exists.
- Canonical `XAUUSD` maps to broker symbol `XAUUSD-VIP`.
- `config/costs.json` includes `vtmarkets_demo_measured` and leaves it inactive/candidate-only.
- Old `vantage_measured` remains present and must not receive VT Markets observations.
- `active_profile` remains `PLACEHOLDER_vt_markets_assumption`.
- `reports/metaapi_cost_check.json` is marked `SNAPSHOT_ONLY_NOT_FOR_BACKTEST_PROFILE` and `DEMO_ACCOUNT_EVIDENCE_ONLY`; local account metadata is redacted in the working tree.

Blockers:

- `config/demo.yaml` still says `broker: vantage_mt5`.
- `config/costs.json` still contains stale Vantage wording in comments/reference profile names; the active profile itself remains the VT Markets placeholder.
- Many active docs still contain Vantage wording, including operational and SVOS implementation documents.
- Snapshot/demo cost reports must remain evidence-only and must not become backtest profiles without controlled measurement windows and owner approval.

## 8. Strategy and Governance Status

Verified:

- `config/strategy_catalog.yaml` has `current_strategy: null`.
- No catalog strategy is approved/current.
- ST-A2 is `DEFERRED_REVALIDATION`, unapproved, and has `deployment_target: null`.
- ST-A2 legacy evidence is preserved but cannot satisfy the current 2026-07-01 gate.
- SMC-LSS is blocked on missing real data; synthetic tests are not qualification evidence.
- PR #44 adds ST-B1 research and failed/blocked validation artifacts, but should not be merged as a mixed PR.

Circular policy:

The current policy language risks requiring Production Approval before broker demo, while also requiring 30+ day broker-demo evidence before final live authorization. The non-circular model should be:

1. **Strategy Qualification Package**: System 1 evidence that a strategy passed replay/backtest/statistical/robustness/offline Virtual Demo gates.
2. **Demo Execution Authorization**: System 2 authorization to run a qualified package on VT Markets demo under controlled limits.
3. **Live Capital Authorization**: owner-only authorization after qualified strategy, execution readiness, 30+ day stable broker-demo evidence, and explicit token.

This audit does not implement that model; it is an owner decision.

## 9. Security and Privacy Findings

Scanner status:

- `python -m pip_audit ...` failed because `python` is absent.
- `python3 -m pip_audit ...` failed because `pip_audit` is not installed.
- `python3 -m bandit ...` failed because `bandit` is not installed.
- PR #44 latest CI reports `Security and dependencies` success, but local audit could not independently reproduce it.

Redacted findings:

| Severity | Finding |
|---|---|
| P0 | `reports/metaapi_cost_check.json` contained real broker-account metadata in a generated snapshot report. The working tree now redacts the account identifier; do not commit the generated report unless sanitized and explicitly required. |
| P1 | UUID/account-like metadata exists in documentation/report paths: `docs/VANTAGE_DEMO_CONNECTION_CHECKLIST.md`, `docs/SPREAD_CAPTURE_PLAN.md`, `docs/audit/function_inventory.md`, `docs/audit/SYSTEM2_BROKER_RECOVERY_REPORT.md`, `docs/audit/SYSTEM2_RUNTIME_OUTAGE_RCA.md`, `docs/OPS02_ACTIVATION_CHECKLIST.md`, `reports/ST_A2_TRADE_AUTOPSY.md`, `reports/dashboard_strategies.json`, and dashboard prototype READMEs. Treat as documentation/report metadata, not credentials, but redact before public output. |
| P1 | `docs/operations/risk-register.md` tracks `SVOS_OPERATOR_TOKEN` exposure to an unrelated health-check service as open. |
| P2 | Repository-local secret-scan helper reports one finding in `scripts/db_preflight.py`; manual review classifies it as a false positive on error-token terminology, not a credential. |
| P2 | Git history contains many broker/auth-related commits; a full history scanner was not available locally. |
| P2 | CI's tracked-secret regex only catches simple quoted assignments in selected file types; broaden with a real secret scanner. |

No unredacted secret values are included in this report. The local `.env` exists and was not opened.

## 10. CI and Test Health

PR #44 latest status:

- Quality and architecture: success.
- Unit tests: success.
- Integration tests: success.
- Security and dependencies: success.
- Documentation and package contracts: success.
- Required CI: success.
- CodeRabbit status: success, but CodeRabbit review comments remain actionable.

Main CI review:

- `ci.yml` has a required aggregate gate and no visible `continue-on-error` in the current main workflow gate.
- Required checks cover architecture, unit/integration tests, docs/package, dependency audit, static security scan.
- Local environment cannot run the same security tools without installing dependencies.

Test risk:

- Some tests and docs still inspect text/governance claims; behavior tests exist for execution pieces, but end-to-end controlled runtime evidence is absent while the service is stopped.

## 11. PR #44 Disposition

PR #44 must not be merged wholesale.

File classification:

| Class | Files |
|---|---|
| A. System 2 security/operational fix | `.github/workflows/*`, `dashboard/rbac.py`, `dashboard/status_server.py`, `deploy/gcp-vm1/systemd/vps-health-check.service`, `execution/operations_recorder.py`, `execution/validation_metrics.py`, `execution/validation_session.py`, `scripts/vps_health_check.sh`, `tests/test_system2_phase1_safety.py` |
| B. Documentation/governance alignment | `SYSTEM2_MASTER_PLAN.md`, `docs/00_Project/TWO_SYSTEM_ARCHITECTURE_TRUTH.md`, `docs/architecture/*`, `docs/index.md`, `docs/operations/*`, `docs/systems/system2/*`, `scripts/check_governance_doc_claims.py` |
| C. ST-B1/System 1 research | `config/strategies/ST-B1_v1.yaml`, `config/research_queue.yaml`, `config/strategy_catalog.yaml`, `config/strategy_portfolio.yaml`, `docs/VERDICT_LOG.md`, `reports/st_b1_*`, `scripts/backtest_st_b1.py`, `strategies/st_b1_*`, `strategies/adapters/st_b1_adapter.py`, `svos/application/adapter_dispatch.py`, `tests/strategies/test_st_b1_*` |
| D. Unrelated/generated | `smc_trading_checklist_accurate.html` and any generated report artifacts not needed for immutable verdict evidence |

Unresolved review themes verified from PR metadata:

- ST-B1 artifact immutability/run-scoped paths.
- ST-B1 lifecycle/catalog state and failure persistence.
- ST-B1 session/open-position logic and tests.
- System 2 auth invalid-credential tests.
- Health-check secret exposure and stale-tick threshold semantics.
- Governance-doc checker coverage.
- Duplicate System 2 planning docs.
- Cloudflare challenge script in HTML checklist.

Recommended split:

1. Cherry-pick only A-class System 2 auth/health fixes after review comments are resolved.
2. Separately land B-class documentation alignment after authority conflicts are settled.
3. Keep C-class ST-B1 research on a separate System 1 branch; do not mix with System 2 readiness.
4. Drop or quarantine D-class generated/unrelated artifacts unless explicitly required.

## 12. P0-P3 Findings

| Rank | Finding | Objective contribution | Owner | Dependencies | Acceptance evidence | Rollback | Files/components | Parallel |
|---|---|---|---|---|---|---|---|---|
| P0 | Live trading must remain disabled; no strategy has approval. | Prevent unauthorized capital risk. | Human owner for any future change; agent enforces no-op. | None. | `LIVE_TRADING=false`, `DEMO_ONLY=true`, no live adapter/authorization. | Revert any live-enabling change; stop services. | `.env`, workflows, runners, `VantageDemoExecutor`. | Yes |
| P0 | Resolve ST-A2 demo carve-out vs catalog authority before broker-demo qualification. | Prevent runtime policy contradiction. | Human owner decision; agent documents/implements after approval. | Authority model decision. | Written decision: keep carve-out as Demo Execution Authorization or block it. | Return to stopped/disabled demo runtime. | `config/strategy_catalog.yaml`, `config/strategy_portfolio.yaml`, docs. | No |
| P0 | Runtime is stopped/disabled and disk is 90%. | System 2 cannot be qualified while down/degraded. | Human owner for service state; agent can prepare checks. | Broker credential/server fix, disk cleanup approval. | Active service with 0 restart growth, healthy tick/broker status, disk below threshold. | Stop/disable service. | systemd, logs, MetaAPI config. | Partial |
| P1 | Establish one canonical System 2 runtime path. | Finish safe deterministic execution platform first. | Agent after owner picks path. | P0 authority decision. | One entrypoint, one systemd unit, bypass scripts blocked or documented non-authoritative. | Restore previous stopped runner. | `scripts/run_st_a2_demo.py`, `scripts/run_portfolio.py`, `production/engine`. | No |
| P1 | Package-first startup must be proven in the selected runtime. | Prevent YAML/config bypass of SVOS approval. | Agent. | Runtime path decision. | Valid v2 fixture starts; invalid/expired/revoked/mismatched package fails before broker connect. | Revert runtime adapter change. | ADR-0002/0003 code, runtime command. | Partial |
| P1 | Broker identity and cost docs/config must align to VT Markets demo. | Avoid false cost evidence and wrong broker provenance. | Agent. | Caller map for env vars/names. | No active doc claims Vantage as current broker; compatibility names documented. | Revert doc-only rename. | `docs/*`, `config/costs.json`, `config/demo.yaml`. | Yes |
| P1 | PR #44 must be split. | Avoid merging research, ops, and generated artifacts as one risk bundle. | Human owner for PR decision; agent can cherry-pick. | Review comments resolved. | Smaller PRs with targeted CI and no unresolved P0/P1 comments. | Close/supersede split PRs. | PR #44 files. | Yes |
| P2 | Controlled runtime evidence must cover emergency stop, recovery, idempotency, close feedback, and limits. | Prove System 2 readiness before System 1 resumes. | Agent with owner-approved runtime start. | P0/P1 complete. | 24h or defined controlled run logs, no critical execution failures. | Stop service and retain logs. | `execution/*`, `production/engine/*`, systemd. | Partial |
| P2 | Secret scanning must be reproducible locally and in CI. | Protect credentials and account identity. | Agent. | Tool availability. | `gitleaks` or equivalent scan over working tree/history with redacted report. | Remove scanner config if noisy, keep CI blocked until fixed. | `.github/workflows/ci.yml`, scanner config. | Yes |
| P2 | Dashboard/control mutations need uniform auth and CONFIRM tokens. | Prevent operational bypass. | Agent. | Runtime/control API inventory. | Invalid auth tests and confirm-token tests pass for every mutation. | Revert route changes. | `dashboard/*`, `execution/control_plane.py`. | Yes |
| P3 | Retire or archive duplicate runners/contracts. | Reduce future drift. | Agent. | System 2 canonical path stable. | No undocumented broker-write-capable alternatives. | Restore from git if needed. | legacy scripts/execution abstractions. | Yes |
| P3 | Resume System 1 qualification only after System 2 readiness. | Align with owner objective. | Human supplies strategy; agent runs pipeline. | System 2 controlled-readiness PASS. | New trial pre-registered; current gate evidence net of fees. | Mark trial FAIL/BLOCKED, no parameter tuning. | `docs/VERDICT_LOG.md`, `svos/*`. | No |

## 13. Fastest Critical-Path Roadmap

1. Freeze safety: verify `LIVE_TRADING=false`, `DEMO_ONLY=true`, service remains stopped unless owner authorizes controlled demo recovery.
2. Owner decision: define the three-artifact model and decide whether ST-A2 demo carve-out is allowed as temporary Demo Execution Authorization.
3. Clear runtime prerequisites: disk below operational threshold, MetaAPI/VT Markets demo metadata verified read-only, broker symbol mapping confirmed.
4. Select one System 2 runner path and block/demote alternatives.
5. Prove package-first startup and fail-closed invalid package behavior without broker writes.
6. Run controlled System 2 readiness with synthetic/fixture package: emergency stop, recovery, idempotency, risk limits, reconciliation, dashboard status.
7. Split PR #44: land only System 2 fixes needed for readiness; keep ST-B1 research separate.
8. After System 2 readiness, resume System 1 with an externally supplied strategy, pre-register the trial, and apply current net-of-fees gates.
9. Only after qualification and broker-demo evidence, prepare owner-only Live Capital Authorization package.

## 14. Owner-Only Action List

- Authorize or reject the ST-A2 demo carve-out as a temporary Demo Execution Authorization.
- Approve any service start/restart/enable action.
- Confirm broker credentials/server profile changes outside the repo.
- Authorize any order placement, close, or modify operation using exact CONFIRM tokens.
- Authorize live trading only with `CONFIRM-LIVE-ON` after all gates pass.
- Decide whether PR #44 should be split, closed, or retained as a research-only branch.

## 15. Do Not Do Yet

- Do not enable live trading.
- Do not restart or enable `smc-demo-runner.service` without explicit owner approval.
- Do not merge PR #44 wholesale.
- Do not tune strategy parameters or rerun old immutable trials.
- Do not use synthetic tests as qualification evidence.
- Do not write VT Markets demo measurements into `vantage_measured`.
- Do not activate `vtmarkets_demo_measured` from a short snapshot.
- Do not rename compatibility env vars until all callers are mapped.
- Do not start new System 1 strategy work before System 2 controlled-readiness is proven.

## 16. Evidence and Commands Used

Commands run, all read-only except creation of this report:

- `sed -n ... pasted-text.txt`
- `sed -n ... docs/00_Project/DOC_AUTHORITY.md`
- `sed -n ... docs/svos/STRATEGY_ENGINEERING_PLATFORM_IMPLEMENTATION_PLAN.md`
- `sed -n ... docs/VERDICT_LOG.md`
- `git status --short --branch`
- `git fetch --prune`
- `git rev-parse HEAD`
- `git rev-parse origin/main`
- `git log --oneline --decorate --graph --max-count=30 --all`
- `git branch -vv --all`
- `gh pr list --state open --json ...`
- `gh pr view 44 --json ...`
- `gh pr diff 44 --name-only`
- `find . -maxdepth 3 ...`
- `find docs -maxdepth 4 ...`
- `sed -n ... config/strategy_catalog.yaml config/strategy_portfolio.yaml config/demo.yaml`
- `sed -n ... .github/workflows/*.yml`
- `sed -n ... scripts/run_st_a2_demo.py execution/trade_manager.py execution/governance_guard.py execution/control_plane.py execution/startup_recovery.py`
- `sed -n ... docs/00_Project/TWO_SYSTEM_ARCHITECTURE_TRUTH.md SYSTEM2_MASTER_PLAN.md docs/audit/SYSTEM2_RUNTIME_OUTAGE_RCA.md`
- `sed -n ... docs/svos/ADR-0002... ADR-0003... ADR-0004...`
- `rg -n ... broker/auth/governance terms`
- `git grep -nEI ...` with output redacted/truncated
- `git log --all --oneline -G ...`
- `systemctl is-active smc-demo-runner.service`
- `systemctl is-enabled smc-demo-runner.service`
- `df -h /`
- `free -h`
- `python -m pip_audit ...` (failed: `python` not found)
- `python3 -m pip_audit ...` (failed: module not installed)
- `python3 -m bandit ...` (failed: module not installed)

Key source files inspected:

- `docs/00_Project/DOC_AUTHORITY.md`
- `docs/00_Project/TWO_SYSTEM_ARCHITECTURE_TRUTH.md`
- `docs/svos/STRATEGY_ENGINEERING_PLATFORM_IMPLEMENTATION_PLAN.md`
- `docs/VERDICT_LOG.md`
- `SYSTEM2_MASTER_PLAN.md`
- `docs/audit/SYSTEM2_RUNTIME_OUTAGE_RCA.md`
- `docs/svos/ADR-0002-CANONICAL-STRATEGY-PACKAGE.md`
- `docs/svos/ADR-0003-SINGLE-RUNTIME-AUTHORITY.md`
- `docs/svos/ADR-0004-CANONICAL-EXECUTION-PIPELINE.md`
- `config/strategy_catalog.yaml`
- `config/strategy_portfolio.yaml`
- `config/broker_symbol_mapping.yaml`
- `config/demo.yaml`
- `.github/workflows/ci.yml`
- `scripts/run_st_a2_demo.py`
- `execution/trade_manager.py`
- `execution/vantage_demo_executor.py`
- `execution/startup_recovery.py`
- `execution/governance_guard.py`

## 17. Unknown and Unverified Items

- Exact current MetaAPI account broker/server metadata was not re-queried in this pass.
- VPS shell history/deploy mechanism that placed prior branch code on the runtime host remains unknown.
- Full GitHub branch protection settings were not available from local CLI evidence.
- Full secret scan across history was not performed because scanner tools were unavailable.
- Current broker credential validity and server.dat status remain unverified.
- Runtime dashboard health was not exercised.
- No order path was tested against broker demo in this audit.
- No tests were run beyond read-only CI/status inspection.
