"""Baseline schema v2 — mark existing tables as already applied.

This migration contains no DDL operations. It exists solely to anchor
the Alembic revision history against the schema that was applied by
running db/schema_v2.sql directly before Alembic was introduced.

After stamping a fresh database with ``alembic stamp 001``, migration 002
can be applied to add the v3 control-plane tables.

Revision ID: 001
Revises: None
Create Date: 2026-06-29
"""
from __future__ import annotations
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    No-op.  The v2 schema (market, research, analytics, config) was applied
    by db/schema_v2.sql before Alembic was introduced.  Stamp the database
    with ``alembic stamp 001`` to record this fact, then run ``alembic upgrade
    head`` to apply migration 002.
    """


def downgrade() -> None:
    """
    No-op.  To revert the entire database, drop all schemas manually.
    """
