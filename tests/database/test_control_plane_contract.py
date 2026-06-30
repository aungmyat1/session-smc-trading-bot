from __future__ import annotations

from pathlib import Path

from db.control_plane import TransitionCommand
from db.models import ArtifactBinding, StageTransition

ROOT = Path(__file__).resolve().parents[2]


def test_control_plane_models_include_revision_and_trust_guards() -> None:
    assert {"from_revision", "to_revision", "gate_decision_id"}.issubset(
        StageTransition.__table__.columns.keys()
    )
    assert {"trust", "invalidated_at", "invalidation_reason"}.issubset(
        ArtifactBinding.__table__.columns.keys()
    )


def test_transition_command_is_immutable() -> None:
    assert TransitionCommand.__dataclass_params__.frozen is True


def test_control_plane_has_no_yaml_or_jsonl_fallback() -> None:
    source = (ROOT / "db/control_plane.py").read_text(encoding="utf-8")
    assert "import yaml" not in source.lower()
    assert "append_jsonl" not in source
    assert "with_for_update()" in source
    assert "session.begin()" in source
