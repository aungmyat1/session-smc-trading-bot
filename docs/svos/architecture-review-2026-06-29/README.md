# SVOS Architecture Review — 2026-06-29

This directory is the authoritative architecture review requested before any
further feature development.

## Decision

**NOT READY** — feature expansion should remain paused until the Critical and
High Phase 1 findings are closed.

Overall readiness: **53/100**.

## Reports

1. [Executive Summary](00_EXECUTIVE_SUMMARY.md)
2. [Architecture Assessment](01_ARCHITECTURE_ASSESSMENT.md)
3. [Database Assessment](02_DATABASE_ASSESSMENT.md)
4. [Code Quality Assessment](03_CODE_QUALITY.md)
5. [Gap Analysis](04_GAP_ANALYSIS.md)
6. [Risk Register](05_RISK_ASSESSMENT.md)
7. [Upgrade Roadmap](06_UPGRADE_ROADMAP.md)

## Evidence baseline

- Active Python files: 411
- Active Python lines including tests: 67,046
- Test cases collected and passed: 1,170 / 1,170
- Test files: 85
- Top-level documentation files: 84
- PostgreSQL schema tables: 16
- Persistence technologies: PostgreSQL, DuckDB, SQLite, YAML, JSON, JSONL,
  Parquet, and Markdown artifacts
- Packaging/quality automation: requirements file and pytest configuration;
  no CI workflow, migration framework, type-check configuration, lint
  configuration, coverage gate, or lock file

“Active” excludes `.git`, `archive`, caches, and generated Python bytecode. The
embedded repository below `session_smc/` is active because pytest/import
configuration does not exclude it and runtime scripts reference that tree.

