"""Persist initial checkout orders separately from recovery links."""

from alembic import op
import sqlalchemy as sa


revision = "0012_initial_payment_orders"
down_revision = "0011_gate17_contact_routing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payment_orders",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_mode", sa.String(length=16), nullable=False),
        sa.Column("provider_order_id", sa.String(length=255), nullable=False),
        sa.Column("checkout_key_id", sa.String(length=255), nullable=True),
        sa.Column("external_reference_id", sa.String(length=255), nullable=False),
        sa.Column("customer_id", sa.String(length=255), nullable=False),
        sa.Column("customer_phone", sa.String(length=32), nullable=True),
        sa.Column("customer_email", sa.String(length=255), nullable=True),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("provider_payment_id", sa.String(length=255), nullable=True),
        sa.Column("failure_reason", sa.String(length=64), nullable=True),
        sa.Column("recovery_case_id", sa.String(length=36), nullable=True),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("result_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["recovery_case_id"], ["recovery_cases.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_payment_orders_idempotency_key"),
        sa.UniqueConstraint("provider", "provider_order_id", name="uq_payment_orders_provider_order"),
        sa.UniqueConstraint("provider", "external_reference_id", name="uq_payment_orders_provider_reference"),
    )
    op.create_index("ix_payment_orders_provider_order_id", "payment_orders", ["provider_order_id"], unique=False)
    op.create_index("ix_payment_orders_recovery_case_id", "payment_orders", ["recovery_case_id"], unique=False)
    op.create_index("ix_payment_orders_status", "payment_orders", ["status"], unique=False)
    op.create_table(
        "payment_order_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("payment_order_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_mode", sa.String(length=16), nullable=False),
        sa.Column("provider_event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("provider_payment_id", sa.String(length=255), nullable=True),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("signature_verified", sa.Boolean(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["payment_order_id"], ["payment_orders.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_event_id", name="uq_payment_order_events_provider_event"),
    )
    op.create_index("ix_payment_order_events_payment_order_id", "payment_order_events", ["payment_order_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_payment_order_events_payment_order_id", table_name="payment_order_events")
    op.drop_table("payment_order_events")
    op.drop_index("ix_payment_orders_status", table_name="payment_orders")
    op.drop_index("ix_payment_orders_recovery_case_id", table_name="payment_orders")
    op.drop_index("ix_payment_orders_provider_order_id", table_name="payment_orders")
    op.drop_table("payment_orders")
