#!/usr/bin/env python3
"""Phase 1: Repair anchors and missing references, and generate reports.

Usage: run from repo root:
  python3 scripts/doc_tools/phase1_repair.py
"""
import json
import os
import re
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / 'docs'
RESULTS = DOCS / '_doc_check_results.json'


def slugify(text):
    # GitHub-style slug (approx): lowercase, remove punctuation, replace spaces with '-'
    s = text.strip().lower()
    s = re.sub(r"[^\n\w\- ]+", "", s)
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s


def collect_headings(path):
    headings = []
    try:
        txt = Path(path).read_text(encoding='utf-8')
    except Exception:
        return headings
    for line in txt.splitlines():
        m = re.match(r'^(#{1,6})\s+(.*)$', line)
        if m:
            level = len(m.group(1))
            text = m.group(2).strip()
            headings.append((level, text, slugify(text)))
    return headings


def relpath(from_path, to_path):
    try:
        return os.path.relpath(to_path, start=os.path.dirname(from_path))
    except Exception:
        return to_path


def repair_anchors(data):
    repairs = []
    for entry in data.get('broken_anchors', []):
        ref_file = ROOT / entry['file']
        target = entry.get('target', '')
        if '#' in target:
            tgt_path, anchor = target.split('#', 1)
        else:
            tgt_path, anchor = target, ''
        # Normalize percent-encoding
        tgt_path = unquote(tgt_path)

        # If anchor is a line number like L123, drop it (local viewers don't need it)
        if re.match(r'^L\d+$', anchor):
            new_target = tgt_path
        else:
            # If target is a markdown file, try to compute canonical slug
            tgt_full = (ROOT / tgt_path).resolve() if tgt_path and not tgt_path.startswith('http') else None
            if tgt_path.endswith('.md') and tgt_full and tgt_full.exists():
                headings = collect_headings(tgt_full)
                slugs = [h[2] for h in headings]
                if anchor in slugs:
                    new_target = f"{tgt_path}#{anchor}"
                else:
                    # fallback: use first heading if available
                    if slugs:
                        new_target = f"{tgt_path}#{slugs[0]}"
                    else:
                        new_target = tgt_path
            else:
                new_target = tgt_path

        # Apply replacement in referring file
        try:
            txt = ref_file.read_text(encoding='utf-8')
        except Exception:
            continue
        if target == new_target:
            continue
        # replace occurrences of the exact target (with or without ./ prefix)
        replaced = False
        patterns = [target, './' + target.lstrip('./')]
        for p in patterns:
            if p in txt:
                txt = txt.replace(p, new_target)
                replaced = True
        if replaced:
            ref_file.write_text(txt, encoding='utf-8')
            repairs.append({'file': entry['file'], 'old': target, 'new': new_target})

    return repairs


def classify_and_fix_missing(data):
    repo_files = []
    for root, dirs, files in os.walk(ROOT):
        for f in files:
            repo_files.append(os.path.relpath(os.path.join(root, f), ROOT))

    classifications = []
    for entry in data.get('missing_files', []):
        ref = entry['file']
        target = entry['target']
        tgt_path = target.split('#', 1)[0]
        tgt_path = unquote(tgt_path)
        matches = [p for p in repo_files if os.path.basename(p) == os.path.basename(tgt_path)]
        classification = 'unknown'
        chosen = None
        if os.path.exists(ROOT / tgt_path):
            classification = 'exists'
            chosen = tgt_path
        elif matches:
            classification = 'moved_or_renamed'
            chosen = matches[0]
        else:
            # try decode percent-encoded path variants
            alt = tgt_path.replace('%20', ' ')
            if os.path.exists(ROOT / alt):
                classification = 'moved_or_renamed'
                chosen = alt
            else:
                classification = 'deleted_or_generated'

        # attempt in-file replacement if we have a candidate
        if chosen:
            ref_file = ROOT / ref
            try:
                txt = ref_file.read_text(encoding='utf-8')
                if target in txt:
                    txt = txt.replace(target, chosen)
                    ref_file.write_text(txt, encoding='utf-8')
            except Exception:
                pass

        classifications.append({'file': ref, 'target': target, 'classification': classification, 'resolved_to': chosen})

    return classifications


def generate_graph(data, out_path):
    lines = ['# Documentation Graph', '']
    for f in data.get('checked_files', []):
        lines.append(f'- {f}')
    lines.append('')
    lines.append('## Missing file references (from scan)')
    for m in data.get('missing_files', []):
        lines.append(f"- {m['file']} -> {m['target']}")
    out_path.write_text('\n'.join(lines), encoding='utf-8')


def generate_index(docs_dir, out_path):
    lines = ['# Documentation INDEX', '']
    for root, dirs, files in os.walk(docs_dir):
        rel = os.path.relpath(root, docs_dir)
        if rel == '.':
            rel = ''
        if files:
            lines.append(f'## {rel or "root"}')
            for f in sorted(files):
                if f.endswith('.md'):
                    p = os.path.join(rel, f).lstrip('./')
                    lines.append(f'- [{f}]({p})')
            lines.append('')
    out_path.write_text('\n'.join(lines), encoding='utf-8')


def main():
    if not RESULTS.exists():
        print('No scan results found at', RESULTS)
        return
    data = json.loads(RESULTS.read_text(encoding='utf-8'))

    print('Repairing anchors...')
    repairs = repair_anchors(data)
    print('Anchor repairs:', len(repairs))
    (DOCS / 'anchor_repair_report.md').write_text(json.dumps(repairs, indent=2), encoding='utf-8')

    print('Classifying and attempting to fix missing files...')
    classes = classify_and_fix_missing(data)
    print('Classifications:', len(classes))
    (DOCS / 'missing_reference_report.md').write_text(json.dumps(classes, indent=2), encoding='utf-8')

    print('Generating documentation graph and INDEX...')
    generate_graph(data, DOCS / 'documentation_graph.md')
    generate_index(DOCS, DOCS / 'INDEX.md')

    print('Done. Updated reports written to docs/. Re-run the doc scanner next.')


if __name__ == '__main__':
    main()
