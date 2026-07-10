"""Add durable risk/portfolio state tables.

Revision ID: 005
Revises: 004

Replaces the JSON-file-based risk/portfolio persistence with transactional
Postgres storage.  See SYSTEM2_MASTER_PLAN.md Phase 2 — "durable transactional
risk/portfolio ledger".

Tables:
  operations.risk_portfolio_state   — current state, upserted per (state_type, period_date)
  operations.risk_portfolio_history — append-only audit trail of significant state changes
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Current-state table: one row per (state_type, period_date) — upserted atomically.
    op.create_table(
        "risk_portfolio_state",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("runtime_id", sa.String(100), nullable=False),
        sa.Column("state_type", sa.String(20), nullable=False),
        sa.Column("state_data", postgresql.JSONB(), nullable=False),
        sa.Column("period_date", sa.Date(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.UniqueConstraint("state_type", "period_date",
                            name="uq_risk_portfolio_state_type_date"),
        schema="operations",
    )
    op.create_index(
        "idx_rps_type_date",
        "risk_portfolio_state",
        ["state_type", "period_date"],
        schema="operations",
    )

    # Append-only history: every trade_close, daily_reset, startup_restore
    # creates a row for audit/debugging.
    op.create_table(
        "risk_portfolio_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("runtime_id", sa.String(100), nullable=False),
        sa.Column("state_type", sa.String(20), nullable=False),
        sa.Column("event", sa.String(50), nullable=False),
        sa.Column("state_data", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        schema="operations",
    )
    op.create_index(
        "idx_rph_created",
        "risk_portfolio_history",
        ["created_at"],
        schema="operations",
    )


def downgrade() -> None:
    op.drop_table("risk_portfolio_history", schema="operations")
    op.drop_table("risk_portfolio_state", schema="operations")
