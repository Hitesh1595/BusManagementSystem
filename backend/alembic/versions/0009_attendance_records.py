"""0009 attendance_records table

Revision ID: 0009_attendance_records
Revises: 0008_alerts_notifications
Create Date: 2026-06-04 00:00:00.000000

Changes:
  - CREATE TABLE attendance_records  (spec §6.5)
      + UNIQUE(trip_id, student_id)
      + idx_att_trip_stop   (trip_id, stop_id)
      + idx_att_school_trip (school_id, trip_id)
      + idx_att_student     (student_id)

Enum types (attendance_status, drop_type) were created in migration 0001.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0009_attendance_records"
down_revision: str | None = "0008_alerts_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "attendance_records",
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
            "trip_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("trips.id"),
            nullable=False,
        ),
        sa.Column(
            "student_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("students.id"),
            nullable=False,
        ),
        sa.Column(
            "stop_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("route_stops.id"),
            nullable=True,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "boarded",
                "absent",
                "absent_parent_marked",
                name="attendance_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "marked_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "marked_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        # Drop-off fields (Chunk 5B)
        sa.Column(
            "drop_type",
            postgresql.ENUM(
                "stop",
                "school",
                name="drop_type",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column(
            "drop_stop_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("route_stops.id"),
            nullable=True,
        ),
        sa.Column(
            "dropped_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # UNIQUE constraint
        sa.UniqueConstraint("trip_id", "student_id", name="uq_att_trip_student"),
    )

    # marked_location geography column — added separately (GeoAlchemy2)
    op.execute(
        "ALTER TABLE attendance_records "
        "ADD COLUMN marked_location geography(Point,4326)"
    )

    # Indexes
    op.create_index("idx_att_trip_stop", "attendance_records", ["trip_id", "stop_id"])
    op.create_index("idx_att_school_trip", "attendance_records", ["school_id", "trip_id"])
    op.create_index("idx_att_student", "attendance_records", ["student_id"])


def downgrade() -> None:
    op.drop_index("idx_att_student", table_name="attendance_records")
    op.drop_index("idx_att_school_trip", table_name="attendance_records")
    op.drop_index("idx_att_trip_stop", table_name="attendance_records")
    op.drop_table("attendance_records")
