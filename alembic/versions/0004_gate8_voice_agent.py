"""Gate 8 voice recovery agent persistence.

Revision ID: 0004_gate8_voice_agent
Revises: 0003_gate7_interventions
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_gate8_voice_agent"
down_revision = "0003_gate7_interventions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "voice_calls",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("intervention_id", sa.String(36), sa.ForeignKey("interventions.id"), nullable=False),
        sa.Column("recovery_case_id", sa.String(36), sa.ForeignKey("recovery_cases.id"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_call_reference", sa.String(255), unique=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("scenario", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("transcript_hash", sa.String(64), nullable=False),
        sa.Column("voice_agent_version", sa.String(64), nullable=False),
        sa.Column("prompt_version", sa.String(64), nullable=False),
        sa.Column("outcome_intent", sa.String(32)),
        sa.Column("payment_link", sa.String(255)),
        sa.Column("failure_code", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lifecycle_version", sa.Integer(), nullable=False),
        sa.UniqueConstraint("intervention_id", name="uq_voice_calls_intervention_id"),
        sa.UniqueConstraint("idempotency_key", name="uq_voice_calls_idempotency_key"),
    )
    op.create_index("ix_voice_calls_intervention_id", "voice_calls", ["intervention_id"])
    op.create_index("ix_voice_calls_recovery_case_id", "voice_calls", ["recovery_case_id"])
    op.create_index("ix_voice_calls_status", "voice_calls", ["status"])

    op.create_table(
        "voice_turns",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("call_id", sa.String(36), sa.ForeignKey("voice_calls.id"), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("speaker", sa.String(16), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("intent", sa.String(32)),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("requested_action", sa.String(32)),
        sa.Column("requires_confirmation", sa.Boolean(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("validated", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("call_id", "sequence_number", name="uq_voice_turns_sequence"),
    )
    op.create_index("ix_voice_turns_call_id", "voice_turns", ["call_id"])

    op.create_table(
        "voice_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("call_id", sa.String(36), sa.ForeignKey("voice_calls.id"), nullable=False),
        sa.Column("event_id", sa.String(128), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("input_hash", sa.String(64)),
        sa.Column("transcript_hash", sa.String(64)),
        sa.Column("voice_agent_version", sa.String(64), nullable=False),
        sa.Column("prompt_version", sa.String(64), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("event_id", name="uq_voice_events_event_id"),
        sa.UniqueConstraint("call_id", "sequence_number", name="uq_voice_events_sequence"),
    )
    op.create_index("ix_voice_events_call_id", "voice_events", ["call_id"])


def downgrade() -> None:
    op.drop_table("voice_events")
    op.drop_table("voice_turns")
    op.drop_table("voice_calls")
