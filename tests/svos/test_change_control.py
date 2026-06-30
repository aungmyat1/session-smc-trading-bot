from __future__ import annotations

import json
from pathlib import Path

import yaml

from svos.shared import change_control


def test_build_change_record_uses_runtime_strategy_when_present(tmp_path: Path, monkeypatch):
    root = tmp_path
    (root / "config").mkdir(parents=True, exist_ok=True)
    (root / "config" / "strategy_catalog.yaml").write_text(
        yaml.safe_dump(
            {
                "current_strategy": None,
                "strategies": {
                    "SMCOrderBlockFVGSession": {
                        "status": "draft",
                        "svos_stage": "INTAKE",
                    }
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (root / "logs").mkdir(parents=True, exist_ok=True)
    (root / "logs" / "strategy_demo_state.json").write_text(
        json.dumps(
            {
                "strategy": "SMCOrderBlockFVGSession",
                "status": "running",
                "updated_at": "2026-06-30T08:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    (root / "logs" / "strategy_demo.log").write_text("latest line\n", encoding="utf-8")

    def fake_run(args: list[str], cwd: Path):
        class Result:
            def __init__(self, stdout: str):
                self.stdout = stdout

        if args[:3] == ["git", "rev-parse", "--abbrev-ref"]:
            return Result("main\n")
        if args[:2] == ["git", "rev-parse"]:
            return Result("abc123\n")
        if args[:2] == ["git", "status"]:
            return Result(" M docs/CHANGE_CONTROL_SYSTEM.md\n")
        if args[:2] == ["ps", "-ef"]:
            return Result("/usr/bin/python3 scripts/run_strategy_demo.py --strategy SMCOrderBlockFVGSession\n")
        raise AssertionError(args)

    monkeypatch.setattr(change_control, "_run", fake_run)

    record = change_control.build_change_record(
        root=root,
        actor="tester",
        change_type="runtime_snapshot",
        status="observed",
        summary="checked runtime",
    )

    assert record.strategy == "SMCOrderBlockFVGSession"
    assert record.lifecycle_stage == "INTAKE"
    assert record.runtime["runner_active"] is True
    assert record.repo["dirty"] is True


def test_write_change_record_creates_json_markdown_and_index(tmp_path: Path, monkeypatch):
    root = tmp_path
    (root / "config").mkdir(parents=True, exist_ok=True)
    (root / "config" / "strategy_catalog.yaml").write_text(
        yaml.safe_dump({"current_strategy": None, "strategies": {}}, sort_keys=False),
        encoding="utf-8",
    )
    (root / "logs").mkdir(parents=True, exist_ok=True)

    def fake_run(args: list[str], cwd: Path):
        class Result:
            def __init__(self, stdout: str):
                self.stdout = stdout

        if args[:3] == ["git", "rev-parse", "--abbrev-ref"]:
            return Result("main\n")
        if args[:2] == ["git", "rev-parse"]:
            return Result("def456\n")
        if args[:2] == ["git", "status"]:
            return Result("")
        if args[:2] == ["ps", "-ef"]:
            return Result("")
        raise AssertionError(args)

    monkeypatch.setattr(change_control, "_run", fake_run)

    record = change_control.build_change_record(
        root=root,
        actor="tester",
        change_type="repo_change",
        status="verified",
        summary="implemented change-control system",
        affected_files=["scripts/document_change.py", "docs/CHANGE_CONTROL_SYSTEM.md"],
        verification_steps=["python3 -m pytest tests/svos/test_change_control.py -q"],
    )
    output_root = root / "reports" / "change_control"
    json_path, md_path = change_control.write_change_record(root, record, output_root)

    assert json_path.exists()
    assert md_path.exists()
    index = json.loads((output_root / "index.json").read_text(encoding="utf-8"))
    assert index["records"][0]["event_id"] == record.event_id
    markdown = md_path.read_text(encoding="utf-8")
    assert "Runner Active: `False`" in markdown
    assert "implemented change-control system" in markdown
