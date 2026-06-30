from __future__ import annotations

from scripts.control_plane_backup import _libpq_environment


def test_backup_credentials_are_not_required_in_command_arguments() -> None:
    environment = _libpq_environment(
        "postgresql://operator:secret@db.internal:5433/svos"
    )
    assert environment["PGPASSWORD"] == "secret"
    assert environment["PGHOST"] == "db.internal"
    assert environment["PGDATABASE"] == "svos"
