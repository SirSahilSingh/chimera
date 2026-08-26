"""Gate 7 provider-independent intervention lifecycle.

Revision ID: 0003_gate7_interventions
Revises: 0002_explanations
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_gate7_interventions"
down_revision = "0002_explanations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interventions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("recovery_case_id", sa.String(36), sa.ForeignKey("recovery_cases.id"), nullable=False),
        sa.Column("decision_id", sa.String(36), sa.ForeignKey("decisions.id"), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("queued_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lifecycle_version", sa.Integer(), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_interventions_idempotency_key"),
        sa.UniqueConstraint("decision_id", name="uq_interventions_decision_id"),
    )
    op.create_index("ix_interventions_recovery_case_id", "interventions", ["recovery_case_id"])
    op.create_index("ix_interventions_decision_id", "interventions", ["decision_id"])
    op.create_index("ix_interventions_status", "interventions", ["status"])

    op.create_table(
        "intervention_executions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("intervention_id", sa.String(36), sa.ForeignKey("interventions.id"), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("executor_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("provider_reference", sa.String(255)),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("result_hash", sa.String(64)),
        sa.Column("error_code", sa.String(64)),
        sa.Column("error_message_safe", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("response_json", sa.JSON(), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_intervention_executions_idempotency_key"),
        sa.UniqueConstraint("intervention_id", "attempt_number", name="uq_intervention_executions_attempt"),
    )
    op.create_index("ix_intervention_executions_intervention_id", "intervention_executions", ["intervention_id"])

    op.create_table(
        "intervention_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("intervention_id", sa.String(36), sa.ForeignKey("interventions.id"), nullable=False),
        sa.Column("recovery_case_id", sa.String(36), sa.ForeignKey("recovery_cases.id"), nullable=False),
        sa.Column("decision_id", sa.String(36), sa.ForeignKey("decisions.id"), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("actor", sa.String(64), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("intervention_id", "sequence_number", name="uq_intervention_events_sequence"),
    )
    op.create_index("ix_intervention_events_intervention_id", "intervention_events", ["intervention_id"])
    op.create_index("ix_intervention_events_recovery_case_id", "intervention_events", ["recovery_case_id"])
    op.create_index("ix_intervention_events_decision_id", "intervention_events", ["decision_id"])

    op.create_table(
        "intervention_outcomes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("intervention_id", sa.String(36), sa.ForeignKey("interventions.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("recovered_amount_paise", sa.Integer()),
        sa.Column("currency", sa.String(3)),
        sa.Column("outcome_reference", sa.String(255)),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_intervention_outcomes_intervention_id", "intervention_outcomes", ["intervention_id"])


def downgrade() -> None:
    op.drop_table("intervention_outcomes")
    op.drop_table("intervention_events")
    op.drop_table("intervention_executions")
    op.drop_table("interventions")
