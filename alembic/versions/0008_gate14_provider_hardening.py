"""Persist provider webhook hashes for Gate 14 voice reliability."""

from alembic import op
import sqlalchemy as sa

revision = "0008_gate14_provider_hardening"
down_revision = "0007_gate11_provider_modes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("voice_events", sa.Column("provider_event_hash", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("voice_events", "provider_event_hash")
