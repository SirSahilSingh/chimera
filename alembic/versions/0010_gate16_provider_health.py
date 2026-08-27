"""Persist append-only Gate 16 provider verification records."""

from alembic import op
import sqlalchemy as sa

revision = "0010_gate16_provider_health"
down_revision = "0009_gate15_learning_reports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_verifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider_name", sa.String(64), nullable=False),
        sa.Column("provider_type", sa.String(32), nullable=False),
        sa.Column("provider_mode", sa.String(16), nullable=False),
        sa.Column("operation", sa.String(32), nullable=False),
        sa.Column("readiness_status", sa.String(32), nullable=False),
        sa.Column("verification_result", sa.String(32), nullable=False),
        sa.Column("verification_result_json", sa.JSON(), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("error_type", sa.String(64), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("idempotency_status", sa.String(32), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("output_hash", sa.String(64), nullable=False),
    )
    op.create_index("ix_provider_verifications_provider_name", "provider_verifications", ["provider_name"])


def downgrade() -> None:
    op.drop_index("ix_provider_verifications_provider_name", table_name="provider_verifications")
    op.drop_table("provider_verifications")

