"""Add v3 control-plane schemas: strategy, governance, evidence, experiments,
robustness, execution, operations; plus research.run, research.metric,
analytics.stage_gate; fix ORM drift (market.candles, analytics.optimization_results,
config.system_config).

Revision ID: 002
Revises: 001
Create Date: 2026-06-29
"""
from __future__ import annotations
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── helpers ───────────────────────────────────────────────────────────────

def _create_schemas() -> None:
    for schema in (
        "strategy", "governance", "evidence",
        "experiments", "robustness", "execution", "operations",
    ):
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")


def _drop_schemas() -> None:
    for schema in (
        "operations", "execution", "robustness",
        "experiments", "evidence", "governance", "strategy",
    ):
        op.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")


# ═══════════════════════════════════════════════════════════════════════════
# upgrade
# ═══════════════════════════════════════════════════════════════════════════

def upgrade() -> None:
    # ── prerequisites ────────────────────────────────────────────────────
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    _create_schemas()

    # The three D-03 tables (candles, optimization_results, system_config)
    # are part of revision 001. Revision 002 only adds control-plane objects.

    # ── strategy schema ──────────────────────────────────────────────────
    op.create_table(
        "strategy",
        sa.Column("id",         postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("name",       sa.String(100), nullable=False, unique=True),
        sa.Column("slug",       sa.String(100), nullable=False, unique=True),
        sa.Column("owner",      sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        schema="strategy",
    )

    op.create_table(
        "version",
        sa.Column("id",            postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("strategy_id",   postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("strategy.strategy.id"), nullable=False),
        sa.Column("version",       sa.String(30), nullable=False),
        sa.Column("spec_hash",     sa.String(64), nullable=False),
        sa.Column("parent_id",     postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("strategy.version.id")),
        sa.Column("source_commit", sa.String(40)),
        sa.Column("rules_json",    postgresql.JSONB(), nullable=False),
        sa.Column("notes",         sa.Text()),
        sa.Column("created_by",    sa.String(100)),
        sa.Column("created_at",    sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.UniqueConstraint("strategy_id", "version"),
        schema="strategy",
    )
    op.create_index("idx_sv_strategy_id", "version", ["strategy_id"], schema="strategy")

    # ── governance schema ────────────────────────────────────────────────
    op.create_table(
        "stage_state",
        sa.Column("id",                  postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("strategy_id",         postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("strategy.strategy.id"), nullable=False, unique=True),
        sa.Column("current_stage",       sa.String(50), nullable=False),
        sa.Column("current_version_id",  postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("strategy.version.id")),
        sa.Column("opt_lock",            sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at",          sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_by",          sa.String(100)),
        schema="governance",
    )

    op.create_table(
        "gate_decision",
        sa.Column("id",             postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("strategy_id",    postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("strategy.strategy.id"), nullable=False),
        sa.Column("version_id",     postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("strategy.version.id")),
        sa.Column("from_stage",     sa.String(50), nullable=False),
        sa.Column("to_stage",       sa.String(50), nullable=False),
        sa.Column("allowed",        sa.Boolean(), nullable=False),
        sa.Column("actor",          sa.String(100), nullable=False),
        sa.Column("reason",         sa.Text()),
        sa.Column("blockers",       postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("evidence_ids",   postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("policy_version", sa.String(20)),
        sa.Column("decided_at",     sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        schema="governance",
    )
    op.create_index("idx_gd_strategy_id", "gate_decision", ["strategy_id"], schema="governance")
    op.create_index("idx_gd_decided_at",  "gate_decision", ["decided_at"],  schema="governance")

    op.create_table(
        "approval",
        sa.Column("id",               postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("strategy_id",      postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("strategy.strategy.id"), nullable=False),
        sa.Column("version_id",       postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("strategy.version.id")),
        sa.Column("gate_decision_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("governance.gate_decision.id")),
        sa.Column("from_stage",       sa.String(50), nullable=False),
        sa.Column("to_stage",         sa.String(50), nullable=False),
        sa.Column("approver",         sa.String(100), nullable=False),
        sa.Column("approver_role",    sa.String(50)),
        sa.Column("reason",           sa.Text(), nullable=False),
        sa.Column("approved_at",      sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("expires_at",       sa.DateTime(timezone=True)),
        sa.Column("revoked_at",       sa.DateTime(timezone=True)),
        schema="governance",
    )
    op.create_index("idx_appr_strategy_id", "approval", ["strategy_id"], schema="governance")

    op.create_table(
        "outbox",
        sa.Column("id",           sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("event_type",   sa.String(100), nullable=False),
        sa.Column("strategy_id",  postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("strategy.strategy.id")),
        sa.Column("payload",      postgresql.JSONB(), nullable=False),
        sa.Column("created_at",   sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        schema="governance",
    )
    op.create_index(
        "idx_outbox_pending", "outbox", ["processed_at"],
        postgresql_where=sa.text("processed_at IS NULL"),
        schema="governance",
    )

    # ── evidence schema ──────────────────────────────────────────────────
    op.create_table(
        "artifact",
        sa.Column("id",             postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("strategy_id",    postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("strategy.strategy.id"), nullable=False),
        sa.Column("stage",          sa.String(50), nullable=False),
        sa.Column("report_type",    sa.String(100), nullable=False),
        sa.Column("uri",            sa.Text(), nullable=False),
        sa.Column("sha256",         sa.String(64), nullable=False),
        sa.Column("media_type",     sa.String(100)),
        sa.Column("size_bytes",     sa.BigInteger()),
        sa.Column("schema_version", sa.String(20)),
        sa.Column("recorded_by",    sa.String(100)),
        sa.Column("recorded_at",    sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        schema="evidence",
    )
    op.create_index("idx_ea_strategy_stage", "artifact",
                    ["strategy_id", "stage"], schema="evidence")
    op.create_index("idx_ea_sha256", "artifact", ["sha256"], schema="evidence")

    op.create_table(
        "binding",
        sa.Column("id",          postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("strategy_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("strategy.strategy.id"), nullable=False),
        sa.Column("version_id",  postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("strategy.version.id")),
        sa.Column("run_id",      postgresql.UUID(as_uuid=True)),
        sa.Column("stage",       sa.String(50), nullable=False),
        sa.Column("artifact_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("evidence.artifact.id"), nullable=False),
        sa.Column("status",      sa.String(20), nullable=False, server_default="active"),
        sa.Column("bound_at",    sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        schema="evidence",
    )
    op.create_index("idx_eb_strategy_stage", "binding",
                    ["strategy_id", "stage"], schema="evidence")
    op.create_index("idx_eb_artifact_id", "binding", ["artifact_id"], schema="evidence")

    # ── research.run + research.metric ───────────────────────────────────
    op.create_table(
        "run",
        sa.Column("id",               postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("run_id",           sa.String(100), unique=True, nullable=False),
        sa.Column("strategy_id",      postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("strategy.strategy.id")),
        sa.Column("version_id",       postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("strategy.version.id")),
        sa.Column("strategy_name",    sa.String(100)),
        sa.Column("symbol",           sa.String(20)),
        sa.Column("start_date",       sa.Date()),
        sa.Column("end_date",         sa.Date()),
        sa.Column("scenario",         sa.String(20), nullable=False, server_default="standard"),
        sa.Column("code_commit",      sa.String(40)),
        sa.Column("env_hash",         sa.String(64)),
        sa.Column("dataset_snapshot", sa.String(64)),
        sa.Column("seed",             sa.Integer()),
        sa.Column("parameters",       postgresql.JSONB()),
        sa.Column("status",           sa.String(20), nullable=False, server_default="pending"),
        sa.Column("started_at",       sa.DateTime(timezone=True)),
        sa.Column("completed_at",     sa.DateTime(timezone=True)),
        sa.Column("created_at",       sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        schema="research",
    )
    op.create_index("idx_run_strategy_id", "run", ["strategy_id"], schema="research")
    op.create_index("idx_run_status",      "run", ["status"],      schema="research")
    op.create_index("idx_run_scenario",    "run", ["scenario"],    schema="research")

    op.create_table(
        "metric",
        sa.Column("id",          sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("run_id",      postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("research.run.id"), nullable=False),
        sa.Column("metric_name", sa.String(100), nullable=False),
        sa.Column("value",       sa.Numeric(14, 6), nullable=False),
        sa.Column("unit",        sa.String(30)),
        sa.Column("window",      sa.String(50)),
        sa.Column("created_at",  sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.UniqueConstraint("run_id", "metric_name", "window"),
        schema="research",
    )
    op.create_index("idx_metric_run_id", "metric", ["run_id"],      schema="research")
    op.create_index("idx_metric_name",   "metric", ["metric_name"], schema="research")

    # ── analytics.stage_gate ─────────────────────────────────────────────
    op.create_table(
        "stage_gate",
        sa.Column("id",           postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("run_id",       postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("research.run.id")),
        sa.Column("strategy_id",  postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("strategy.strategy.id")),
        sa.Column("stage",        sa.String(50), nullable=False),
        sa.Column("scenario",     sa.String(20)),
        sa.Column("n_trades",     sa.Integer()),
        sa.Column("metrics",      postgresql.JSONB()),
        sa.Column("gate_pass",    sa.Boolean(), nullable=False),
        sa.Column("blockers",     postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("notes",        sa.Text()),
        schema="analytics",
    )
    op.create_index("idx_sg_run_id",      "stage_gate", ["run_id"],      schema="analytics")
    op.create_index("idx_sg_strategy_id", "stage_gate", ["strategy_id"], schema="analytics")
    op.create_index("idx_sg_stage",       "stage_gate", ["stage"],       schema="analytics")

    # ── experiments schema ───────────────────────────────────────────────
    op.create_table(
        "experiment",
        sa.Column("id",              postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("exp_id",          sa.String(50), unique=True, nullable=False),
        sa.Column("strategy_id",     postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("strategy.strategy.id")),
        sa.Column("version_id",      postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("strategy.version.id")),
        sa.Column("title",           sa.String(200), nullable=False),
        sa.Column("hypothesis",      sa.Text()),
        sa.Column("instrument",      sa.String(20)),
        sa.Column("dataset_version", sa.String(64)),
        sa.Column("feature_set",     postgresql.JSONB()),
        sa.Column("parameters",      postgresql.JSONB()),
        sa.Column("status",          sa.String(20), nullable=False, server_default="pending"),
        sa.Column("verdict",         sa.String(20)),
        sa.Column("verdict_reason",  sa.Text()),
        sa.Column("created_by",      sa.String(100)),
        sa.Column("created_at",      sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("concluded_at",    sa.DateTime(timezone=True)),
        schema="experiments",
    )
    op.create_index("idx_exp_strategy_id", "experiment", ["strategy_id"], schema="experiments")
    op.create_index("idx_exp_exp_id",      "experiment", ["exp_id"],      schema="experiments")

    op.create_table(
        "parameter_set",
        sa.Column("id",            postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("experiment_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("experiments.experiment.id"), nullable=False),
        sa.Column("label",         sa.String(100)),
        sa.Column("parameters",    postgresql.JSONB(), nullable=False),
        sa.Column("created_at",    sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        schema="experiments",
    )
    op.create_index("idx_ps_experiment_id", "parameter_set", ["experiment_id"],
                    schema="experiments")

    op.create_table(
        "result_binding",
        sa.Column("id",            postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("experiment_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("experiments.experiment.id"), nullable=False),
        sa.Column("run_id",        postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("research.run.id")),
        sa.Column("stage",         sa.String(50), nullable=False),
        sa.Column("verdict",       sa.String(20)),
        sa.Column("artifact_id",   postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("evidence.artifact.id")),
        sa.Column("bound_at",      sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        schema="experiments",
    )
    op.create_index("idx_rb_experiment_id", "result_binding", ["experiment_id"],
                    schema="experiments")

    # ── robustness schema ────────────────────────────────────────────────
    op.create_table(
        "walk_forward_result",
        sa.Column("id",            postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("run_id",        postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("research.run.id"), nullable=False),
        sa.Column("fold_index",    sa.Integer(), nullable=False),
        sa.Column("train_start",   sa.Date(), nullable=False),
        sa.Column("train_end",     sa.Date(), nullable=False),
        sa.Column("test_start",    sa.Date(), nullable=False),
        sa.Column("test_end",      sa.Date(), nullable=False),
        sa.Column("n_trades",      sa.Integer()),
        sa.Column("profit_factor", sa.Numeric(8, 4)),
        sa.Column("win_rate",      sa.Numeric(5, 2)),
        sa.Column("net_r",         sa.Numeric(10, 2)),
        sa.Column("max_drawdown",  sa.Numeric(8, 4)),
        sa.Column("gate_pass",     sa.Boolean()),
        sa.Column("created_at",    sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.UniqueConstraint("run_id", "fold_index"),
        schema="robustness",
    )
    op.create_index("idx_wfr_run_id", "walk_forward_result", ["run_id"], schema="robustness")

    op.create_table(
        "monte_carlo_result",
        sa.Column("id",               postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("run_id",           postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("research.run.id"), nullable=False),
        sa.Column("n_simulations",    sa.Integer(), nullable=False),
        sa.Column("percentile_5_pf",  sa.Numeric(8, 4)),
        sa.Column("percentile_25_pf", sa.Numeric(8, 4)),
        sa.Column("median_pf",        sa.Numeric(8, 4)),
        sa.Column("percentile_75_pf", sa.Numeric(8, 4)),
        sa.Column("percentile_95_pf", sa.Numeric(8, 4)),
        sa.Column("ruin_probability", sa.Numeric(6, 4)),
        sa.Column("max_dd_p95",       sa.Numeric(8, 4)),
        sa.Column("gate_pass",        sa.Boolean()),
        sa.Column("created_at",       sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        schema="robustness",
    )
    op.create_index("idx_mcr_run_id", "monte_carlo_result", ["run_id"], schema="robustness")

    op.create_table(
        "sensitivity_result",
        sa.Column("id",              postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("run_id",          postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("research.run.id"), nullable=False),
        sa.Column("parameter_name",  sa.String(100), nullable=False),
        sa.Column("parameter_value", sa.Text(), nullable=False),
        sa.Column("n_trades",        sa.Integer()),
        sa.Column("profit_factor",   sa.Numeric(8, 4)),
        sa.Column("net_r",           sa.Numeric(10, 2)),
        sa.Column("max_drawdown",    sa.Numeric(8, 4)),
        sa.Column("created_at",      sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        schema="robustness",
    )
    op.create_index("idx_sr_run_id", "sensitivity_result", ["run_id"], schema="robustness")

    # ── execution schema ─────────────────────────────────────────────────
    op.create_table(
        "virtual_order",
        sa.Column("id",              postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("run_id",          postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("research.run.id")),
        sa.Column("symbol",          sa.String(20), nullable=False),
        sa.Column("direction",       sa.String(10), nullable=False),
        sa.Column("requested_price", sa.Numeric(12, 5)),
        sa.Column("filled_price",    sa.Numeric(12, 5)),
        sa.Column("slippage_pips",   sa.Numeric(8, 4)),
        sa.Column("latency_ms",      sa.Integer()),
        sa.Column("status",          sa.String(20), nullable=False),
        sa.Column("reason",          sa.Text()),
        sa.Column("ordered_at",      sa.DateTime(timezone=True), nullable=False),
        sa.Column("filled_at",       sa.DateTime(timezone=True)),
        sa.Column("created_at",      sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        schema="execution",
    )
    op.create_index("idx_vo_run_id", "virtual_order", ["run_id"], schema="execution")
    op.create_index("idx_vo_symbol", "virtual_order", ["symbol"], schema="execution")
    op.create_index("idx_vo_status", "virtual_order", ["status"], schema="execution")

    op.create_table(
        "virtual_fill",
        sa.Column("id",              postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("order_id",        postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("execution.virtual_order.id"), nullable=False),
        sa.Column("symbol",          sa.String(20), nullable=False),
        sa.Column("direction",       sa.String(10), nullable=False),
        sa.Column("requested_price", sa.Numeric(12, 5)),
        sa.Column("filled_price",    sa.Numeric(12, 5)),
        sa.Column("slippage_pips",   sa.Numeric(8, 4)),
        sa.Column("latency_ms",      sa.Integer()),
        sa.Column("execution_time",  sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at",      sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        schema="execution",
    )
    op.create_index("idx_vf_order_id", "virtual_fill", ["order_id"], schema="execution")

    op.create_table(
        "virtual_position",
        sa.Column("id",               postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("order_id",         postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("execution.virtual_order.id"), nullable=False),
        sa.Column("run_id",           postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("research.run.id")),
        sa.Column("symbol",           sa.String(20), nullable=False),
        sa.Column("direction",        sa.String(10), nullable=False),
        sa.Column("entry_price",      sa.Numeric(12, 5), nullable=False),
        sa.Column("exit_price",       sa.Numeric(12, 5)),
        sa.Column("sl_price",         sa.Numeric(12, 5)),
        sa.Column("tp_price",         sa.Numeric(12, 5)),
        sa.Column("spread_cost_pips", sa.Numeric(8, 4)),
        sa.Column("gross_profit_r",   sa.Numeric(8, 4)),
        sa.Column("net_profit_r",     sa.Numeric(8, 4)),
        sa.Column("duration_seconds", sa.Numeric(12, 2)),
        sa.Column("exit_reason",      sa.String(50)),
        sa.Column("opened_at",        sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at",        sa.DateTime(timezone=True)),
        sa.Column("created_at",       sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        schema="execution",
    )
    op.create_index("idx_vp_run_id", "virtual_position", ["run_id"], schema="execution")
    op.create_index("idx_vp_symbol", "virtual_position", ["symbol"], schema="execution")

    op.create_table(
        "drift_observation",
        sa.Column("id",                 postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("run_id",             postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("research.run.id")),
        sa.Column("observation_time",   sa.DateTime(timezone=True), nullable=False),
        sa.Column("symbol",             sa.String(20), nullable=False),
        sa.Column("expected_direction", sa.String(10)),
        sa.Column("actual_direction",   sa.String(10)),
        sa.Column("expected_entry",     sa.Numeric(12, 5)),
        sa.Column("actual_entry",       sa.Numeric(12, 5)),
        sa.Column("slippage_pips",      sa.Numeric(8, 4)),
        sa.Column("latency_ms",         sa.Integer()),
        sa.Column("verdict",            sa.String(20)),
        sa.Column("created_at",         sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        schema="execution",
    )
    op.create_index("idx_do_run_id", "drift_observation", ["run_id"], schema="execution")

    # ── operations schema ────────────────────────────────────────────────
    op.create_table(
        "deployment",
        sa.Column("id",                postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("strategy_id",       postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("strategy.strategy.id"), nullable=False),
        sa.Column("version_id",        postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("strategy.version.id")),
        sa.Column("environment",       sa.String(30), nullable=False),
        sa.Column("broker",            sa.String(50)),
        sa.Column("account_id",        sa.String(100)),
        sa.Column("status",            sa.String(20), nullable=False, server_default="active"),
        sa.Column("deployed_by",       sa.String(100)),
        sa.Column("deployed_at",       sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("decommissioned_at", sa.DateTime(timezone=True)),
        schema="operations",
    )
    op.create_index("idx_dep_strategy_id", "deployment", ["strategy_id"], schema="operations")

    op.create_table(
        "incident",
        sa.Column("id",            postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("deployment_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("operations.deployment.id")),
        sa.Column("strategy_id",   postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("strategy.strategy.id")),
        sa.Column("severity",      sa.String(10), nullable=False),
        sa.Column("title",         sa.String(200), nullable=False),
        sa.Column("description",   sa.Text()),
        sa.Column("status",        sa.String(20), nullable=False, server_default="open"),
        sa.Column("opened_at",     sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("resolved_at",   sa.DateTime(timezone=True)),
        sa.Column("resolution",    sa.Text()),
        schema="operations",
    )
    op.create_index("idx_inc_strategy_id",   "incident", ["strategy_id"],   schema="operations")
    op.create_index("idx_inc_deployment_id", "incident", ["deployment_id"], schema="operations")

    # ── seed canonical strategy record ───────────────────────────────────
    op.execute("""
        INSERT INTO strategy.strategy (name, slug, owner)
        VALUES ('ST-A2', 'ST-A2', 'aung.pro1@gmail.com')
        ON CONFLICT (slug) DO NOTHING
    """)


# ═══════════════════════════════════════════════════════════════════════════
# downgrade
# ═══════════════════════════════════════════════════════════════════════════

def downgrade() -> None:
    # Drop v3 schemas in reverse dependency order
    _drop_schemas()

    # Revision 001 owns the legacy schemas and tables.
