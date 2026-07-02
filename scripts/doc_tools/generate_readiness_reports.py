#!/usr/bin/env python3
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
res_file=ROOT/'docs'/'_doc_check_results.json'
out_doc=ROOT/'docs'/'documentation_readiness_report.md'
out_repo=ROOT/'docs'/'repository_readiness_report.md'

if not res_file.exists():
    print('No results file found:', res_file)
    raise SystemExit(1)

data=json.loads(res_file.read_text())

total=data.get('total_markdown',0)
issues = len(data.get('missing_files',[])) + len(data.get('missing_images',[])) + len(data.get('broken_anchors',[]))
orphaned=len(data.get('orphaned_files',[]))

# simple readiness metric: fraction of files without direct issues
problem_files_set = set([x.get('file') for x in data.get('missing_files',[])])
problem_files_set.update([x.get('file') for x in data.get('missing_images',[])])
problem_files_set.update([x.get('file') for x in data.get('broken_anchors',[])])
num_problem_files = len([f for f in data.get('checked_files',[]) if f in problem_files_set])

readiness_pct = max(0, round(100.0 * (1 - (len(problem_files_set)+orphaned)/max(1,total)),2))

doc_lines=[]
doc_lines.append('# Documentation Readiness Report')
doc_lines.append('')
doc_lines.append(f'- Total markdown files: **{total}**')
doc_lines.append(f'- Files with broken refs/images/anchors: **{len(problem_files_set)}**')
doc_lines.append(f'- Orphaned documents: **{orphaned}**')
doc_lines.append(f'- High-level readiness estimate: **{readiness_pct}%**')
doc_lines.append('')
doc_lines.append('Key recommendations:')
doc_lines.append('')
doc_lines.append('- Prioritise fixing `missing_files` for top-level runbooks and `README.md`.')
doc_lines.append('- Repair broken anchors and standardize headings (use the metadata header added).')
doc_lines.append('- Review `docs/archive_candidates.md` and confirm archival moves.')
doc_lines.append('- Add owners and last-reviewed dates to remaining high-value docs.')

out_doc.write_text('\n'.join(doc_lines))

repo_lines=[]
repo_lines.append('# Repository Readiness Report')
repo_lines.append('')
repo_lines.append('This report summarises documentation readiness in the repository and next actions for achieving the documentation acceptance criteria.')
repo_lines.append('')
repo_lines.append(f'- Documentation readiness (per docs scan): **{readiness_pct}%**')
repo_lines.append('- Required: ≥95% to pass the audit')
repo_lines.append('')
repo_lines.append('Action plan:')
repo_lines.append('')
repo_lines.append('1. Fix top 50 missing file references and broken anchors. (owner: Documentation Team)')
repo_lines.append('2. Review and archive confirmed legacy artifacts. (owner: Architecture Team)')
repo_lines.append('3. Re-run documentation integrity scan and confirm readiness >=95%.')

out_repo.write_text('\n'.join(repo_lines))

print('Wrote', out_doc, 'and', out_repo)
