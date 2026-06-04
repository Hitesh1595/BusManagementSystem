"""0006 students assignments transport_requests

Revision ID: 5379341db880
Revises: 543969fd1196
Create Date: 2026-06-04 18:47:54.295240

Changes:
  - CREATE TYPE request_status AS ENUM ('pending','approved','rejected','assigned')
  - CREATE TABLE students (parent_id FK, school_id FK, pickup_location geography(Point))
    + GIST idx_students_pickup, btree idx_students_parent
  - CREATE TABLE student_route_assignments (UNIQUE student_id+route_id, partial idx_sra_route)
  - CREATE TABLE transport_requests (pickup_location geography(Point), status request_status)
    + idx_treq_school_status
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "5379341db880"
down_revision: str | Sequence[str] | None = "543969fd1196"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # request_status enum
    # ------------------------------------------------------------------
    op.execute(
        "DO $$ BEGIN "
        "  CREATE TYPE request_status AS ENUM ('pending','approved','rejected','assigned'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; "
        "END $$;"
    )

    # ------------------------------------------------------------------
    # students table (spec §6.2)
    # ------------------------------------------------------------------
    op.create_table(
        "students",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "school_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("schools.id"),
            nullable=False,
        ),
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("grade", sa.String(20), nullable=True),
        sa.Column("section", sa.String(20), nullable=True),
        sa.Column("pickup_address", sa.Text(), nullable=True),
        # pickup_location added via raw DDL below (geography type)
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # Add geography(Point) for pickup_location (nullable)
    op.execute(
        "ALTER TABLE students ADD COLUMN pickup_location geography(Point,4326);"
    )

    # GIST index on pickup_location (spec §6.2)
    op.execute(
        "CREATE INDEX idx_students_pickup ON students USING GIST (pickup_location);"
    )

    # btree index on parent_id (spec §6.2)
    op.create_index("idx_students_parent", "students", ["parent_id"])

    # ------------------------------------------------------------------
    # student_route_assignments table (spec §6.3)
    # ------------------------------------------------------------------
    op.create_table(
        "student_route_assignments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "school_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("schools.id"),
            nullable=False,
        ),
        sa.Column(
            "student_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("students.id"),
            nullable=False,
        ),
        sa.Column(
            "route_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("routes.id"),
            nullable=False,
        ),
        sa.Column(
            "stop_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("route_stops.id"),
            nullable=False,
        ),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.UniqueConstraint("student_id", "route_id", name="uq_sra_student_route"),
    )

    # Partial index idx_sra_route (route_id, stop_id) WHERE is_active (spec §6.3)
    op.execute(
        "CREATE INDEX idx_sra_route ON student_route_assignments (route_id, stop_id) "
        "WHERE is_active = true;"
    )

    # ------------------------------------------------------------------
    # transport_requests table (spec §6.3)
    # ------------------------------------------------------------------
    op.create_table(
        "transport_requests",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "school_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("schools.id"),
            nullable=False,
        ),
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "student_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("students.id"),
            nullable=False,
        ),
        sa.Column("pickup_address", sa.Text(), nullable=True),
        # pickup_location added via raw DDL below
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "approved",
                "rejected",
                "assigned",
                name="request_status",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "assigned_route_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("routes.id"),
            nullable=True,
        ),
        sa.Column(
            "assigned_stop_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("route_stops.id"),
            nullable=True,
        ),
        sa.Column("admin_notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # Add geography(Point) for pickup_location (nullable)
    op.execute(
        "ALTER TABLE transport_requests ADD COLUMN pickup_location geography(Point,4326);"
    )

    # Index on (school_id, status) (spec §6.3)
    op.create_index(
        "idx_treq_school_status",
        "transport_requests",
        ["school_id", "status"],
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_treq_school_status;")
    op.drop_table("transport_requests")
    op.execute("DROP INDEX IF EXISTS idx_sra_route;")
    op.drop_table("student_route_assignments")
    op.execute("DROP INDEX IF EXISTS idx_students_pickup;")
    op.execute("DROP INDEX IF EXISTS idx_students_parent;")
    op.drop_table("students")
    op.execute("DROP TYPE IF EXISTS request_status;")
