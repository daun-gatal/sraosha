"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-31
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
        "alerting_profiles",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "alerting_profile_channels",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "alerting_profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("alerting_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel_type", sa.String(), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_alerting_profile_channels_profile_id",
        "alerting_profile_channels",
        ["alerting_profile_id"],
    )

    op.create_table(
        "teams",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column(
            "default_alerting_profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("alerting_profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "compliance_scores",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "team_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("teams.id"),
            nullable=False,
        ),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("total_runs", sa.Integer(), nullable=False),
        sa.Column("passed_runs", sa.Integer(), nullable=False),
        sa.Column("violations_count", sa.Integer(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("team_id", "period_start", "period_end"),
    )

    op.create_table(
        "contracts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("contract_id", sa.String(), nullable=False, unique=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("file_path", sa.String(), nullable=False),
        sa.Column(
            "team_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("teams.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "alerting_profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("alerting_profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("raw_yaml", sa.Text(), nullable=False),
        sa.Column("enforcement_mode", sa.String(), nullable=False, server_default="block"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_contracts_team_id", "contracts", ["team_id"])
    op.create_index("ix_contracts_alerting_profile_id", "contracts", ["alerting_profile_id"])

    op.create_table(
        "validation_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "contract_id",
            sa.String(),
            sa.ForeignKey("contracts.contract_id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("enforcement_mode", sa.String(), nullable=False),
        sa.Column("checks_total", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("checks_passed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("checks_failed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("failures", sa.JSON(), nullable=True),
        sa.Column("server", sa.String(), nullable=True),
        sa.Column("triggered_by", sa.String(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("run_log", sa.Text(), nullable=True),
        sa.Column(
            "run_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "validation_schedules",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "contract_id",
            sa.String(),
            sa.ForeignKey("contracts.contract_id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("interval_preset", sa.String(), nullable=False, server_default="daily"),
        sa.Column("cron_expression", sa.String(), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "connections",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("server_type", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("host", sa.String(), nullable=True),
        sa.Column("port", sa.Integer(), nullable=True),
        sa.Column("database", sa.String(), nullable=True),
        sa.Column("schema_name", sa.String(), nullable=True),
        sa.Column("account", sa.String(), nullable=True),
        sa.Column("warehouse", sa.String(), nullable=True),
        sa.Column("role", sa.String(), nullable=True),
        sa.Column("catalog", sa.String(), nullable=True),
        sa.Column("http_path", sa.String(), nullable=True),
        sa.Column("project", sa.String(), nullable=True),
        sa.Column("dataset", sa.String(), nullable=True),
        sa.Column("location", sa.String(), nullable=True),
        sa.Column("path", sa.String(), nullable=True),
        sa.Column("username", sa.String(), nullable=True),
        sa.Column("password_encrypted", sa.Text(), nullable=True),
        sa.Column("token_encrypted", sa.Text(), nullable=True),
        sa.Column("service_account_json_encrypted", sa.Text(), nullable=True),
        sa.Column("extra_params", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "dq_checks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "connection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("connections.id"),
            nullable=False,
        ),
        sa.Column(
            "team_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("teams.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "alerting_profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("alerting_profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("data_source_name", sa.String(), nullable=False),
        sa.Column("sodacl_yaml", sa.Text(), nullable=False),
        sa.Column("tables", postgresql.JSONB(), nullable=True),
        sa.Column("check_categories", postgresql.JSONB(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("tags", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_dq_checks_team_id", "dq_checks", ["team_id"])
    op.create_index("ix_dq_checks_alerting_profile_id", "dq_checks", ["alerting_profile_id"])

    op.create_table(
        "dq_check_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "dq_check_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("dq_checks.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("checks_total", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("checks_passed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("checks_warned", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("checks_failed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("results_json", postgresql.JSONB(), nullable=True),
        sa.Column("diagnostics_json", postgresql.JSONB(), nullable=True),
        sa.Column("run_log", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("triggered_by", sa.String(), nullable=False, server_default="manual"),
        sa.Column(
            "run_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index(
        "ix_dq_check_runs_check_run_at",
        "dq_check_runs",
        ["dq_check_id", sa.text("run_at DESC")],
    )

    op.create_table(
        "dq_schedules",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "dq_check_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("dq_checks.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("interval_preset", sa.String(), nullable=False, server_default="daily"),
        sa.Column("cron_expression", sa.String(), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "alerts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "contract_id",
            sa.String(),
            sa.ForeignKey("contracts.contract_id"),
            nullable=True,
        ),
        sa.Column(
            "dq_check_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("dq_checks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "alerting_profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("alerting_profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "alerting_profile_channel_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("alerting_profile_channels.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("alert_type", sa.String(), nullable=False),
        sa.Column("channel_type", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("error_message", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("dq_schedules")
    op.drop_index("ix_dq_check_runs_check_run_at", table_name="dq_check_runs")
    op.drop_table("dq_check_runs")
    op.drop_table("alerts")
    op.drop_table("dq_checks")
    op.drop_table("connections")
    op.drop_table("validation_schedules")
    op.drop_table("validation_runs")
    op.drop_table("contracts")
    op.drop_table("compliance_scores")
    op.drop_table("teams")
    op.drop_index("ix_alerting_profile_channels_profile_id", table_name="alerting_profile_channels")
    op.drop_table("alerting_profile_channels")
    op.drop_table("alerting_profiles")
