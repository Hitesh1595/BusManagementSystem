"""0011 feedback + complaints tables

Revision ID: 0011_feedback_complaints
Revises: 0010_rls_tenant_isolation
Create Date: 2026-06-12 00:00:00.000000

Spec §6.7 (V2). Creates `trip_feedback` and `complaints`. The enums
(complaint_against, complaint_status, priority) were created in migration 0001,
so they're referenced with create_type=False. Both tables carry school_id and
are enrolled in the same RLS tenant-isolation policy as migration 0010.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0011_feedback_complaints"
down_revision: str | None = "0010_rls_tenant_isolation"
branch_labels = None
depends_on = None

_NEW_TENANT_TABLES = ("trip_feedback", "complaints")
_PREDICATE = (
    "coalesce(current_setting('app.current_school_id', true), '') = '' "
    "OR school_id::text = current_setting('app.current_school_id', true)"
)


def upgrade() -> None:
    op.create_table(
        "trip_feedback",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "school_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("schools.id"), nullable=False,
        ),
        sa.Column(
            "trip_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("trips.id"), nullable=False,
        ),
        sa.Column(
            "parent_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"), nullable=False,
        ),
        sa.Column(
            "driver_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"), nullable=False,
        ),
        sa.Column("rating", sa.SmallInteger(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "is_flagged", sa.Boolean(), nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "admin_reviewed", sa.Boolean(), nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("admin_notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_feedback_rating"),
        sa.UniqueConstraint("trip_id", "parent_id", name="uq_feedback_trip_parent"),
    )
    op.execute(
        "CREATE INDEX idx_feedback_driver ON trip_feedback (driver_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX idx_feedback_flag ON trip_feedback (school_id, is_flagged, admin_reviewed)"
    )

    op.create_table(
        "complaints",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "school_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("schools.id"), nullable=False,
        ),
        sa.Column(
            "submitted_by", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"), nullable=False,
        ),
        sa.Column(
            "against_type",
            postgresql.ENUM(
                "driver", "route", "vehicle", "general",
                name="complaint_against", create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("against_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "trip_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("trips.id"), nullable=True,
        ),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "open", "in_review", "resolved", "closed",
                name="complaint_status", create_type=False,
            ),
            nullable=False,
            server_default="open",
        ),
        sa.Column(
            "priority",
            postgresql.ENUM(
                "low", "medium", "high", "urgent",
                name="priority", create_type=False,
            ),
            nullable=False,
            server_default="medium",
        ),
        sa.Column(
            "assigned_to", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"), nullable=True,
        ),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.execute(
        "CREATE INDEX idx_complaint_school ON complaints (school_id, status, created_at DESC)"
    )

    # Enroll both new tenant tables in the RLS tenant-isolation policy (see 0010).
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
    op.drop_table("complaints")
    op.drop_table("trip_feedback")
