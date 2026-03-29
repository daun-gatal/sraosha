"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-29
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "contracts",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("contract_id", sa.String(), nullable=False, unique=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("file_path", sa.String(), nullable=False),
        sa.Column("owner_team", sa.String(), nullable=True),
        sa.Column("raw_yaml", sa.Text(), nullable=False),
        sa.Column("enforcement_mode", sa.String(), nullable=False, server_default="block"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "validation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("contract_id", sa.String(), sa.ForeignKey("contracts.contract_id"), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("enforcement_mode", sa.String(), nullable=False),
        sa.Column("checks_total", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("checks_passed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("checks_failed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("failures", postgresql.JSONB(), nullable=True),
        sa.Column("server", sa.String(), nullable=True),
        sa.Column("triggered_by", sa.String(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "drift_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("contract_id", sa.String(), sa.ForeignKey("contracts.contract_id"), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("validation_runs.id"), nullable=True),
        sa.Column("metric_type", sa.String(), nullable=False),
        sa.Column("table_name", sa.String(), nullable=False),
        sa.Column("column_name", sa.String(), nullable=True),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("warning_threshold", sa.Float(), nullable=True),
        sa.Column("breach_threshold", sa.Float(), nullable=True),
        sa.Column("is_warning", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_breached", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "drift_baselines",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("contract_id", sa.String(), sa.ForeignKey("contracts.contract_id"), nullable=False),
        sa.Column("metric_type", sa.String(), nullable=False),
        sa.Column("table_name", sa.String(), nullable=False),
        sa.Column("column_name", sa.String(), nullable=True),
        sa.Column("mean", sa.Float(), nullable=True),
        sa.Column("std_dev", sa.Float(), nullable=True),
        sa.Column("trend_slope", sa.Float(), nullable=True),
        sa.Column("is_trending_to_breach", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("estimated_breach_in_runs", sa.Integer(), nullable=True),
        sa.Column("window_size", sa.Integer(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("contract_id", "metric_type", "table_name", "column_name"),
    )

    op.create_table(
        "alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("contract_id", sa.String(), sa.ForeignKey("contracts.contract_id"), nullable=False),
        sa.Column("alert_type", sa.String(), nullable=False),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("error_message", sa.Text(), nullable=True),
    )

    op.create_table(
        "teams",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("slack_channel", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "compliance_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("total_runs", sa.Integer(), nullable=False),
        sa.Column("passed_runs", sa.Integer(), nullable=False),
        sa.Column("violations_count", sa.Integer(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("team_id", "period_start", "period_end"),
    )


def downgrade() -> None:
    op.drop_table("compliance_scores")
    op.drop_table("teams")
    op.drop_table("alerts")
    op.drop_table("drift_baselines")
    op.drop_table("drift_metrics")
    op.drop_table("validation_runs")
    op.drop_table("contracts")
