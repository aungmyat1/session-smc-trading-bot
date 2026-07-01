from __future__ import annotations

from pathlib import Path

from scripts.check_docs_drift import check_repo


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_check_docs_drift_passes_for_repo_files():
    assert check_repo(Path.cwd()) == []


def test_check_docs_drift_detects_magic_and_pair_mismatch(tmp_path: Path):
    _write(
        tmp_path / "CLAUDE.md",
        """
## §5 — BROKER / AUTH

- Magic number: flat 21001
- Live-traded pairs: EURUSD, GBPUSD
""".strip()
        + "\n",
    )
    _write(
        tmp_path / "config" / "demo.yaml",
        """
execution:
  magic_number: 21099
trading:
  allowed_pairs:
    - EURUSD
    - GBPUSD
    - XAUUSD
""".strip()
        + "\n",
    )
    _write(
        tmp_path / "scripts" / "run_st_a2_demo.py",
        'PAIRS = ["EURUSD", "GBPUSD", "XAUUSD"]\n',
    )

    issues = check_repo(tmp_path)

    assert any("magic number mismatch" in issue for issue in issues)
    assert any("live-traded pairs mismatch" in issue for issue in issues)
