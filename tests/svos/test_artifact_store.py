from __future__ import annotations

from pathlib import Path

from svos.adapters.artifacts import FilesystemArtifactStore


def test_artifact_store_is_content_addressed_and_idempotent(tmp_path: Path) -> None:
    source = tmp_path / "report.json"
    source.write_text('{"status":"PASS"}', encoding="utf-8")
    store = FilesystemArtifactStore(tmp_path / "artifacts")

    first = store.put(source)
    second = store.put(source)

    assert first == second
    assert first.path.name == first.sha256
    assert first.path.parent.name == first.sha256[:2]
    assert store.verify(first)
    assert first.path.stat().st_mode & 0o222 == 0
