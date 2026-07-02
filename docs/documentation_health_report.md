# Documentation Health Report

Summary:

- Total markdown files scanned: **464**
- Missing file references: **75** — FAIL
- Missing images: **0** — PASS
- Broken anchors: **0** — PASS
- Orphaned documents: **228** — FAIL

Recommendations:

- Fix or update links listed in `docs/_doc_check_results.json` -> `missing_files`. Prioritise runbooks and top-level docs.
- Review orphaned docs and either link them from the map or move to `docs/archive/`.

Detailed findings are written to `docs/_doc_check_results.json` (machine-readable).