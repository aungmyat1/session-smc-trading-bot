#!/usr/bin/env python3
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
res_file=ROOT/'docs'/'_doc_check_results.json'
out_file=ROOT/'docs'/'archive_candidates.md'

if not res_file.exists():
    print('No results file found:', res_file)
    raise SystemExit(1)

data=json.loads(res_file.read_text())
orphaned=data.get('orphaned_files',[])

# filter orphaned files under docs/ (non-archive)
candidates=[f for f in orphaned if f.startswith('docs/') and 'Archive' not in f and 'archive/' not in f]

content=['# Archive Candidates','']
content.append('The following orphaned documentation files were detected by the automated scan. These are *candidates* for archival — DO NOT MOVE THEM AUTOMATICALLY. Review each and confirm before relocating to `docs/archive/`.')
content.append('')
for c in sorted(candidates):
    content.append('- ' + c)

if not candidates:
    content.append('No candidates found under `docs/`.')

out_file.write_text('\n'.join(content))
print('Wrote', out_file)
