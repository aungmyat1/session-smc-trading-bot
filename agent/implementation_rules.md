# SVOS Implementation Rules
# Load this file in every implementation session.
# These rules are permanent. They do not change between tasks.

---

## Session Startup Checklist

Before writing any code, load these files (in order, read nothing else unless the task requires it):

1. `docs/project_manifest.yaml` — completion status, current priority, module status
2. `tasks/<TASK_ID>.yaml` — exact goal, files to read, done_when, do_not
3. Read only the files listed in the task manifest's `files_to_read` section
4. `docs/dependency_graph.yaml` — only if you need to understand task ordering

Do NOT load the full project status report, architecture docs, or governing plans
unless the task manifest explicitly requires it.

---

## Absolute Rules (never violate)

1. **Never hardcode a strategy name.** Use registry lookup keyed by strategy_id.
   Applies to: SQL strings, script paths, file paths, banner text, comments.

2. **Never bypass governance.** `svos/lifecycle/manager.py` is the only authority
   for lifecycle stage mutations. No direct YAML writes. No `promote_strategy_stage()`.
   The `DirectCatalogMutationError` is not a bug to work around — it is a safety gate.

3. **Never write YAML for lifecycle state.** `config/strategy_catalog.yaml` is a
   read-only projection. The only writer is `db/projection.py`.

4. **Never enable live trading.** `LIVE_TRADING=false` and `DEMO_ONLY=true` are
   platform invariants. The only unlock is `CONFIRM-LIVE-ON` from the owner.

5. **Never run a backtest without a pre-registered trial ID.** Add a row to
   `docs/VERDICT_LOG.md` with the trial ID and spec BEFORE running. Never reuse a
   trial ID after changing parameters.

6. **Never start a new feature while `feature_freeze: true`** in project_manifest.yaml.
   Complete P0 tasks first.

7. **Offline Virtual Demo only.** No broker connection. No network access. No MetaAPI.

8. **Net-of-fees only.** Backtest results without spread + commission are not results.
   Must pass both standard spread AND 2× stress.

---

## Code Change Rules

- Read the target file before editing. Understand the existing pattern.
- Match the existing code style exactly (indentation, naming, docstring format).
- One logical change per commit. Do not bundle unrelated fixes.
- Every change must have a test or extend an existing test.
- Do not change test assertions to make tests pass — fix the production code.
- Do not add `# pragma: no cover` to skip coverage.
- Dependencies point inward: domain code must not import SQLAlchemy, Flask, or broker SDKs.

---

## Scope Rules

- Complete the task in `tasks/<TASK_ID>.yaml`. Nothing more.
- If you discover a related issue while implementing: note it in the output, do not fix it.
- Do not refactor surrounding code unless it directly blocks the task.
- Do not add features the task does not require.

---

## Output Format (every task must return)

```
## <TASK_ID> Result
Status: COMPLETE | BLOCKED | PARTIAL
Files changed: [exact list]
Tests: N passed, N failed
Key verification: [done_when item → PASS/FAIL]
Issues found (not fixed): [if any]
Next task: <TASK_ID>
```

---

## Token Efficiency Rules

- Read only the files listed in the task manifest.
- Do not re-read a file you already read in the same session.
- Do not re-run analysis you already completed.
- Do not produce narrative explanations unless the task asks for a report.
- Keep output in the standard format above.
