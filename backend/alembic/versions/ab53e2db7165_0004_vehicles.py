"""0004 vehicles

Revision ID: ab53e2db7165
Revises: 551b608c6082
Create Date: 2026-06-04 18:25:59.595739

Changes:
  - CREATE TYPE vehicle_type AS ENUM (...)
  - CREATE TABLE vehicles with school_id FK, plate_number,
    vehicle_type enum, capacity CHECK(>0), make, model, year,
    insurance_expiry, fitness_expiry, is_active, timestamps.
  - UNIQUE(school_id, plate_number)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "ab53e2db7165"
down_revision: str | Sequence[str] | None = "551b608c6082"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

VEHICLE_TYPE_ENUM = ("bus", "van", "minibus", "car", "other")


def upgrade() -> None:
    # ------------------------------------------------------------------
    # vehicle_type enum — create only if it doesn't exist yet.
    # We use raw DDL so we can use IF NOT EXISTS syntax.
    # ------------------------------------------------------------------
    op.execute(
        "DO $$ BEGIN "
        "  CREATE TYPE vehicle_type AS ENUM ('bus','van','minibus','car','other'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; "
        "END $$;"
    )

    # ------------------------------------------------------------------
    # vehicles table (spec §6.3)
    # ------------------------------------------------------------------
    op.create_table(
        "vehicles",
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
        sa.Column("plate_number", sa.String(20), nullable=False),
        sa.Column(
            "vehicle_type",
            # Use postgresql.ENUM with create_type=False so alembic does NOT
            # issue a redundant CREATE TYPE (we already did it via raw DDL above).
            postgresql.ENUM(*VEHICLE_TYPE_ENUM, name="vehicle_type", create_type=False),
            nullable=False,
            server_default="bus",
        ),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("make", sa.String(100), nullable=True),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("insurance_expiry", sa.Date(), nullable=True),
        sa.Column("fitness_expiry", sa.Date(), nullable=True),
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
        # Constraints
        sa.UniqueConstraint("school_id", "plate_number", name="uq_vehicle_school_plate"),
        sa.CheckConstraint("capacity > 0", name="ck_vehicle_capacity_positive"),
    )


def downgrade() -> None:
    op.drop_table("vehicles")
    op.execute("DROP TYPE IF EXISTS vehicle_type;")
