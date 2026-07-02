#!/usr/bin/env python3
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
res_file=ROOT/'docs'/'_doc_check_results.json'
out_file=ROOT/'docs'/'documentation_health_report.md'

if not res_file.exists():
    print('No results file found:', res_file)
    raise SystemExit(1)

data=json.loads(res_file.read_text())

total=data.get('total_markdown',0)
missing_files=len(data.get('missing_files',[]))
missing_images=len(data.get('missing_images',[]))
broken_anchors=len(data.get('broken_anchors',[]))
orphaned=len(data.get('orphaned_files',[]))

def status_label(count):
    if count==0:
        return 'PASS'
    if count<=5:
        return 'WARNING'
    return 'FAIL'

content=[]
content.append('# Documentation Health Report')
content.append('')
content.append('Summary:')
content.append('')
content.append(f'- Total markdown files scanned: **{total}**')
content.append(f'- Missing file references: **{missing_files}** — {status_label(missing_files)}')
content.append(f'- Missing images: **{missing_images}** — {status_label(missing_images)}')
content.append(f'- Broken anchors: **{broken_anchors}** — {status_label(broken_anchors)}')
content.append(f'- Orphaned documents: **{orphaned}** — {status_label(orphaned)}')
content.append('')
content.append('Recommendations:')
content.append('')
if missing_files>0:
    content.append('- Fix or update links listed in `docs/_doc_check_results.json` -> `missing_files`. Prioritise runbooks and top-level docs.')
if missing_images>0:
    content.append('- Replace or remove image references listed in `docs/_doc_check_results.json` -> `missing_images`.')
if broken_anchors>0:
    content.append('- Repair broken anchors or update links to match heading text. Use consistent header metadata.')
if orphaned>0:
    content.append('- Review orphaned docs and either link them from the map or move to `docs/archive/`.')

content.append('')
content.append('Detailed findings are written to `docs/_doc_check_results.json` (machine-readable).')

out_file.write_text('\n'.join(content))
print('Wrote', out_file)
