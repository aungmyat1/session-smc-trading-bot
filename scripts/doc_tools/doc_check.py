#!/usr/bin/env python3
import re
import os
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[2]
EXCLUDE_DIRS={'node_modules','.venv','build','dist','coverage','__pycache__','.pytest_cache'}

def is_excluded(path: Path) -> bool:
    return any(part in EXCLUDE_DIRS for part in path.parts)

md_files=[p for p in ROOT.rglob('*.md') if not is_excluded(p.relative_to(ROOT))]
md_paths=[p.relative_to(ROOT).as_posix() for p in md_files]

link_re=re.compile(r"!\[.*?\]\((.*?)\)|\[(?:[^\]]+)\]\(([^)]+)\)")
anchor_re=re.compile(r"#([A-Za-z0-9_\-]+)")

results={
    'total_markdown': len(md_files),
    'checked_files': [],
    'broken_links': [],
    'missing_images': [],
    'missing_files': [],
    'broken_anchors': [],
    'orphaned_files': []
}

# build a map of references to files
refs={p:0 for p in md_paths}

for p in md_files:
    rel=p.relative_to(ROOT).as_posix()
    text=p.read_text(errors='ignore')
    for m in link_re.findall(text):
        target = m[0] or m[1]
        if not target:
            continue
        # skip external
        if target.startswith('http://') or target.startswith('https://') or target.startswith('mailto:'):
            continue
        # remove title part [text](url "title")
        if ' ' in target and '(' not in target:
            # keep as-is
            pass
        # handle anchors within same file
        if target.startswith('#'):
            anchor=target[1:]
            # look for header in this file
            headers=[h.strip() for h in re.findall(r'^#+\s*(.*)$', text, flags=re.M)]
            anchors=[re.sub(r"[^0-9a-z\- ]","",h.lower()).replace(' ','-') for h in headers]
            if anchor not in anchors:
                results['broken_anchors'].append({'file':rel,'target':target})
            continue
        # split file and anchor
        if '#' in target:
            file_part,anchor=target.split('#',1)
        else:
            file_part=target
            anchor=None
        # resolve relative path
        file_path=(p.parent / file_part).resolve()
        try:
            rel_path=file_path.relative_to(ROOT).as_posix()
        except Exception:
            rel_path=None
        if not rel_path or not (ROOT/rel_path).exists():
            results['missing_files'].append({'file':rel,'target':target,'resolved':str(file_path)})
        else:
            refs[rel_path]=refs.get(rel_path,0)+1
            if anchor:
                ttext=(ROOT/rel_path).read_text(errors='ignore')
                headers=[h.strip() for h in re.findall(r'^#+\s*(.*)$', ttext, flags=re.M)]
                anchors=[re.sub(r"[^0-9a-z\- ]","",h.lower()).replace(' ','-') for h in headers]
                if anchor not in anchors:
                    results['broken_anchors'].append({'file':rel,'target':target,'resolved':rel_path})
    # images
    for img in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text):
        if img.startswith('http'):
            continue
        img_path=(p.parent / img).resolve()
        try:
            img_rel=img_path.relative_to(ROOT).as_posix()
        except Exception:
            img_rel=None
        if not img_rel or not (ROOT/img_rel).exists():
            results['missing_images'].append({'file':rel,'target':img,'resolved':str(img_path)})

# orphan detection: files with zero refs (ignore index/README)
for f,c in refs.items():
    if c==0 and not f.lower().endswith(('readme.md','index.md','docs/_full_inventory_files.md')):
        results['orphaned_files'].append(f)

results['checked_files']=md_paths
out=json.dumps(results,indent=2)
print(out)
with open(ROOT/'docs'/'_doc_check_results.json','w') as fh:
    fh.write(out)
