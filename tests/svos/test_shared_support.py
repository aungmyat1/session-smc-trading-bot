"""Tests for svos/shared/support.py"""
from __future__ import annotations

import json


from svos.shared.support import (
    append_jsonl,
    ensure_parent,
    file_sha1,
    now_iso,
    read_json,
    read_jsonl,
    stable_manifest_hash,
    write_json,
)


def test_now_iso_returns_utc_iso_format():
    result = now_iso()
    assert "T" in result
    assert result.endswith("+00:00")


def test_ensure_parent_creates_dirs(tmp_path):
    target = tmp_path / "a" / "b" / "c" / "file.txt"
    ensure_parent(target)
    assert (tmp_path / "a" / "b" / "c").is_dir()


def test_read_json_returns_default_when_missing(tmp_path):
    path = tmp_path / "nonexistent.json"
    result = read_json(path, {"default": True})
    assert result == {"default": True}


def test_read_json_returns_default_on_invalid_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("not json!", encoding="utf-8")
    result = read_json(path, [])
    assert result == []


def test_read_json_returns_content(tmp_path):
    path = tmp_path / "data.json"
    path.write_text(json.dumps({"key": "value"}), encoding="utf-8")
    result = read_json(path, {})
    assert result == {"key": "value"}


def test_write_json_creates_file(tmp_path):
    path = tmp_path / "sub" / "out.json"
    write_json(path, {"result": 42})
    assert path.exists()
    assert json.loads(path.read_text()) == {"result": 42}


def test_write_json_overwrites(tmp_path):
    path = tmp_path / "out.json"
    write_json(path, {"v": 1})
    write_json(path, {"v": 2})
    assert json.loads(path.read_text())["v"] == 2


def test_append_jsonl_creates_and_appends(tmp_path):
    path = tmp_path / "events.jsonl"
    append_jsonl(path, {"event": "first"})
    append_jsonl(path, {"event": "second"})
    lines = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    assert len(lines) == 2
    assert lines[0]["event"] == "first"
    assert lines[1]["event"] == "second"


def test_read_jsonl_missing_file(tmp_path):
    result = read_jsonl(tmp_path / "missing.jsonl")
    assert result == []


def test_read_jsonl_skips_invalid_lines(tmp_path):
    path = tmp_path / "data.jsonl"
    path.write_text('{"a": 1}\nnot valid json\n{"b": 2}\n', encoding="utf-8")
    result = read_jsonl(path)
    assert len(result) == 2
    assert result[0]["a"] == 1
    assert result[1]["b"] == 2


def test_read_jsonl_skips_non_dict_lines(tmp_path):
    path = tmp_path / "data.jsonl"
    path.write_text('["array"]\n{"key": "val"}\n42\n', encoding="utf-8")
    result = read_jsonl(path)
    assert len(result) == 1
    assert result[0]["key"] == "val"


def test_read_jsonl_skips_blank_lines(tmp_path):
    path = tmp_path / "data.jsonl"
    path.write_text('\n\n{"x": 1}\n\n', encoding="utf-8")
    result = read_jsonl(path)
    assert len(result) == 1


def test_stable_manifest_hash_deterministic():
    payload = {"a": 1, "b": [1, 2, 3]}
    h1 = stable_manifest_hash(payload)
    h2 = stable_manifest_hash(payload)
    assert h1 == h2
    assert isinstance(h1, str)
    assert len(h1) in (40, 64)  # SHA-1 (40) or SHA-256 (64)


def test_stable_manifest_hash_changes_on_content():
    h1 = stable_manifest_hash({"key": "a"})
    h2 = stable_manifest_hash({"key": "b"})
    assert h1 != h2


def test_file_sha1_returns_empty_for_missing(tmp_path):
    result = file_sha1(tmp_path / "missing.txt")
    assert result == ""


def test_file_sha1_returns_empty_for_directory(tmp_path):
    result = file_sha1(tmp_path)
    assert result == ""


def test_file_sha1_computes_hash(tmp_path):
    path = tmp_path / "file.txt"
    path.write_bytes(b"hello world")
    result = file_sha1(path)
    assert len(result) == 40
    assert result == file_sha1(path)  # deterministic


def test_file_sha1_differs_on_content(tmp_path):
    p1 = tmp_path / "a.txt"
    p2 = tmp_path / "b.txt"
    p1.write_bytes(b"content A")
    p2.write_bytes(b"content B")
    assert file_sha1(p1) != file_sha1(p2)
