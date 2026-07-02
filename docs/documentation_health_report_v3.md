# Documentation Health Report

Summary:

- Total markdown files scanned: **596**
- Missing file references: **92** — FAIL
- Missing images: **1** — WARNING
- Broken anchors: **0** — PASS
- Orphaned documents: **247** — FAIL

Recommendations:

- Fix or update links listed in `docs/_doc_check_results.json` -> `missing_files`. Prioritise runbooks and top-level docs.
- Replace or remove image references listed in `docs/_doc_check_results.json` -> `missing_images`.
- Review orphaned docs and either link them from the map or move to `docs/archive/`.

Detailed findings are written to `docs/_doc_check_results.json` (machine-readable).