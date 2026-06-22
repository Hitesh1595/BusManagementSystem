"""0012 payments: fee_schedules, invoices, payments

Revision ID: 0012_payments
Revises: 0011_feedback_complaints
Create Date: 2026-06-13 00:00:00.000000

Spec §6.7 / §16 (V2, manual/offline only). Enums (billing_cycle, invoice_status,
payment_gateway, payment_status) were created in migration 0001. All three tables
carry school_id and are enrolled in the RLS tenant-isolation policy (see 0010).
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0012_payments"
down_revision: str | None = "0011_feedback_complaints"
branch_labels = None
depends_on = None

_NEW_TENANT_TABLES = ("fee_schedules", "invoices", "payments")
_PREDICATE = (
    "coalesce(current_setting('app.current_school_id', true), '') = '' "
    "OR school_id::text = current_setting('app.current_school_id', true)"
)


def _uuid(name: str, fk: str | None = None, nullable: bool = False):
    args = [name, postgresql.UUID(as_uuid=True)]
    if fk is not None:
        args.append(sa.ForeignKey(fk))
    return sa.Column(*args, nullable=nullable)


def upgrade() -> None:
    op.create_table(
        "fee_schedules",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            primary_key=True, server_default=sa.text("gen_random_uuid()"),
        ),
        _uuid("school_id", "schools.id"),
        _uuid("route_id", "routes.id", nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="INR"),
        sa.Column(
            "billing_cycle",
            postgresql.ENUM(
                "one_time", "monthly", "quarterly", "term", "annual",
                name="billing_cycle", create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "invoices",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            primary_key=True, server_default=sa.text("gen_random_uuid()"),
        ),
        _uuid("school_id", "schools.id"),
        _uuid("parent_id", "users.id"),
        _uuid("student_id", "students.id"),
        _uuid("fee_schedule_id", "fee_schedules.id", nullable=True),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "draft", "sent", "paid", "overdue", "cancelled",
                name="invoice_status", create_type=False,
            ),
            nullable=False, server_default="draft",
        ),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("now()"),
        ),
    )
    op.execute("CREATE INDEX idx_invoice_parent ON invoices (parent_id, status)")

    op.create_table(
        "payments",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            primary_key=True, server_default=sa.text("gen_random_uuid()"),
        ),
        _uuid("school_id", "schools.id"),
        _uuid("invoice_id", "invoices.id"),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="INR"),
        sa.Column(
            "gateway",
            postgresql.ENUM(
                "razorpay", "stripe", "manual", "offline",
                name="payment_gateway", create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("gateway_payment_id", sa.String(length=120), nullable=True),
        sa.Column("gateway_order_id", sa.String(length=120), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending", "completed", "failed", "refunded",
                name="payment_status", create_type=False,
            ),
            nullable=False, server_default="pending",
        ),
        sa.Column("receipt_no", sa.String(length=40), nullable=True),
        sa.Column(
            "metadata", postgresql.JSONB(), nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("now()"),
        ),
    )

    for table in _NEW_TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING ({_PREDICATE}) WITH CHECK ({_PREDICATE})"
        )


def downgrade() -> None:
    for table in _NEW_TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
    op.drop_table("payments")
    op.drop_table("invoices")
    op.drop_table("fee_schedules")
