"""Gate 9 payment link and provider event persistence.

Revision ID: 0005_gate9_payments
Revises: 0004_gate8_voice_agent
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_gate9_payments"
down_revision = "0004_gate8_voice_agent"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payment_links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("recovery_case_id", sa.String(36), sa.ForeignKey("recovery_cases.id"), nullable=False),
        sa.Column("intervention_id", sa.String(36), sa.ForeignKey("interventions.id"), nullable=False),
        sa.Column("decision_id", sa.String(36), sa.ForeignKey("decisions.id"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_payment_link_id", sa.String(255), nullable=False),
        sa.Column("short_url", sa.String(512), nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("result_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_payment_links_idempotency_key"),
        sa.UniqueConstraint("provider", "provider_payment_link_id", name="uq_payment_links_provider_ref"),
    )
    op.create_index("ix_payment_links_recovery_case_id", "payment_links", ["recovery_case_id"])
    op.create_index("ix_payment_links_intervention_id", "payment_links", ["intervention_id"])
    op.create_index("ix_payment_links_decision_id", "payment_links", ["decision_id"])
    op.create_index("ix_payment_links_status", "payment_links", ["status"])
    op.create_table(
        "payment_attempts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("payment_link_id", sa.String(36), sa.ForeignKey("payment_links.id"), nullable=False),
        sa.Column("provider_payment_id", sa.String(255)),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_payment_attempts_payment_link_id", "payment_attempts", ["payment_link_id"])
    op.create_index("ix_payment_attempts_provider_payment_id", "payment_attempts", ["provider_payment_id"])
    op.create_table(
        "payment_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("payment_link_id", sa.String(36), sa.ForeignKey("payment_links.id"), nullable=False),
        sa.Column("payment_attempt_id", sa.String(36), sa.ForeignKey("payment_attempts.id")),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_event_id", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("signature_verified", sa.Boolean(), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider", "provider_event_id", name="uq_payment_events_provider_event"),
    )
    op.create_index("ix_payment_events_payment_link_id", "payment_events", ["payment_link_id"])
    op.create_index("ix_payment_events_payment_attempt_id", "payment_events", ["payment_attempt_id"])


def downgrade() -> None:
    op.drop_table("payment_events")
    op.drop_table("payment_attempts")
    op.drop_table("payment_links")
