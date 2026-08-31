"""Persist customer contact routing data from payment providers."""

from alembic import op
import sqlalchemy as sa

revision = "0011_gate17_contact_routing"
down_revision = "0010_gate16_provider_health"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("recovery_cases", sa.Column("customer_phone", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column("recovery_cases", "customer_phone")
