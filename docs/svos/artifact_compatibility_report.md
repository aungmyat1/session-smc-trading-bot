# SVOS Orchestrator Artifact Compatibility Report

Status: PLANNING ONLY — HOLD on execution. No code, tests, or runtime
behavior changed by this document. Deepens
`docs/svos/orchestrator_dependency_map.md`'s Q4 finding (artifact formats are
"not interchangeable") into a full schema diff, consumer map, adapter
recommendation, revised migration sequence, and rollback validation, per
TASK-GROUP-2-ARTIFACT-COMPAT. Builds on, and in one place corrects, both
`docs/svos/ORCHESTRATOR_CONSOLIDATION.md` and
`docs/svos/orchestrator_dependency_map.md` — read those first; not repeated
here except where this closer read adds or corrects something.

Commands used for this analysis (repo root, read-only):

```
grep -n "class StageResult|class SVOSRunResult|def run_pipeline|def _resolve_canonical_output_dir|canonical_report|self.stages|@dataclass" research/svos/engine.py
grep -n "report_artifact|builders\.|from svos.reports|import.*builders" svos/application/intake.py svos/application/audit.py
grep -rln "def write_stage_report_package" . --include=*.py
grep -n "_SCHEMA_VERSION\s*=" svos/reports/builders.py
grep -n "dest_dir|def __init__|class.*Builder|def build" svos/reports/builders.py
grep -n "class SVOSPlatform|def bootstrap|def record_report_evidence|PersistenceMode|jsonl|postgres" svos/orchestration/service.py
grep -n "approval_|data/svos/approvals|reports/svos|canonical_output_dir|StrategyPipeline|SVOSRunner" dashboard/pipeline_service.py
```

---

## 1. Artifact format comparison (field-by-field)

There are actually **three** distinct artifact shapes in play, not two — a
correction to the dependency map's framing, which only compared the
top-level `approval_<vid>.json` vs the canonical report tree's
`run_summary.json`/per-stage reports. `StrategyPipeline` produces **two**
different JSON shapes internally:

### 1a. `StrategyPipeline`'s per-phase reports (schema_version `"1.0"`)

Written by `svos/reports/builders.py` (`IntakeReportBuilder`,
`AuditReportBuilder`, `ReplayReportBuilder`, `BacktestReportBuilder`,
`RobustnessReportBuilder`, `VirtualDemoReportBuilder`), one JSON+MD pair per
phase, called from each `svos/application/<phase>.py` integration service
(e.g. `IntakeService.__init__` builds `IntakeReportBuilder(platform.root)`,
`svos/application/intake.py:64-65`).

- Schema version constant: `"1.0"` (`svos/reports/builders.py:28`).
- Path: `data/svos/reports/<phase>/<strategy>/<phase>_<report_id[:16]>.json`
  (e.g. `svos/reports/builders.py:80-83` for intake: `self.reports_root = self.root / "data" / "svos" / "reports" / "intake"`).
- Fields (intake example, `svos/reports/builders.py:59-78`): `report_type`,
  `schema_version`, `stage` (UPPERCASE — `"INTAKE"`), `strategy`,
  `version_id`, `status`, `generated_at`, `specification_hash`, `summary`
  (`error_count`/`warning_count`/`finding_count`), `findings`, `catalog`,
  `run_manifest`, `report_id`.
- No `hard_gate_results`, no `promotion_allowed`, no `thresholds`, no
  `metrics`, no `evidence_hashes`, no `remediation`, no `version_comparison`
  — none of the fields `verify_report_package`'s
  `_REQUIRED_REPORT_FIELDS` (`application/strategy_service.py:42-60`)
  requires.

### 1b. `StrategyPipeline`'s top-level approval package

Written by `StrategyPipeline._write_approval_package`
(`svos/application/pipeline.py:216-240`):

- Path: `data/svos/approvals/<strategy>/approval_<version_id[:12]>.json`.
- Fields: `strategy`, `version_id`, `status` (hardcoded literal
  `"APPROVED_PHASE5"` — note this string is written unconditionally inside
  `_write_approval_package`, which itself is only called when
  `all_passed` is true, `svos/application/pipeline.py:199-203`, so the
  literal is accurate in context but is a magic string, not derived from a
  real 6-phase status enum), `generated_at`, `evidence_ids` (dict of
  `phase -> evidence_id`), `report_artifacts` (dict of
  `phase -> report_artifact path`, i.e. pointers into the 1a per-phase
  files), `manifest_ids` (dict of `phase -> manifest_id`), `manifest_hash`.
- 6 phase keys only: `INTAKE, AUDIT, REPLAY, BACKTEST, ROBUSTNESS,
  VIRTUAL_DEMO` (`svos/application/pipeline.py:17`).
- No `schema_version` field at all on this top-level wrapper (only the
  per-phase files it points to have one, and that one is `"1.0"`).

### 1c. `SVOSRunner`'s canonical report tree (schema_version `"2.0.0"`)

Written by `svos/reports/stage_package.py:write_stage_report_package`
(schema constant `SCHEMA_VERSION = "2.0.0"`, `svos/reports/stage_package.py:13`),
invoked from `SVOSRunner._write_canonical_report_package`
(`research/svos/engine.py:897-960`), itself called at the end of
`run_pipeline` (`research/svos/engine.py:847`).

- Path root: `_resolve_canonical_output_dir()` — defaults to
  `reports/svos/` at repo root unless `output_dir` was explicitly set
  outside the repo tree (`research/svos/engine.py:857-863`). Full path:
  `reports/svos/<strategy_id>/<strategy_version>/<run_id>/<stem>.json`
  (`svos/reports/stage_package.py:471-477`), e.g.
  `01_strategy_audit.json` … `06_production_approval.json` plus
  `run_summary.json`.
- **9 internal stages tracked** (`intake, audit, enhancement, replay,
  backtest, robustness, verification_ready, virtual_demo,
  production_approval` — matches the canonical `svos/lifecycle/manager.py`
  enum), but **collapsed into 6 public report files**
  (`PUBLIC_STAGES`, `svos/reports/stage_package.py:15-22`:
  `strategy_audit, historical_replay, backtest, robustness, virtual_demo,
  production_approval`) via `_SOURCE_STAGES`
  (`svos/reports/stage_package.py:24-31`) — e.g. `strategy_audit` rolls up
  `intake + audit + enhancement`; `virtual_demo` rolls up
  `verification_ready + virtual_demo`. This is a correction/addition to the
  dependency map's "9-stage report tree" framing: the on-disk *file count*
  per run is actually 6 public stage reports + `run_summary` + 5 supporting
  reports (`00_strategy_summary`, `strategy_evolution`, `failure_analysis`,
  `improvement_report`, `final_qualification` —
  `svos/reports/stage_package.py:576-755`) = 11 JSON+MD pairs per run, not 9.
  The "9 stages" language in the prior docs refers to the internal
  `StageResult` count, not the file tree shape.
- Per-stage JSON fields (`svos/reports/stage_package.py:529-558`):
  `schema_version` ("2.0.0"), `report_id`
  (`"<strategy_id>:<strategy_version>:<run_id>:<public_stage>"`), `run_id`,
  `strategy_name`, `strategy_id`, `strategy_version`, `stage` (lowercase
  snake_case, e.g. `"strategy_audit"`), `stage_label`, `status`, `score`,
  `promotion_allowed`, `thresholds`, `hard_gate_results`, `metrics`,
  `findings`, `warnings`, `evidence_hashes`, `remediation`
  (`{route, actions}`), `version_comparison`
  (`{previous_version, current_version, changed}`), `internal_sources`,
  `sections`, `visualizations`, `generated_at`, `release`. This is exactly
  the set `_REQUIRED_REPORT_FIELDS` in
  `application/strategy_service.py:42-60` expects (confirmed 1:1 match).
- `run_summary.json` fields (`svos/reports/stage_package.py:691-725`):
  `schema_version`, `report_id`, `run_id`, `strategy_name`, `strategy_id`,
  `strategy_version`, `overall_status`, `latest_passed_stage`,
  `active_blocker`, `next_task`, `promoted_stage`, `evidence_hashes`,
  `stages` (list of per-stage summaries), `report_center` (pointers to the
  4 supporting reports), `generated_at`, `release`.

### Net diff

| Property | 1a: StrategyPipeline per-phase | 1b: StrategyPipeline approval package | 1c: SVOSRunner canonical tree |
|---|---|---|---|
| schema_version | `"1.0"` | none | `"2.0.0"` |
| Path root | `data/svos/reports/<phase>/<strategy>/` | `data/svos/approvals/<strategy>/` | `reports/svos/<strategy_id>/<strategy_version>/<run_id>/` |
| Stage key casing | `"INTAKE"` (upper) | `"INTAKE"` (upper) | `"strategy_audit"` (lower snake, rolled-up) |
| Phase/stage count | 6 phase-specific builders | 6 phase keys | 6 public files (from 9 internal `StageResult`s) |
| Gate/threshold fields | none | none | `thresholds`, `hard_gate_results`, `promotion_allowed` |
| Evidence hashing | `specification_hash` only | `manifest_hash` (whole package) | `evidence_hashes` dict, per-input |
| Human-readable pair | yes (`.md` per phase) | no (JSON only) | yes (`.md` per stage + per supporting report) |
| Supporting/meta reports | none | none | 5 (`strategy_summary`, `evolution`, `failure_analysis`, `improvement`, `final_qualification`) |

**All three shapes are mutually non-interchangeable** — none of 1a/1b's
fields satisfy `_REQUIRED_REPORT_FIELDS`, and 1c has no equivalent of 1b's
single-file `approval_<vid>.json` (its closest analog,
`06_production_approval.json`, is stage-scoped, not a rollup summary of all
phases — `run_summary.json` is the closer analog but has a different field
set, e.g. no `manifest_hash`, no `evidence_ids`/`manifest_ids` dicts).

---

## 2. Producer/consumer mapping

The dependency map already answered most of this (Q1–Q3); this section adds
the read-side (who *consumes* each artifact *format*, not just who
constructs each *runner*) which the prior doc did not fully separate out.

**Consumers of `StrategyPipeline`'s artifacts (1a/1b):**
- None found beyond the writer itself. `grep -rn "data/svos/approvals\|approval_" --include="*.py" .` (implicit in the file-path search already done for the dependency map) surfaces no reader — `_write_approval_package`'s return value (`approval_package_path`) is only consumed by `svos_main`'s `_print_table` to print the path string (`application/strategy_service.py:139`), not to parse the file back. **No code reads these files back in.** This matters for §3/§4: there is no live reader to migrate, only a writer to potentially retire.

**Consumers of `SVOSRunner`'s canonical tree (1c):**
- `application/strategy_service.py:verify_report_package` (lines 259-314) —
  the **reference implementation** the task brief points to. Reads
  `run_summary.json` + all 6 stage JSON/MD pairs, asserts
  `_REQUIRED_REPORT_FIELDS` presence, `stage`/`status` correctness, and
  JSON/MD status agreement. Called by `run_sample`
  (`application/strategy_service.py:317-349`), which is the CLI's
  `sample_main` entry point (line 209-223) — an isolated, deterministic
  fixture harness, not a production consumer, but it is the only place in
  the repo that programmatically validates the canonical tree's shape.
- `dashboard/pipeline_service.py` — imports and runs `SVOSRunner` directly
  (lines 2-3, 277, 285-289: `"Reports are written to reports/svos/<strategy_id>/..."`),
  and per `docs/audit/function_inventory.md:577` (cited in the dependency
  map) is itself flagged **UNUSED** (no inbound import/launch
  guard/deployment reference). So even this consumer is dormant in
  production today — worth re-flagging since it affects §4/§5 risk
  sizing: there is currently no live production reader of *either* artifact
  format, only test/sample harnesses and a dormant dashboard module.
- `scripts/run_svos_pipeline.py`, `scripts/run_current_strategy_svos.py`,
  `strategy_audit/rules.py` — per `ORCHESTRATOR_CONSOLIDATION.md`'s finding
  (line 21-23), these call `SVOSRunner` but were not verified in this task
  to parse the canonical report tree back in (out of scope here; flagged as
  unverified, not re-derived, per the "don't re-derive" instruction).

**Correction to the risk framing:** because no code reads `StrategyPipeline`'s
artifacts back in, the "artifact incompatibility" risk is **not** "an
existing consumer will break" — it is "a human/manual/dashboard process that
*expects* one format on disk will not find it" (documentation/discoverability
risk), plus the rollback-orphan risk in §5. This is a materially lower risk
class than a live parsing consumer breaking, and changes the §3/§4
recommendation below.

---

## 3. Required adapters — recommendation

**Given §2's finding that no code parses `StrategyPipeline`'s artifacts back
in, building a translation adapter (SVOSRunner output → StrategyPipeline's
`approval_<vid>.json`/per-phase-report shape, or vice versa) is not
justified.** There is no live consumer to keep working. An adapter would add
a fourth artifact shape to maintain for zero functional benefit, and would
directly violate CLAUDE.md §9's "never introduce a second implementation of
something that already exists" governance rule (an adapter here would be a
translation layer nobody reads).

**Recommendation: migrate the one real production touchpoint
(`svos_main`) directly to consume `SVOSRunner`/canonical-tree output, using
`verify_report_package`/`run_sample` (`application/strategy_service.py:259-349`)
as the proven reference for the expected shape, per the dependency map's Q3
step 1.** Do not build a `StrategyPipeline`-format adapter. Concretely:

- `svos_main`'s `_print_table` (`application/strategy_service.py:120-138`)
  must be rewritten (not adapted) to iterate `SVOSRunResult.stages`
  (9 internal `StageResult`s) or the 6 public `PUBLIC_STAGES` — the
  dependency map already flagged this as required; this task confirms there
  is no cheaper adapter path and rewriting `_print_table` + `_PHASE_LABELS`
  is the correct scope, not a translation shim.
- The `approval_<vid>.json` *concept* (single-file, easy-to-grep pass/fail
  summary) has a direct analog already: `run_summary.json`. No new file
  format is needed; point any documentation/runbook that currently
  references `data/svos/approvals/<strategy>/approval_*.json` at
  `reports/svos/<strategy_id>/<strategy_version>/<run_id>/run_summary.json`
  instead.

**Tradeoff acknowledged:** this means any *hypothetical* external tooling
that might exist outside this repo (e.g. a manual analyst script, a BI
import) and expects `data/svos/approvals/...` would break with no
translation layer. §2's search found no such consumer in-repo; if one is
later discovered outside the repo, build a narrow, single-purpose exporter
at that time rather than a general adapter now (YAGNI — do not speculatively
build it as part of this migration).

---

## 4. Migration sequence — revised

Original `ORCHESTRATOR_CONSOLIDATION.md` plan and the dependency map's Q3
correction (write adapter first) are both directionally right but did not
explicitly sequence *artifact* work relative to *re-pointing* `svos_main`.
This section makes that ordering explicit and answers the task's direct
question: artifact/format work must happen **before**, not after, the
`svos_main` re-point, because the re-point *is* the artifact-format change
(there is no separate "re-point now, fix format later" option — `_print_table`
would simply crash on `SVOSRunner`'s `StageResult` shape, per dependency map
Q3(a)).

Revised order (supersedes `ORCHESTRATOR_CONSOLIDATION.md`'s 5-step plan and
folds in dependency map Q3's corrections):

1. **Pre-flight: confirm zero external readers of `data/svos/approvals/`.**
   §2 of this doc did an in-repo search only. Before touching `svos_main`,
   grep any deploy scripts, cron jobs, or runbooks outside the Python
   codebase (shell scripts, systemd units, docs) one more time for
   `data/svos/approvals` and `approval_` as a final check — cheap, and
   removes the single unknown this doc's recommendation (§3) depends on.
2. **Rewrite `_print_table` and `_PHASE_LABELS`** to consume
   `SVOSRunResult`/`StageResult` directly (9 internal stages or the 6
   `PUBLIC_STAGES` rollup — decide and document which, per dependency map
   Q3(a)). Model the read path on `verify_report_package`
   (`application/strategy_service.py:259-314`), the proven working
   reference.
3. **Re-point `svos_main` to `SVOSRunner`.** This step and step 2 are
   effectively one change (they cannot be tested independently — step 2's
   new `_print_table` has nothing to render until step 3 supplies
   `SVOSRunner` output), so land them in the same PR/commit, not
   sequentially.
4. **Manual CLI smoke test**: `python -m agtrade.cli strategy svos --help`
   plus a dry run against `examples/svos_sample` fixtures (dependency map's
   suggested check, still correct).
5. **Port `tests/svos/test_pipeline.py`'s 12 call sites** to `SVOSRunner`
   (dependency map Q3 step 2, unchanged).
6. **Update `svos/application/__init__.py`** deprecation marking (dependency
   map Q3 step 3, unchanged).
7. **Mark `svos/application/pipeline.py` deprecated**, leave in place
   (unchanged from original plan).
8. **Full regression**: `pytest tests/svos/ tests/research_engine/ -q`.
9. **One clean release cycle**, then remove `svos/application/pipeline.py`
   and its test file, **and** at the same time archive (do not delete) any
   `data/svos/approvals/` artifacts that exist on disk from the
   pre-migration period, so the old-format directory isn't left silently
   stale — a small addition this doc makes to step 6 of the original plan.

**Answer to the task's explicit question:** artifact-format work happens
*inside* the `svos_main` re-point step (steps 2-3 above are inseparable),
not before or after it as a distinct phase — because the CLI's read path is
itself the only place format matters, per §2's finding that nothing else
reads either format back in.

---

## 5. Rollback validation

**Question restated:** does rolling back after some `SVOSRunner` runs have
occurred (via the migrated `svos_main`) leave orphaned or incompatible state
in `SVOSPlatform`'s shared persistence layer?

**Finding: no orphaned or incompatible *lifecycle/evidence* state — the
prior dependency map's Q4 conclusion holds and this task's closer read
confirms it with one addition.**

- `SVOSPlatform` (`svos/orchestration/service.py:44`) is a thin
  governance/evidence-record layer with a `PersistenceMode` enum
  (`AUTO`/`AUTHORITATIVE_PG`/`LOCAL_COMPAT`/`PG_AUTO` —
  `svos/orchestration/service.py:27-114`) and a
  `record_report_evidence` method (line 180) that both runners call to
  register *pointers* to their report artifacts (path, stage, status,
  metadata), not the artifact content itself. Rolling back does not corrupt
  this pointer log — old pointers to `SVOSRunner`-produced files simply
  remain valid rows referencing files that are "orphaned" only from the
  post-rollback CLI's *default* expectations, not from `SVOSPlatform`'s
  perspective (it never assumed one runner's format over the other; it just
  records whatever path it's given).
- **Addition this task confirms beyond the dependency map:** because
  `record_report_evidence` stores `artifact_path` as an opaque string
  (`svos/orchestration/service.py:180` signature takes `artifact_path: str`
  with no schema validation on read), a mixed history (some evidence rows
  pointing at `data/svos/reports/<phase>/...` schema-1.0 files, others at
  `reports/svos/.../<stem>.json` schema-2.0.0 files) is mechanically
  harmless to `SVOSPlatform` itself — it will never try to parse one as the
  other. The risk is entirely in *downstream human/dashboard expectations*,
  not in `SVOSPlatform`'s own data integrity. This confirms and slightly
  strengthens the dependency map's Q4 answer ("lifecycle state via
  SVOSPlatform stays consistent either way").
- **Genuine gap (unchanged from dependency map):** any manual audit,
  runbook, or dashboard view that assumes a single canonical artifact
  location for a given strategy will not automatically discover both
  formats — this is a discoverability/documentation risk, not a data
  corruption risk. Given §2's finding that no in-repo code currently reads
  either format back in besides `verify_report_package` (sample-fixture
  only) and the dormant `dashboard/pipeline_service.py`, this residual risk
  is low-severity today, but should still be called out explicitly in the
  migration PR/changelog per the dependency map's original recommendation.

**Summary:** rollback is safe from a `SVOSPlatform` state-integrity
standpoint (confirmed, not just repeated). The only rollback action needed
beyond the mechanical 3-file code revert (dependency map Q4) is archiving
(not deleting) any `SVOSRunner`-produced `reports/svos/...` trees generated
during the migration window, and noting in the rollback changelog which
artifact format is authoritative post-rollback.

---

## Corrections to prior docs (summary)

1. **Three artifact shapes, not two** — `StrategyPipeline` produces both a
   per-phase report set (schema `"1.0"`, `data/svos/reports/<phase>/...`)
   *and* a top-level approval package (`data/svos/approvals/...`, no
   schema_version field at all), not one flat format as implied by the
   dependency map's framing.
2. **"9-stage report tree" clarified**: `SVOSRunner` tracks 9 internal
   `StageResult`s but writes 6 public per-stage files + `run_summary` + 5
   supporting reports = 11 JSON+MD pairs on disk per run. "9 stages" refers
   to the internal model, not the file count.
3. **No live consumer reads `StrategyPipeline`'s artifacts back in** — this
   was not established by either prior doc. It changes the practical risk
   class from "a reader will break" to "a human/dashboard expectation will
   go unmet," and is why this doc recommends against building a translation
   adapter.
4. **`dashboard/pipeline_service.py` (the one real `SVOSRunner` artifact
   consumer besides the sample harness) is itself flagged UNUSED** — re-
   confirmed here (already flagged by the dependency map as a backlog item,
   not re-derived, just re-surfaced because it directly affects this
   report's §2/§3 risk sizing).
5. **Artifact-format work is not a separable phase** — it must land in the
   same change as the `svos_main` re-point (§4), because `_print_table`'s
   crash-on-wrong-shape is the only place the two formats actually collide
   today.
