"""Create or adopt the idempotent v2 baseline schema.

The canonical v2 SQL uses ``IF NOT EXISTS`` and conflict-safe seeds, so the
same revision supports both an empty database and a database that previously
received ``db/schema_v2.sql`` manually. Existing installations should run
``alembic upgrade head``; they must not stamp past this validation step.

Revision ID: 001
Revises: None
Create Date: 2026-06-29
"""

from __future__ import annotations
from pathlib import Path
from typing import Sequence, Union

from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    schema_path = Path(__file__).resolve().parents[2] / "schema_v2.sql"
    op.execute(schema_path.read_text(encoding="utf-8"))


def downgrade() -> None:
    """
    No-op.  To revert the entire database, drop all schemas manually.
    """
