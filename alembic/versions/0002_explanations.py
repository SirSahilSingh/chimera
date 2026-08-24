"""Gate 6 immutable explanation records.

Revision ID: 0002_explanations
Revises: 0001_gate5_application_backend
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_explanations"
down_revision = "0001_gate5_application_backend"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "explanations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("decision_id", sa.String(36), sa.ForeignKey("decisions.id"), nullable=False),
        sa.Column("recovery_case_id", sa.String(36), sa.ForeignKey("recovery_cases.id"), nullable=False),
        sa.Column("explanation_source", sa.String(16), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("model_name", sa.String(128), nullable=False),
        sa.Column("prompt_version", sa.String(64), nullable=False),
        sa.Column("explanation_version", sa.String(64), nullable=False),
        sa.Column("input_context_hash", sa.String(64), nullable=False),
        sa.Column("output_hash", sa.String(64), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fallback_reason", sa.String(64), nullable=True),
        sa.Column("structured_explanation", sa.JSON(), nullable=False),
    )
    op.create_index("ix_explanations_decision_id", "explanations", ["decision_id"])
    op.create_index("ix_explanations_recovery_case_id", "explanations", ["recovery_case_id"])
    op.create_index("ix_explanations_generated_at", "explanations", ["generated_at"])


def downgrade() -> None:
    op.drop_table("explanations")
