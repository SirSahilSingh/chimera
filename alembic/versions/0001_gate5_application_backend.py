"""Gate 5 application persistence foundation.

Revision ID: 0001_gate5_application_backend
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_gate5_application_backend"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recovery_cases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("external_event_id", sa.String(255), nullable=False),
        sa.Column("payment_id", sa.String(255), nullable=False),
        sa.Column("customer_id", sa.String(255), nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("failure_reason", sa.String(64), nullable=False),
        sa.Column("incident_flag", sa.Boolean(), nullable=False),
        sa.Column("payment_method", sa.String(32), nullable=False),
        sa.Column("decision_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("external_event_id", name="uq_recovery_cases_external_event_id"),
    )
    op.create_table(
        "decisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("recovery_case_id", sa.String(36), sa.ForeignKey("recovery_cases.id"), nullable=False),
        sa.Column("decision_run_id", sa.String(64), nullable=False),
        sa.Column("selected_action", sa.String(32), nullable=False),
        sa.Column("predicted_probability", sa.Float(), nullable=False),
        sa.Column("expected_gross_recovery_paise", sa.Integer(), nullable=False),
        sa.Column("expected_net_value_paise", sa.Integer(), nullable=False),
        sa.Column("model_version", sa.String(128), nullable=False),
        sa.Column("feature_schema_version", sa.String(128), nullable=False),
        sa.Column("engine_version", sa.String(128), nullable=False),
        sa.Column("simulator_version", sa.String(64)),
        sa.Column("prompt_version", sa.String(64)),
        sa.Column("decision_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trace_json", sa.JSON(), nullable=False),
        sa.UniqueConstraint("decision_run_id", name="uq_decisions_decision_run_id"),
    )
    op.create_table(
        "decision_candidates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("decision_id", sa.String(36), sa.ForeignKey("decisions.id"), nullable=False),
        sa.Column("action", sa.String(32), nullable=False), sa.Column("status", sa.String(32), nullable=False),
        sa.Column("blocked_reason", sa.Text()), sa.Column("predicted_probability", sa.Float(), nullable=False),
        sa.Column("recoverable_amount_paise", sa.Integer(), nullable=False), sa.Column("expected_gross_recovery_paise", sa.Integer(), nullable=False),
        sa.Column("action_cost_paise", sa.Integer(), nullable=False), sa.Column("incentive_cost_paise", sa.Integer(), nullable=False),
        sa.Column("fatigue_penalty_paise", sa.Integer(), nullable=False), sa.Column("expected_net_value_paise", sa.Integer(), nullable=False),
        sa.Column("expected_net_without_action_cost_paise", sa.Integer(), nullable=False), sa.Column("expected_net_without_fatigue_paise", sa.Integer(), nullable=False),
        sa.Column("rank", sa.Integer()), sa.Column("friction_rank", sa.Integer(), nullable=False), sa.Column("fatigue_reason", sa.Text(), nullable=False),
    )
    op.create_table(
        "action_executions",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("recovery_case_id", sa.String(36), sa.ForeignKey("recovery_cases.id"), nullable=False),
        sa.Column("decision_id", sa.String(36), sa.ForeignKey("decisions.id"), nullable=False), sa.Column("action", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False), sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("provider_reference", sa.String(255)), sa.Column("error_code", sa.String(64)), sa.Column("error_message", sa.Text()),
        sa.Column("request_json", sa.JSON(), nullable=False), sa.Column("response_json", sa.JSON(), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_action_executions_idempotency_key"),
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("recovery_case_id", sa.String(36), sa.ForeignKey("recovery_cases.id")),
        sa.Column("decision_id", sa.String(36), sa.ForeignKey("decisions.id")), sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("actor", sa.String(64), nullable=False), sa.Column("payload_json", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for table, column in (("decisions", "recovery_case_id"), ("decision_candidates", "decision_id"), ("action_executions", "recovery_case_id"), ("audit_logs", "recovery_case_id")):
        op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("action_executions")
    op.drop_table("decision_candidates")
    op.drop_table("decisions")
    op.drop_table("recovery_cases")
