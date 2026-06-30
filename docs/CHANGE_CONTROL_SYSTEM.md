# Change Control System

Date: 2026-06-30
Status: Authoritative
Version: 1.0
Updated: 2026-06-30
Owner: Engineering
Authority: Level 5 — Development Standards
Related: docs/00_Project/DOC_AUTHORITY.md, docs/DEVELOPER_HANDBOOK.md, docs/OPERATING_MANUAL.md

## Purpose

This document defines the repository-level documentation system for recording:

- code and configuration changes
- runtime observations
- verification results
- the "runner not active" state

The goal is to make ordinary repository work traceable without requiring a full
SVOS stage run or PostgreSQL evidence write.

## Scope

This system is for:

- repo changes that affect implementation, config, docs, or operations
- manual runtime checks
- operator observations about whether a bot is running or not running
- small implementation tasks that still need durable context

This system is not a replacement for:

- SVOS run manifests under `data/svos/manifests/`
- stage evidence packages
- PostgreSQL control-plane records
- research or backtest reports

## Storage Location

All change-control records are written under:

`reports/change_control/`

Artifacts:

- `<event_id>.json` — machine-readable record
- `<event_id>.md` — operator-readable summary
- `index.json` — reverse-chronological index

These files are append-only operational records. New records supersede older
observations; old records are preserved for auditability.

## Required Record Types

Use one of these `change_type` values:

- `repo_change` — code or file modifications
- `runtime_snapshot` — status check of current runners or bot state
- `config_change` — config or environment-facing change
- `doc_update` — documentation-only change
- `verification` — result of tests, health checks, or manual validation

Use one of these `status` values:

- `planned`
- `implemented`
- `verified`
- `observed`

## Minimum Content

Every record must include:

- timestamp
- actor
- summary
- change type
- status
- repository snapshot
  - branch
  - commit
  - dirty file list
- runtime snapshot
  - whether a runner appears active
  - latest runtime state file when present
  - latest known log line when present

Optional but recommended:

- strategy name
- lifecycle stage or catalog status
- affected files
- verification steps
- notes

## Command

Use:

```bash
python3 scripts/document_change.py \
  --summary "Implemented data-layer partitioned outputs" \
  --change-type repo_change \
  --status verified \
  --strategy D2E3 \
  --affected-file src/pipeline.py \
  --affected-file src/data/layered_store.py \
  --verify "python3 -m pytest -o addopts='' tests/research_engine/test_pipeline.py -q"
```

Runtime-only observation:

```bash
python3 scripts/document_change.py \
  --summary "Checked bot runtime; no SMCOrderBlockFVGSession process active" \
  --change-type runtime_snapshot \
  --status observed \
  --strategy SMCOrderBlockFVGSession
```

## Usage Rules

Create a record when:

- a task changes repo files in a way another operator should be able to trace
- a runtime state is checked and that result matters
- a verification result is used to support a decision
- an inactive runner state is relevant to current work

Do not create records for:

- trivial read-only exploration with no operational consequence
- duplicate checks that add no new information
- generated artifacts unrelated to the current repository state

## Relationship To Existing Systems

- Use SVOS run manifests for replay, backtest, robustness, virtual demo, and
  audit runs.
- Use change-control records for normal repository work and runtime checks.
- If a task produces both a repo change and a stage run, keep both:
  - stage run in SVOS manifest/evidence path
  - implementation and operator context in change control

## Operator Benefit

This system answers:

- what changed
- who recorded it
- what commit and dirty state existed at that time
- what strategy context applied
- whether a bot was running, stale, or not active
- how the change was verified
