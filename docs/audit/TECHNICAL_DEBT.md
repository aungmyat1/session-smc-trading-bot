# Technical Debt Audit

Date: 2026-07-04
Status: Read-only audit finding
Companion: `CURRENT_PROJECT_STATUS.md`, `IMPLEMENTATION_MATRIX.md`

---

## 1. Root-level report sprawl

17 root-level `.md` files are all git-tracked (committed clutter, not scratch output), clustering
into three unlinked "audit generations" written within days of each other:

| Gen | Date | Files |
|---|---|---|
| 0 | 2026-06-20 | `LOOKAHEAD_AUDIT.md` (narrow, orphaned, harmless) |
| 1 | 2026-07-01/02 | `CURRENT_ARCHITECTURE.md`, `REPOSITORY_CONSISTENCY_REPORT.md`, `IMPLEMENTATION_GAP_MATRIX.md`, `PROJECT_READINESS_SCORECARD.md`, `END_TO_END_VALIDATION_REPORT.md`, `WORKFLOW_VALIDATION_REPORT.md`, `CI_READINESS_REPORT.md`, `DEMO_READINESS_BACKLOG.md` |
| 2 | 2026-07-03 | `ADR_0002/3/4_IMPLEMENTATION_REPORT.md`, `DEMO_RUNTIME_INTEGRATION_REPORT.md`, `DEMO_SMOKE_TEST_SPRINT.md`, `UPDATED_PROJECT_READINESS_SCORECARD.md`, `AGENTS.md` |
| 3 | 2026-07-03 | `ARCHITECTURE_STABILIZATION_ROADMAP.md`, `PROJECT_GAP_ANALYSIS.md` |

None of these files reference each other (`grep` across them for each other's names returns
nothing). **`docs/00_Project/DOC_AUTHORITY.md`'s authority table lists only `docs/`-tree paths —
zero of these 17 root files are named anywhere in it.** Root-level reports sit entirely outside
documentation governance.

**Confirmed active risk**: `PROJECT_READINESS_SCORECARD.md` (emoji bands, e.g. "Demo Runtime ⚠️
Partial") is superseded by `UPDATED_PROJECT_READINESS_SCORECARD.md` (numeric %, most items 100%,
"Demo Runtime Integration Sprint: PASS") — but neither file has a superseded/status pointer to the
other. A reader opening the alphabetically-earlier file gets a materially stale picture.

**Verdict**: needs owner decision. Minimum action: delete or archive `PROJECT_READINESS_SCORECARD.md`
now. Longer-term: add a "Root Reports" tier to `DOC_AUTHORITY.md` with explicit supersession
ordering, or move Gen 0/1 into `docs/Archive/` now that Gen 2/3 supersede them, keeping only the
latest scorecard + `AGENTS.md` + `ARCHITECTURE_STABILIZATION_ROADMAP.md` + `PROJECT_GAP_ANALYSIS.md`
live at root.

---

## 2. Documentation sprawl (whole-repo scale)

643 total `.md` files repository-wide: 259 under `docs/`, 51 under `reports/`, 102 under
`New Dashborad/` (largely vendored/generated), 28 under `docs/Archive/`, 20 at repo root.
`docs/00_Project/DOC_AUTHORITY.md` (2026-06-29, Status: Authoritative) is a genuinely
well-structured 10-level precedence system with a canonical lifecycle-vocabulary mapping — but it
governs the `docs/` tree only, not root-level files, and the readiness scanner
(`scripts/lint_docs.py`) still reports ~67 broken links and `docs/documentation_readiness_report_v4.md`
reports ~98 missing file references. The readiness trend across report generations is not a clean
improvement (v3→v4: 84.4%→83.7%, a small regression on a growing file count, and v1's 41.16% used
a different scoring methodology entirely — not directly comparable).

**Verdict**: `DOC_AUTHORITY.md` is a sound mechanism but the existing corpus has not been brought
into compliance with it. Needs an owner-sponsored cleanup pass, not a redesign.

---

## 3. Duplicate/overlapping module directories

**`research/` vs `research_db/` vs `research_engine/` vs `research_sweep/`**
- `research/` — live code, imported by `application/strategy_service.py`, `application/research_service.py`. **Keep.**
- `research_db/` — mixed: `client.py` is a real, imported Postgres/DuckDB client; the rest is
  437 MB of local, gitignored parquet/duckdb data. **Keep code; consider renaming to reduce
  confusion with the root `research.db` file** (owner decision).
- `research_engine/` — pure data dump, 0 imports anywhere, 0 tracked in git, 6.6 MB local.
  **Delete-candidate** (local disk clutter only, no git risk).
- `research_sweep/` — same profile, 0 imports, 0 tracked, 21 MB local. **Delete-candidate.**
- Root `research.db` (10.7 MB) / `research_sweep.db` (5.3 MB) — both untracked/gitignored, no repo
  bloat, just local disk clutter.

**`strategy/` vs `strategies/` vs `strategy_audit/` vs `strategy_validation/` vs `strategy_input/`**
— all five genuinely distinct pipeline stages, all actively imported (raw logic, adapter layer,
Phase-0 audit, Phase-3 validation, intake, respectively). **Verdict: keep all five.**

**`execution/` vs `execution_simulator/` vs `execution_validation/`** — distinct and all live
(real broker layer; Phase-5 offline replay engine; rule-based execution audit engine).
**Verdict: keep all three.**

**`agent/` vs `agents/` vs `agtrade/` vs `adaptive/`** — naming collision, not code duplication:
- `agent/` (singular) — not Python at all, 3 markdown files only.
- `agents/` (plural) — real package (`approval/`, `quality/`, `testing/`), imported by scripts.
- `agtrade/` — CLI orchestrator, imported by `scripts/svos_run.py`.
- `adaptive/` — self-contained engine powering 3 of the 5 portfolio strategies
  (`LondonBreakout`/`NYMomentum`/`AdaptiveSMC`), while `strategies/` adapters run the other 2
  (`ST-A2`, `VWAPMeanReversion`) — **two parallel strategy-execution architectures coexist within
  one declared portfolio**, a real architecture-fragmentation finding, not simple naming debt.
- **Verdict**: rename `agent/` → e.g. `docs/agent_prompts/` (low effort, owner decision). The
  `adaptive/`-vs-`strategies/` split needs a higher-effort owner decision on whether to
  consolidate execution architectures.

**`simulator/` vs `execution_simulator/` vs `virtual_broker/`** — layered, not duplicated
(data/orchestration/broker-primitives respectively, cross-imported as expected). **Verdict: keep all three.**

---

## 4. `archive/` directory

Two full legacy repo snapshots (`session-smc-trading-bot-updated`, `Database-F-prototype`) plus
phase-complete scripts/docs archives. No live code imports from `archive/` — the only string hits
for "archive" in live code are the English word (`tarfile.getnames()`, `archive_sha256` field
names), not actual imports. **Archival was done cleanly. Verdict: keep as-is** — dead weight but
isolated, no risk.

---

## 5. Stray root files and directories

- `audit_strategy.py` — tracked, tiny wrapper calling `strategy_audit.cli.main`, redundant with
  `python -m strategy_audit.cli`. **Verdict: keep (low priority), consider moving to `scripts/`.**
- `scratch_deepseek_test.py` — **untracked but not gitignored**, a one-off DeepSeek API smoke test
  reading a live key from env, named "scratch_" — risks accidental `git add -A` commit.
  **Verdict: delete, or add `scratch_*.py` to `.gitignore`.**
- `backtest_output_d2_holdout/` (1 tracked file) and `backtest_output_d2_optimized/` (3 tracked
  files) — **not gitignored**, inconsistent with the sibling `backtest_output_d2_data/` which
  correctly is. **Verdict: gitignore + untrack.**
- `"New Dashborad"` (typo'd name, stray leading space in a nested path) — 66 tracked files,
  157 MB on disk. **Contains a nested full duplicate of itself** at
  `New Dashborad/Two system on one Dashboard/` — 34 of the 66 tracked files and 156 MB of the
  157 MB is that duplicate, including a committed `dist/` build output and `package-lock.json`.
  No active Python code imports it; referenced only by a couple of dashboard-assessment docs.
  **Verdict: needs owner decision — at minimum delete the nested duplicate; consider moving the
  whole directory to `archive/` and fixing the name if it's kept as the live migration target.**

---

## 6. TODO/FIXME sweep

Repo-wide sweep (excluding `.venv`/`archive/`) found **exactly 1** inline marker:
`strategy/__init__.py:48` — `# TODO (Phase-0 complete): implement SMC signal chain` — self-
contradictory (says "complete" but is still phrased as a TODO); worth a maintainer pass to
confirm actual status. This is unusually low for a repo this size — debt here is tracked in the
root/`docs/` `.md` reports (loss-limit dead code, portfolio YAML not loaded at runtime, dual SVOS
orchestrators, dual execution stacks) rather than in inline code comments. See
`OBJECTIVE_GAP_ANALYSIS.md` and `IMPLEMENTATION_MATRIX.md` for that debt.

---

## 7. Security concerns

- `.gitignore` covers `.env`; no secret-like filenames tracked in git
  (`grep -iE '\.env$|secret|credential|\.pem$|\.key$'` against tracked files → empty).
- `config/llm.yaml` and other config YAML files contain no literal API keys/tokens — only
  non-secret parameters and env-var references.
- CI's own secret-scan (`ci.yml` security job) independently enforces this on every push.
- **Verdict: clean, no action needed** beyond the LLM-adapter dependency-declaration gap noted in
  `IMPLEMENTATION_MATRIX.md` (Multi-Agent/LLM Architecture section) — `openai` is installed but
  undeclared in requirements files.

---

## 8. Committed cache/build artifacts

`git ls-files | grep -E '__pycache__|\.mypy_cache|\.pytest_cache|\.ruff_cache'` → **0 results**.
`.gitignore` explicitly covers `.pytest_cache/`, `.ruff_cache/`, `__pycache__/`.
`.mypy_cache/` isn't explicitly named in `.gitignore` but also isn't tracked.
**Verdict: clean**; optionally add an explicit `.mypy_cache/` line for defense-in-depth, no
current tracked-file risk.

---

## 9. Architecture-level debt (cross-referenced from `IMPLEMENTATION_MATRIX.md`)

These are called out here because they are structural technical debt, not missing features:

- **Two parallel SVOS pipeline orchestrators** (`svos/application/pipeline.py` vs.
  `research/svos/engine.py` + `research/validation/engine.py`) — the legacy one was edited as
  recently as 2026-07-02, after this duplication was first flagged. Neither retired.
- **Two competing execution/order stacks** (`execution/trade_manager.py`, the real path, vs.
  `production/engine/orders.py`/`positions.py`, built in commit `e009d5f` but never imported
  outside their own tests) — scaffolding added without consolidation.
- **Canonical-vs-legacy inversion**: `scripts/run_portfolio.py` (canonical) has weaker
  recovery/governance wiring than `scripts/run_st_a2_demo.py` (legacy) — the supersession is
  incomplete.
- **3 unconsolidated dashboard backend processes** plus 1 in-progress frontend migration
  containing a 156 MB self-duplicate.
