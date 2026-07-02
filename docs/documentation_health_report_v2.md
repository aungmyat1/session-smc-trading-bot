# Documentation Health Report

Summary:

- Total markdown files scanned: **592**
- Missing file references: **67** — FAIL
- Missing images: **1** — WARNING
- Broken anchors: **77** — FAIL
- Orphaned documents: **326** — FAIL

Recommendations:

- Fix or update links listed in `docs/_doc_check_results.json` -> `missing_files`. Prioritise runbooks and top-level docs.
- Replace or remove image references listed in `docs/_doc_check_results.json` -> `missing_images`.
- Repair broken anchors or update links to match heading text. Use consistent header metadata.
- Review orphaned docs and either link them from the map or move to `docs/archive/`.

Detailed findings are written to `docs/_doc_check_results.json` (machine-readable).