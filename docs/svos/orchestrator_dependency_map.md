# SVOS Orchestrator Dependency Map

Status: PREPARATION ONLY — no code changed, no migration executed.
Scope: deepens `docs/svos/ORCHESTRATOR_CONSOLIDATION.md` into a verifiable,
file:line-cited dependency audit before that migration is approved. Distinct
from `docs/systems/system2/PIPELINE_CONSOLIDATION_PLAN.md` (System-2
execution runner duplication) — not touched, not conflated here.

Search commands run (repo root, working tree clean):

```
grep -rn "StrategyPipeline" --include="*.py" .
grep -rln "StrategyPipeline" . --exclude-dir=.git
grep -rn "application\.pipeline|application/pipeline" --include="*.py" .
grep -rn "SVOSRunner" --include="*.py" . --exclude-dir=.git
grep -rln "SVOSRunner" . --exclude-dir=.git
grep -rn "SVOSPlatform" --include="*.py" . --exclude-dir=.git
grep -rln "SVOSPlatform" . --exclude-dir=.git
grep -rn "orchestration\.service|orchestration/service" --include="*.py" .
find . -iname "*.service" -o -iname "*cron*" -o -path "*/deploy/*" | xargs grep -l "StrategyPipeline|svos_main|application.pipeline"
find . -iname "*.service" -not -path "./.git/*"
grep -rn "svos_main|strategy svos|agtrade" --include="*.py" . | grep -i "entry|console_scripts|argparse|subparsers"
grep -n "StrategyPipeline|svos_main" docs/project_manifest.yaml docs/architecture_summary.md docs/audit/function_inventory.md
grep -n "svos" Makefile
```

---

## Q1 — What uses `StrategyPipeline`?

**Real Python dependents (exhaustive):**

| File:line | Reference |
|---|---|
| `application/strategy_service.py:17` | `from svos.application.pipeline import StrategyPipeline` |
| `application/strategy_service.py:186` | `pipeline = StrategyPipeline(platform)` — inside `svos_main()` |
| `svos/application/__init__.py:14,39` | re-exports `StrategyPipeline` as part of `svos.application`'s public API |
| `tests/svos/test_pipeline.py:19,111,126,142,154,166,178,189,204,221,249,270,284` | 12 test functions (`grep -c "^def test_" tests/svos/test_pipeline.py` = 12) instantiate `StrategyPipeline(platform).run(...)` directly — **correction: `ORCHESTRATOR_CONSOLIDATION.md` states "9 tests"; actual count verified at 12** |

**CLI entry point trace:** `agtrade/cli.py:22` imports `svos_main` from
`application.strategy_service`; `agtrade/cli.py:44-45` registers it as
`agtrade strategy svos` (`strategy_svos.set_defaults(handler=svos_main)`).
This is the **only** CLI path that reaches `StrategyPipeline` — confirmed,
not just asserted (see call chain: `agtrade strategy svos` → `svos_main` →
`StrategyPipeline(platform).run(...)`, `application/strategy_service.py:186-200`).

**Scheduled jobs / systemd / cron:** none found. `find . -iname "*.service"`
returned 7 units, all under `deploy/gcp-vm1/systemd/` (`agtrade-deployment-agent`,
`d2e3-journal-sync`, `reconcile-positions`, `d2e3`, `vps-health-check`,
`smc-demo-runner`, `live-dashboard`). None reference `StrategyPipeline`,
`svos_main`, or `application.pipeline` — grepped directly, zero hits.

**Docs/deployment references (non-code):**
- `docs/architecture_summary.md:36` — `application/  COMPLETE — StrategyPipeline (6-phase orchestrator); svos_run.py CLI entry`
- `docs/audit/function_inventory.md:972` — lists `StrategyPipeline` as **ACTIVE**, citing "Referenced by Makefile/README/deployment configuration" — **this claim does not hold up**. `grep -n "svos" Makefile` shows only two generic lint/type-check targets (`ruff check svos strategy_validation`, `mypy svos/lifecycle svos/shared`, `Makefile:36-37`) that lint the whole `svos` package tree, not a `StrategyPipeline`-specific reference. No README references `svos_main` or `agtrade strategy svos` (`grep -rln` on `README*` returned zero hits). **Correction to prior audit doc: the Makefile/README claim in `function_inventory.md:972` is not supported by evidence and should not be relied on.**
- `docs/svos/ORCHESTRATOR_CONSOLIDATION.md` — this session's own recommendation doc (already accounted for, not a new dependency).
- `reports/unit-coverage.json` — a generated coverage artifact, not a dependency; it records line coverage for `svos/application/pipeline.py` (stale/regenerable, not load-bearing).
- `docs/project_manifest.yaml` — grepped, contains a `StrategyPipeline` string reference in the module inventory listing only (metadata, not a live dependency).

**False positives (unrelated, do not touch):** `New Dashborad/Two system on
one Dashboard/src/types.ts:46`, `.../SocketContext.tsx`, `.../PipelineOpsDashboard.tsx`,
`New Dashborad/Gai dashboard/src/docs/UPGRADE_SPEC.md:77` all reference a
TypeScript `StrategyPipelineReport` type / `LiveStrategyPipeline` UI component
in the frontend dashboards. These are naming coincidences with the dashboard's
own report type, not references to the Python `StrategyPipeline` class. No
action needed.

**Correction to prior finding:** ARCH-01's claim of "exactly one call site
(`application/strategy_service.py:svos_main`)" is **CONFIRMED CORRECT** for
production/CLI code paths. It is incomplete only in that it didn't enumerate
the 12 direct test call sites in `tests/svos/test_pipeline.py` or the
re-export in `svos/application/__init__.py:14,39` — neither changes the
consolidation calculus (both are consequences of the one real call site, not
independent production dependents), but both must be migrated/updated as part
of any change (see Q3).

---

## Q2 — What breaks if `StrategyPipeline` is removed?

Tracing each caller from Q1 to its exact failure mode if
`svos/application/pipeline.py` disappeared with no other change:

1. **`application/strategy_service.py:17`** — `ImportError` at module import
   time (`from svos.application.pipeline import StrategyPipeline`). This
   module is imported by `agtrade/cli.py:22`, so **the entire `agtrade` CLI
   would fail to start** (not just `strategy svos` — argparse subcommand
   registration happens at import time, before any subcommand is dispatched),
   taking down `strategy audit`, `strategy validate`, and `strategy sample`
   CLI paths as collateral damage since they share the same module.
2. **`svos/application/__init__.py:14,39`** — `ImportError` on
   `from svos.application.pipeline import PhaseOutcome, PipelineResult, StrategyPipeline`.
   Anything doing `from svos.application import StrategyPipeline` (or `import
   svos.application` at all, since the failing import is at package-init
   time) breaks. This makes the blast radius the whole `svos.application`
   namespace, not just direct importers of `svos.application.pipeline`.
3. **`tests/svos/test_pipeline.py`** — collection error (`ImportError` at
   `import` time), which under pytest turns into all 12 tests in that file
   reporting as errored, and depending on pytest config (`--strict-markers`
   / collection failure handling) may abort the `tests/svos/` collection run
   entirely rather than just skipping the one file.
4. **Indirect: `dashboard/pipeline_service.py`, `scripts/run_svos_pipeline.py`,
   `scripts/run_current_strategy_svos.py`** — these use `SVOSRunner`, not
   `StrategyPipeline` (confirmed by grep, Q1/Q3 target-side trace below); they
   are unaffected by removing `StrategyPipeline` and should not be touched in
   this migration.

**Net: removal without migration = broken `agtrade` CLI (whole binary, not
just the `svos` subcommand) + broken `tests/svos/` collection.** This is
consistent with why `ORCHESTRATOR_CONSOLIDATION.md`'s plan does NOT delete the
file immediately (step 5, deferred "after one clean release cycle") — that
sequencing is correct and should not be shortcut.

---

## Q3 — Exact migration steps (verified/corrected from `ORCHESTRATOR_CONSOLIDATION.md`)

The high-level plan in `ORCHESTRATOR_CONSOLIDATION.md` is directionally
correct but under-specifies two things this map corrects: (a) `svos_main`'s
current CLI output contract depends on flat per-phase attributes
(`phase.phase`, `phase.status`, `phase.elapsed_s` — see `_print_table`,
`application/strategy_service.py:120-138`) that `SVOSRunner`'s `StageResult`
objects do not share verbatim (`StageResult`/`SVOSRunResult`, `research/svos/engine.py:377,438`,
9-stage shape vs `StrategyPipeline`'s 6-phase shape) — a naive re-point breaks
`_print_table` and the approval-package writer; (b) `svos/application/__init__.py`
re-export must be updated in lockstep with step 1, not left dangling.

Corrected, ordered steps:

1. **Write an adapter, not a raw re-point.** In `application/strategy_service.py`,
   `svos_main` (currently line ~142-207) must translate `SVOSRunner.run_pipeline()`'s
   `SVOSRunResult`/`StageResult` (`research/svos/engine.py:377-457`, 9 stages:
   intake, audit, enhancement, replay, backtest, robustness,
   verification_ready, virtual_demo, production_approval) into the same shape
   `_print_table` and the CLI's exit-code contract (`result.passed`,
   `application/strategy_service.py` phase table) currently expect, OR update
   `_print_table` to accept `StageResult`'s actual field names directly.
   Decide and document which; do not silently drop the 3 extra stages
   (`ENHANCEMENT`, `VERIFICATION_READY` plus the 9-vs-6 stage mismatch) — the
   CLI's `_PHASE_LABELS` dict (`application/strategy_service.py:24-30`) only
   maps 6 phases and will need the 3 additional labels or an explicit
   "N/A for this CLI" decision.
   Test after this step: `pytest tests/svos/test_pipeline.py -x` will still
   fail/be irrelevant until step 2; use manual CLI smoke test instead:
   `python -m agtrade.cli strategy svos --help` plus a dry run against
   `examples/svos_sample` fixtures.
2. **Port `tests/svos/test_pipeline.py`'s 12 call sites to `SVOSRunner`.**
   Each of the 9 named test functions (per file docstring, `tests/svos/test_pipeline.py:1`)
   needs its `StrategyPipeline(platform).run(...)` call and PASS/FAIL/SKIPPED
   assertions re-expressed against `SVOSRunner(...).run_pipeline(...)`
   (`research/svos/engine.py:704`) — note the different `stop_after` /
   `promote` / `allow_live_promotion` kwargs vs `StrategyPipeline.run`'s
   `expected_pf`/`symbol` kwargs; these are not 1:1. Port intent, not syntax.
   Test after this step: `pytest tests/svos/ -x` (whole directory, not just
   the renamed file, to catch platform-shared regressions).
3. **Update `svos/application/__init__.py:14,39`** to stop re-exporting
   `StrategyPipeline` as a public/blessed symbol once no production code
   calls it, OR leave the re-export (harmless) and only mark it deprecated —
   ORCHESTRATOR_CONSOLIDATION.md's step 3 says "docstring, no new callers";
   this map adds: also audit `__all__` in that `__init__.py` so deprecation is
   visible to anything doing `from svos.application import *`.
4. **Mark `svos/application/pipeline.py` deprecated** (docstring only, per
   original plan) — no code change to its logic, since it must keep working
   for rollback (Q4).
5. **Confirm `tests/svos/test_platform.py` and dashboard SVOS tests stay
   green.** Command: `pytest tests/svos/test_platform.py tests/svos/test_research_pipeline.py tests/svos/test_virtual_demo_pipeline.py tests/svos/test_intake_pipeline.py -x`
   (these all import `SVOSPlatform` directly per Q-shared-layer trace below
   and must be unaffected by the `StrategyPipeline`→`SVOSRunner` swap since
   they don't touch either runner class).
6. **One clean release cycle, then remove** `svos/application/pipeline.py`
   and `tests/svos/test_pipeline.py` in a follow-up change — unchanged from
   original plan, still correct.

**Full regression command to run after every step above:**
`pytest tests/svos/ tests/research_engine/ -q` (covers both runner families
and the shared platform layer in one pass).

---

## Q4 — Rollback plan (concrete, including state/format compatibility)

**Mechanical rollback (steps 1-3 above only, before step 6's deletion):**
revert the `svos_main` adapter in `application/strategy_service.py` back to
direct `StrategyPipeline(platform).run(...)` calls, revert
`tests/svos/test_pipeline.py` to its original `StrategyPipeline` assertions,
revert the `svos/application/__init__.py` deprecation docstring/export
change. This is a 3-file revert (not the "single-file revert" the original
doc claims — `ORCHESTRATOR_CONSOLIDATION.md`'s rollback section undercounts
the surface by omitting the test file and the `__init__.py` re-export, both
of which get touched in steps 2-3). **Correction: rollback is 3 files, not 1,
until step 6 executes** (after step 6, the file is gone and rollback would
require restoring it from git history — still simple, but a different
operation than "revert an import").

**State/evidence format compatibility — this is the substantive risk the
original doc does not address:**

- `StrategyPipeline` writes its own approval artifact directly:
  `data/svos/approvals/<strategy>/approval_<version_id[:12]>.json`
  (`svos/application/pipeline.py:216-240`), with `"status": "APPROVED_PHASE5"`
  and a flat 6-phase `evidence_summary`/`report_artifacts`/`manifest_ids`
  shape. This is a bespoke output format that only `StrategyPipeline`
  produces — nothing else reads or writes files at that path.
- `SVOSRunner` writes to a completely different, richer artifact tree via
  `canonical_output_dir` (`research/svos/engine.py:679,698-701,857`,
  `_resolve_canonical_output_dir`): per-stage `run_summary.json`/`.md` plus
  JSON/Markdown pairs per stage under a `reports/svos`-style canonical root
  (see `verify_report_package` in `application/strategy_service.py:259-315`
  for the exact expected shape SVOSRunner already produces via `run_sample`/
  `sample_main`, which is the **existing, working reference implementation**
  of consuming `SVOSRunner` output — worth reusing as the model for the step-1
  adapter rather than inventing a new translation).
- **Both runners share `SVOSPlatform` for lifecycle/evidence persistence**
  (`svos/orchestration/service.py:44`, confirmed: `StrategyPipeline.__init__`
  takes a `platform` object and wires 6 `*IntegrationService` classes to it,
  `svos/application/pipeline.py:72-79`; `SVOSRunner._platform` is also an
  `SVOSPlatform` instance, `research/svos/engine.py:697,886`). This means
  **lifecycle-stage writes and evidence-hash records made by either runner
  land in the same underlying store** (local JSONL or Postgres, per
  `PersistenceMode`) — so a strategy audited via `StrategyPipeline` and later
  re-run via `SVOSRunner` (or vice versa) will see consistent lifecycle
  state through `SVOSPlatform`, but the **file-level approval package and
  report artifacts will NOT be interchangeable** — `SVOSRunner` cannot read
  a `StrategyPipeline`-produced `approval_<vid>.json`, and downstream
  tooling that consumes `SVOSRunner`'s canonical report tree
  (`dashboard/pipeline_service.py`) will not find anything if only
  `StrategyPipeline` was run for a given strategy/version.
- **Practical consequence for rollback:** if `SVOSRunner` runs occur through
  the migrated `svos_main` (writing canonical-report-tree artifacts) and the
  team then rolls back to `StrategyPipeline` (reverting to
  `data/svos/approvals/...` artifacts), the two artifact sets are **not
  orphaned in the sense of corrupting shared state** (because `SVOSPlatform`
  lifecycle/evidence records remain consistent underneath), but they **are
  incompatible file-format-wise** — any dashboard, report viewer, or manual
  audit process expecting one format will not find the other. Rollback should
  explicitly note in its changelog/PR description which artifact format is
  authoritative post-rollback, and that pre-rollback `SVOSRunner`-produced
  canonical reports for strategies run during the migration window remain on
  disk (harmless, just orphaned from the CLI's post-rollback expectations)
  and can be manually archived, not deleted.

**Summary answer to Q4:** rollback is mechanically simple (revert 3 files,
covered by tests/svos/ and tests/research_engine/ passing), lifecycle state
via `SVOSPlatform` stays consistent either way, but **artifact/report file
formats between the two runners are not interchangeable** — this is a real,
previously undocumented risk that should gate how long the team runs
`SVOSRunner`-via-CLI before treating step 6 (deletion) as safe.

---

## Summary of corrections to `ORCHESTRATOR_CONSOLIDATION.md`

1. Single-call-site claim for production code: confirmed correct; doc should
   additionally note the 12 direct test call sites and the `__init__.py`
   re-export as required-but-not-independent migration touchpoints.
2. `function_inventory.md:972`'s "Referenced by Makefile/README/deployment
   configuration" justification for `StrategyPipeline` being ACTIVE is
   **not supported by evidence** — the only Makefile `svos` references are
   generic lint targets covering the whole package tree, not this file
   specifically. Should not be cited as a reason to keep the module.
3. Rollback is a 3-file revert (svos_main call site, test file, `__init__.py`
   re-export), not a "single-file revert with no cascading changes" as
   originally stated.
4. Artifact/report format compatibility between `StrategyPipeline` and
   `SVOSRunner` was not addressed in the original doc and is a real gap:
   the two runners produce non-interchangeable output files even though
   they share `SVOSPlatform` for lifecycle state.
5. `dashboard/pipeline_service.py` is itself flagged **UNUSED** by
   `docs/audit/function_inventory.md:577` (no static inbound import, launch
   guard, or deployment reference found) despite importing `SVOSRunner` —
   noted here for completeness; it is a consumer of the migration target,
   not the duplicate, so out of scope for this task but worth flagging to
   the PM backlog as a separate dead-code question.
