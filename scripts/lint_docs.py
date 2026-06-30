#!/usr/bin/env python3
"""
docs/ linter — three checks:

  1. Header compliance: Date, Status, Owner present in first 30 lines of every
     .md under docs/ (excl. Archive/, examples/).  Reported as warnings, does
     NOT fail CI on first pass (use --strict-headers to also fail on this).

  2. Dead link check: every relative Markdown link inside docs/ resolves to a
     real path in the repo.  Fails CI.

  3. Orphan check: every .md under docs/ (excl. Archive/, examples/) is
     reachable from docs/index.md via BFS through relative .md links.
     Directory-level reachability: once any file in a directory is visited, all
     .md files in that same directory are also considered reachable (handles
     strategy sub-files and architecture-review sub-docs that aren't
     individually linked from hubs).  Fails CI.

Usage:
  python scripts/lint_docs.py [--root docs] [--index docs/index.md]
                               [--strict-headers]

Exit code:
  0  all checks pass
  1  dead-link or orphan violations found (or --strict-headers + header issues)
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import unquote

# ── constants ─────────────────────────────────────────────────────────────────

LINK_RE = re.compile(r'\[(?:[^\]]*)\]\(([^)#\s][^)]*)\)')
HEADER_FIELDS = ("Date:", "Status:", "Owner:")
EXCLUDE_DIRS = {"Archive", "examples"}


# ── helpers ───────────────────────────────────────────────────────────────────

def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _relative_md_links(file: Path) -> list[Path]:
    """Extract resolved absolute paths for all relative links in file.

    Skips:
    - Absolute URLs (http/https/mailto)
    - Absolute filesystem paths (leading '/') — machine-specific, not portable
    - Pure anchor links (#...)
    Strips:
    - #fragment suffixes
    - :N integer line-number suffixes (VS Code-style code links)
    """
    results: list[Path] = []
    for raw in LINK_RE.findall(_read(file)):
        raw = raw.split("#")[0].strip()
        if not raw:
            continue
        if raw.startswith(("http://", "https://", "mailto:", "/")):
            continue
        # Strip :N line-number suffix
        raw = re.sub(r":\d+$", "", raw)
        if not raw:
            continue
        decoded = unquote(raw)
        try:
            resolved = (file.parent / decoded).resolve()
        except OSError:
            continue
        results.append(resolved)
    return results


def _collect_md(root: Path) -> set[Path]:
    """All .md files under root, excluding EXCLUDE_DIRS."""
    out: set[Path] = set()
    for p in root.rglob("*.md"):
        parts = {part for part in p.relative_to(root).parts}
        if parts & EXCLUDE_DIRS:
            continue
        out.add(p.resolve())
    return out


# ── check 1: header compliance ────────────────────────────────────────────────

def check_headers(root: Path) -> list[str]:
    violations: list[str] = []
    for f in sorted(_collect_md(root)):
        preview = "\n".join(_read(f).splitlines()[:30])
        missing = [field for field in HEADER_FIELDS if field not in preview]
        if missing:
            rel = f.relative_to(root.parent)
            violations.append(f"{rel}: missing header fields: {', '.join(missing)}")
    return violations


# ── check 2: dead links ───────────────────────────────────────────────────────

def check_dead_links(root: Path) -> list[str]:
    violations: list[str] = []
    for f in sorted(root.rglob("*.md")):
        rel = f.relative_to(root.parent)
        for target in _relative_md_links(f):
            if not target.exists():
                violations.append(f"{rel}: dead link → {target.relative_to(root.parent.resolve())}")
    return violations


# ── check 3: orphan check ─────────────────────────────────────────────────────

def check_orphans(root: Path, index: Path) -> list[str]:
    """
    BFS from index.  Directory-level reachability: when a file is visited,
    all .md siblings in its directory are also marked reachable.  This lets
    strategy sub-files (flow.md, parameters.md …) become reachable once any
    file in their directory is linked.
    """
    all_docs = _collect_md(root)
    reachable: set[Path] = set()
    queue: list[Path] = [index.resolve()]
    visited: set[Path] = set()

    while queue:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)

        # Mark file + all .md siblings as reachable
        reachable.add(current)
        for sibling in current.parent.glob("*.md"):
            s = sibling.resolve()
            if s not in reachable:
                reachable.add(s)
                if s not in visited:
                    queue.append(s)

        # Follow relative .md links
        for target in _relative_md_links(current):
            if target.suffix == ".md" and target not in visited:
                queue.append(target)

    orphans = sorted(all_docs - reachable)
    return [str(o.relative_to(root.parent)) for o in orphans]


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root",           default="docs",        help="docs root directory")
    parser.add_argument("--index",          default="docs/index.md", help="navigation index file")
    parser.add_argument("--strict-headers", action="store_true",   help="also fail on missing headers")
    args = parser.parse_args()

    repo_root = Path.cwd()
    docs_root = (repo_root / args.root).resolve()
    index_path = (repo_root / args.index).resolve()

    if not docs_root.is_dir():
        print(f"ERROR: docs root not found: {docs_root}", file=sys.stderr)
        return 1
    if not index_path.exists():
        print(f"ERROR: index not found: {index_path}", file=sys.stderr)
        return 1

    exit_code = 0

    # Check 1 — headers (warn; fail only with --strict-headers)
    header_violations = check_headers(docs_root)
    if header_violations:
        tag = "FAIL" if args.strict_headers else "WARN"
        print(f"\n[Header compliance — {tag}] {len(header_violations)} file(s):")
        for v in header_violations:
            print(f"  {v}")
        if args.strict_headers:
            exit_code = 1
    else:
        print("[Header compliance — PASS] all docs have Date/Status/Owner")

    # Check 2 — dead links (always fail)
    dead_violations = check_dead_links(docs_root)
    if dead_violations:
        print(f"\n[Dead links — FAIL] {len(dead_violations)} broken link(s):")
        for v in dead_violations:
            print(f"  {v}")
        exit_code = 1
    else:
        print("[Dead links — PASS] all relative links resolve")

    # Check 3 — orphans (always fail)
    orphan_violations = check_orphans(docs_root, index_path)
    if orphan_violations:
        print(f"\n[Orphan check — FAIL] {len(orphan_violations)} unreachable doc(s):")
        for v in orphan_violations:
            print(f"  {v}")
        exit_code = 1
    else:
        print("[Orphan check — PASS] all docs reachable from docs/index.md")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
