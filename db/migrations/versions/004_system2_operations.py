"""Add complete System 2 operational records.

Revision ID: 004
Revises: 003
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _record(name: str, *columns: sa.Column) -> None:
    op.create_table(
        name,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        *columns,
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema="operations",
    )


def upgrade() -> None:
    _record("runtime", sa.Column("runtime_id", sa.String(100), nullable=False), sa.Column("status", sa.String(30), nullable=False))
    _record("market_data_health", sa.Column("symbol", sa.String(20), nullable=False), sa.Column("status", sa.String(30), nullable=False))
    _record("intent", sa.Column("intent_id", sa.String(150), nullable=False, unique=True), sa.Column("symbol", sa.String(20), nullable=False))
    _record("risk_decision", sa.Column("intent_id", sa.String(150), nullable=False), sa.Column("approved", sa.Boolean(), nullable=False))
    _record("order_record", sa.Column("order_id", sa.String(150)), sa.Column("idempotency_key", sa.String(200), nullable=False, unique=True), sa.Column("status", sa.String(40), nullable=False))
    _record("fill", sa.Column("order_id", sa.String(150), nullable=False), sa.Column("status", sa.String(40), nullable=False))
    _record("position_record", sa.Column("symbol", sa.String(20), nullable=False), sa.Column("status", sa.String(40), nullable=False))
    _record("reconciliation", sa.Column("runtime_id", sa.String(100), nullable=False), sa.Column("consistent", sa.Boolean(), nullable=False))
    _record("recovery_checkpoint", sa.Column("runtime_id", sa.String(100), nullable=False), sa.Column("state", postgresql.JSONB(), nullable=False))
    _record("execution_event", sa.Column("event_type", sa.String(80), nullable=False))
    op.create_index("idx_execution_event_created", "execution_event", ["created_at"], schema="operations")
    op.create_index("idx_checkpoint_runtime_created", "recovery_checkpoint", ["runtime_id", "created_at"], schema="operations")


def downgrade() -> None:
    for name in reversed(("runtime", "market_data_health", "intent", "risk_decision", "order_record", "fill", "position_record", "reconciliation", "recovery_checkpoint", "execution_event")):
        op.drop_table(name, schema="operations")
