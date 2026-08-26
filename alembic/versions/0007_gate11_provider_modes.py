"""Persist Gate 11 provider execution modes."""

from alembic import op
import sqlalchemy as sa

revision = "0007_gate11_provider_modes"
down_revision = "0006_gate10_orchestration"
branch_labels = None
depends_on = None


TABLES = (
    "action_executions",
    "intervention_executions",
    "payment_links",
    "payment_events",
    "voice_calls",
    "voice_events",
    "message_attempts",
    "messaging_events",
    "retry_attempts",
    "scheduled_retries",
    "escalations",
)


def upgrade() -> None:
    for table in TABLES:
        op.add_column(table, sa.Column("provider_mode", sa.String(16), nullable=False, server_default="LOCAL"))


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_column(table, "provider_mode")
