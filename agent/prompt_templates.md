# SVOS Agent Prompt Templates
# Copy-paste these to start an implementation session.
# Replace [TASK_ID] with the actual task. Keep everything else as-is.

---

## Template 1 — Standard Implementation Task

```
Load docs/project_manifest.yaml and tasks/[TASK_ID].yaml.
Load agent/implementation_rules.md.
Then load only the files listed in tasks/[TASK_ID].yaml → files_to_read.

Do not load any other files unless blocked.

Implement the task. Follow the done_when criteria exactly.
Return output in the standard format from agent/implementation_rules.md.
```

**Token budget:** ~2,000–5,000 tokens per task (manifest + task file + 2-4 source files)

---

## Template 2 — Quick Fix (P0-4 pattern)

```
Load docs/project_manifest.yaml.
Read svos/shared/__init__.py and svos/shared/models.py.
Add GateDecision and ApprovalRecord to the __init__.py exports.
Run: python -c "from svos.shared import GateDecision, ApprovalRecord"
Run: pytest tests/governance/ -q
Return: files changed, test result, next task.
```

**Token budget:** ~500–1,000 tokens

---

## Template 3 — Verification Task

```
Load docs/project_manifest.yaml.
Read tasks/[TASK_ID].yaml → done_when section only.
Run the verification commands for each done_when criterion.
Report: PASS or FAIL for each. Do not make changes.
```

**Token budget:** ~1,000 tokens

---

## Template 4 — Exploration Before Implementation

```
Load docs/project_manifest.yaml and docs/architecture_summary.md.
Read these specific files: [list — max 4 files].
Answer: [specific question].
Do not implement anything.
```

**Token budget:** ~3,000 tokens

---

## Template 5 — Test Writing

```
Load docs/project_manifest.yaml.
Read [source file to test] and [existing test file for similar module].
Write tests for [specific functions/methods].
Follow agent/coding_rules.md test naming conventions.
Do not test [excluded scenarios].
Target: [N] test functions.
Return: file path, test count, coverage delta if measurable.
```

**Token budget:** ~3,000–6,000 tokens

---

## Template 6 — Pipeline Task (P1-2 sub-tasks)

```
Load docs/project_manifest.yaml.
Read tasks/P1-2.yaml → sub_tasks section for [P1-2a | P1-2b | P1-2c | P1-2d].
Read the target file: [pipeline/run_phase0.py | pipeline_03 | pipeline_04 | __init__.py].
Read strategies/adapters/__init__.py for the dispatch registry.
Implement only the sub-task described. One sub-task per session.
Verify with: grep -r 'ST-A2\|ST_A2\|sta2' pipeline/ after change.
Return: standard format + grep result.
```

**Token budget:** ~3,000–6,000 tokens per sub-task

---

## Anti-patterns (never use these)

```
# BAD — loads too much
"Read the entire project. Understand the architecture.
Then implement P0-1."
→ Wastes 15,000+ tokens on context that isn't needed.

# BAD — no task scoping
"Fix all the hardcoded strategy references in the codebase."
→ Too broad; will miss things and make incorrect changes.

# BAD — redundant analysis
"Based on the project status report, determine what needs to be done for P1-2."
→ tasks/P1-2.yaml already contains this. Load the file.

# GOOD — scoped, file-indexed
"Load docs/project_manifest.yaml and tasks/P0-4.yaml.
Read svos/shared/__init__.py.
Fix the missing exports. Run the verification. Return the standard output."
→ ~800 tokens total.
```

---

## Estimating token usage

| Session type | Files loaded | Typical tokens |
|---|---|---|
| Trivial fix (P0-4) | manifest + 1-2 files | 500-1,000 |
| Small task (P0-1, P0-3) | manifest + task + 3 files | 2,000-4,000 |
| Medium task (P1-1, P1-4) | manifest + task + 4-5 files | 4,000-8,000 |
| Large task (P1-2 sub-task) | manifest + task + 3 files | 3,000-6,000 |
| Test writing | manifest + source + test example | 3,000-6,000 |
| Full audit (PROJECT_STATUS_REPORT) | entire codebase | 50,000-150,000 |

Run a full audit once per milestone. Run targeted tasks for everything else.
