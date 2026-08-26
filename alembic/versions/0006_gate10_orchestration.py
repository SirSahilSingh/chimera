"""Gate 10 messaging, retry scheduling, and escalation persistence.

Revision ID: 0006_gate10_orchestration
Revises: 0005_gate9_payments
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_gate10_orchestration"
down_revision = "0005_gate9_payments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("message_attempts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("recovery_case_id", sa.String(36), sa.ForeignKey("recovery_cases.id"), nullable=False),
        sa.Column("intervention_id", sa.String(36), sa.ForeignKey("interventions.id"), nullable=False),
        sa.Column("decision_id", sa.String(36), sa.ForeignKey("decisions.id"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("template_key", sa.String(64), nullable=False),
        sa.Column("template_version", sa.String(64), nullable=False),
        sa.Column("rendered_content_hash", sa.String(64), nullable=False),
        sa.Column("provider_message_id", sa.String(255)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("delivery_state", sa.String(32), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_message_attempts_idempotency_key"),
    )
    for name in ("recovery_case_id", "intervention_id", "decision_id"):
        op.create_index(f"ix_message_attempts_{name}", "message_attempts", [name])
    op.create_table("messaging_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("message_attempt_id", sa.String(36), sa.ForeignKey("message_attempts.id"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_event_id", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("delivery_state", sa.String(32), nullable=False),
        sa.Column("signature_verified", sa.Boolean(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider", "provider_event_id", name="uq_messaging_events_provider_event"),
    )
    op.create_index("ix_messaging_events_message_attempt_id", "messaging_events", ["message_attempt_id"])
    op.create_table("retry_attempts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("recovery_case_id", sa.String(36), sa.ForeignKey("recovery_cases.id"), nullable=False),
        sa.Column("intervention_id", sa.String(36), sa.ForeignKey("interventions.id"), nullable=False),
        sa.Column("decision_id", sa.String(36), sa.ForeignKey("decisions.id"), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_reference", sa.String(255)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("result_hash", sa.String(64)),
        sa.Column("validated_result_json", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_retry_attempts_idempotency_key"),
        sa.UniqueConstraint("intervention_id", "attempt_number", name="uq_retry_attempts_intervention_attempt"),
    )
    for name in ("recovery_case_id", "intervention_id", "decision_id"):
        op.create_index(f"ix_retry_attempts_{name}", "retry_attempts", [name])
    op.create_table("scheduled_retries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("recovery_case_id", sa.String(36), sa.ForeignKey("recovery_cases.id"), nullable=False),
        sa.Column("intervention_id", sa.String(36), sa.ForeignKey("interventions.id"), nullable=False),
        sa.Column("decision_id", sa.String(36), sa.ForeignKey("decisions.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("schedule_reason", sa.String(128), nullable=False),
        sa.Column("eligibility_status", sa.String(32), nullable=False),
        sa.Column("execution_status", sa.String(32), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_scheduled_retries_idempotency_key"),
    )
    for name in ("recovery_case_id", "intervention_id", "decision_id", "scheduled_at"):
        op.create_index(f"ix_scheduled_retries_{name}", "scheduled_retries", [name])
    op.create_table("escalations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("recovery_case_id", sa.String(36), sa.ForeignKey("recovery_cases.id"), nullable=False),
        sa.Column("intervention_id", sa.String(36), sa.ForeignKey("interventions.id"), nullable=False),
        sa.Column("decision_id", sa.String(36), sa.ForeignKey("decisions.id"), nullable=False),
        sa.Column("escalation_reason", sa.String(255), nullable=False),
        sa.Column("context_json", sa.JSON(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_escalations_idempotency_key"),
        sa.UniqueConstraint("intervention_id", name="uq_escalations_intervention_id"),
    )
    for name in ("recovery_case_id", "intervention_id", "decision_id", "status"):
        op.create_index(f"ix_escalations_{name}", "escalations", [name])
    op.create_table("escalation_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("escalation_id", sa.String(36), sa.ForeignKey("escalations.id"), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("actor", sa.String(64), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("escalation_id", "sequence_number", name="uq_escalation_events_sequence"),
    )
    op.create_index("ix_escalation_events_escalation_id", "escalation_events", ["escalation_id"])


def downgrade() -> None:
    op.drop_table("escalation_events")
    op.drop_table("escalations")
    op.drop_table("scheduled_retries")
    op.drop_table("retry_attempts")
    op.drop_table("messaging_events")
    op.drop_table("message_attempts")
