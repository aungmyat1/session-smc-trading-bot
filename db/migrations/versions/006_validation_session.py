"""Add Demo Validation Mode session/lifecycle tables.

Revision ID: 006
Revises: 005

Backs execution/validation_session.py and execution/validation_recorder.py —
the Demo Validation Mode session tracker and per-stage lifecycle recorder.
Distinct from operations.runtime (one row per process start): a validation
session is a longer-lived campaign that must survive runner restarts, so it
needs its own identity and explicit start/end timestamps rather than reusing
the per-process Runtime row.

Tables:
  operations.validation_session         — one row per validation campaign
  operations.validation_lifecycle_event — per-trade, per-stage timing/status
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "validation_session",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", sa.String(100), nullable=False, unique=True),
        sa.Column("operator", sa.String(100), nullable=False),
        sa.Column("broker", sa.String(50), nullable=False),
        sa.Column("account", sa.String(100), nullable=False),
        sa.Column("software_version", sa.String(100), nullable=False),
        sa.Column("git_commit", sa.String(64), nullable=False),
        sa.Column("config_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        schema="operations",
    )

    op.create_table(
        "validation_lifecycle_event",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("validation_session_id", sa.String(100), nullable=False),
        sa.Column("trade_id", sa.String(150), nullable=False),
        sa.Column("stage", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        schema="operations",
    )
    op.create_index(
        "idx_vle_session_trade",
        "validation_lifecycle_event",
        ["validation_session_id", "trade_id"],
        schema="operations",
    )
    op.create_index(
        "idx_vle_session_stage",
        "validation_lifecycle_event",
        ["validation_session_id", "stage"],
        schema="operations",
    )


def downgrade() -> None:
    op.drop_table("validation_lifecycle_event", schema="operations")
    op.drop_table("validation_session", schema="operations")
