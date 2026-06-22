"""0013 platform billing: platform_invoices

Revision ID: 0013_platform_invoices
Revises: 0012_payments
Create Date: 2026-06-13 00:00:00.000000

Platform → school monthly fee (super_admin only). Distinct from parent transport
fees (0012). Reuses the invoice_status enum (0001). Carries school_id and is
enrolled in the RLS tenant-isolation policy (see 0010); super_admin (empty GUC)
bypasses it to manage all schools.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0013_platform_invoices"
down_revision: str | None = "0012_payments"
branch_labels = None
depends_on = None

_PREDICATE = (
    "coalesce(current_setting('app.current_school_id', true), '') = '' "
    "OR school_id::text = current_setting('app.current_school_id', true)"
)


def upgrade() -> None:
    op.create_table(
        "platform_invoices",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            primary_key=True, server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "school_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("schools.id"), nullable=False,
        ),
        sa.Column("period", sa.String(length=7), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="INR"),
        sa.Column(
            "status",
            postgresql.ENUM(
                "draft", "sent", "paid", "overdue", "cancelled",
                name="invoice_status", create_type=False,
            ),
            nullable=False, server_default="sent",
        ),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("receipt_no", sa.String(length=40), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("school_id", "period", name="uq_platform_invoice_period"),
    )

    op.execute("ALTER TABLE platform_invoices ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE platform_invoices FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON platform_invoices")
    op.execute(
        f"CREATE POLICY tenant_isolation ON platform_invoices "
        f"USING ({_PREDICATE}) WITH CHECK ({_PREDICATE})"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON platform_invoices")
    op.drop_table("platform_invoices")
