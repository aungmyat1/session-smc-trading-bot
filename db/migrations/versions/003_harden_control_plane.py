"""Harden control-plane lineage, transitions, reports, and legacy imports.

Revision ID: 003
Revises: 002
Create Date: 2026-06-29
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op


revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stage_transition",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("strategy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("strategy.strategy.id"), nullable=False),
        sa.Column("version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("strategy.version.id"), nullable=False),
        sa.Column("gate_decision_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("governance.gate_decision.id"), nullable=False, unique=True),
        sa.Column("from_stage", sa.String(50), nullable=False),
        sa.Column("to_stage", sa.String(50), nullable=False),
        sa.Column("from_revision", sa.Integer(), nullable=False),
        sa.Column("to_revision", sa.Integer(), nullable=False),
        sa.Column("actor", sa.String(100), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("transitioned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("to_revision = from_revision + 1", name="ck_stage_transition_revision"),
        schema="governance",
    )
    op.create_index("idx_transition_strategy_time", "stage_transition", ["strategy_id", "transitioned_at"], schema="governance")

    op.add_column("binding", sa.Column("trust", sa.String(30), nullable=False, server_default="LEGACY_IMPORTED"), schema="evidence")
    op.add_column("binding", sa.Column("invalidated_at", sa.DateTime(timezone=True)), schema="evidence")
    op.add_column("binding", sa.Column("invalidation_reason", sa.Text()), schema="evidence")
    op.create_check_constraint(
        "ck_binding_trust",
        "binding",
        "trust IN ('QUALIFYING_REAL','SYNTHETIC','LEGACY_IMPORTED','INVALIDATED')",
        schema="evidence",
    )

    op.create_table(
        "report_record",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("report_id", sa.String(200), nullable=False, unique=True),
        sa.Column("strategy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("strategy.strategy.id"), nullable=False),
        sa.Column("version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("strategy.version.id"), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("research.run.id")),
        sa.Column("stage", sa.String(50), nullable=False),
        sa.Column("report_type", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("trust", sa.String(30), nullable=False),
        sa.Column("json_artifact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("evidence.artifact.id"), nullable=False),
        sa.Column("markdown_artifact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("evidence.artifact.id")),
        sa.Column("schema_version", sa.String(20), nullable=False),
        sa.Column("generator_version", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("status IN ('PASS','FAIL','BLOCKED','IN_PROGRESS','NOT_RUN','INVALIDATED')", name="ck_report_status"),
        sa.CheckConstraint("trust IN ('QUALIFYING_REAL','SYNTHETIC','LEGACY_IMPORTED','INVALIDATED')", name="ck_report_trust"),
        schema="evidence",
    )
    op.create_index("idx_report_lookup", "report_record", ["strategy_id", "version_id", "stage", "created_at"], schema="evidence")

    op.create_table(
        "legacy_import",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("source_timestamp", sa.DateTime(timezone=True)),
        sa.Column("record_type", sa.String(50), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("imported_by", sa.String(100), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("source_path", "source_sha256", "record_type", name="uq_legacy_import_source"),
        schema="evidence",
    )


def downgrade() -> None:
    op.drop_table("legacy_import", schema="evidence")
    op.drop_table("report_record", schema="evidence")
    op.drop_constraint("ck_binding_trust", "binding", schema="evidence", type_="check")
    op.drop_column("binding", "invalidation_reason", schema="evidence")
    op.drop_column("binding", "invalidated_at", schema="evidence")
    op.drop_column("binding", "trust", schema="evidence")
    op.drop_table("stage_transition", schema="governance")
