"""Persist immutable Gate 15 learning snapshots."""

from alembic import op
import sqlalchemy as sa

revision = "0009_gate15_learning_reports"
down_revision = "0008_gate14_provider_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "learning_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("report_type", sa.String(32), nullable=False),
        sa.Column("analysis_version", sa.String(64), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("baseline_window", sa.String(128), nullable=True),
        sa.Column("current_window", sa.String(128), nullable=True),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("output_hash", sa.String(64), nullable=False),
        sa.Column("structured_report", sa.JSON(), nullable=False),
    )
    op.create_index("ix_learning_reports_report_type", "learning_reports", ["report_type"])


def downgrade() -> None:
    op.drop_index("ix_learning_reports_report_type", table_name="learning_reports")
    op.drop_table("learning_reports")
