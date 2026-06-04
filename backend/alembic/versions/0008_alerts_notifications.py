"""0008 alerts + notifications tables

Revision ID: 0008_alerts_notifications
Revises: 0007_trips_gps_logs
Create Date: 2026-06-04 00:00:00.000000

Changes:
  - CREATE TABLE alerts  (spec §6.5)
      + idx_alerts_school_sev  (school_id, severity, created_at DESC)
      + idx_alerts_trip_unresolved  PARTIAL (trip_id) WHERE resolved_at IS NULL
  - CREATE TABLE notifications  (spec §6.6)
      + idx_notif_user  (user_id, is_read, created_at DESC)

Enum types (alert_type, alert_severity, notification_type) were created in 0001.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0008_alerts_notifications"
down_revision: str | None = "0007_trips_gps_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # alerts
    # ------------------------------------------------------------------
    op.create_table(
        "alerts",
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
            nullable=True,
        ),
        sa.Column(
            "type",
            postgresql.ENUM(
                "child_not_boarded",
                "child_not_dropped",
                "driver_no_show",
                "sos",
                "route_deviation",
                "incident",
                "insurance_expiry",
                "driver_behavior_pattern",
                name="alert_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "severity",
            postgresql.ENUM(
                "critical",
                "high",
                "medium",
                "low",
                name="alert_severity",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "triggered_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "acknowledged_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        # geography column — created via raw SQL below
        sa.Column(
            "metadata",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Add geography column separately (GeoAlchemy2 type not directly usable in op.create_table)
    op.execute(
        "ALTER TABLE alerts ADD COLUMN location geography(Point,4326)"
    )

    # Regular index
    op.create_index(
        "idx_alerts_school_sev",
        "alerts",
        ["school_id", "severity", "created_at"],
        postgresql_ops={"created_at": "DESC"},
    )

    # Partial index — trip_id WHERE resolved_at IS NULL
    op.execute(
        "CREATE INDEX idx_alerts_trip_unresolved ON alerts (trip_id) "
        "WHERE resolved_at IS NULL"
    )

    # ------------------------------------------------------------------
    # notifications
    # ------------------------------------------------------------------
    op.create_table(
        "notifications",
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
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "type",
            postgresql.ENUM(
                "trip_started",
                "trip_ended",
                "attendance",
                "child_not_boarded",
                "child_not_dropped",
                "bus_approaching",
                "broadcast",
                "alert",
                "generic",
                name="notification_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text, nullable=True),
        sa.Column(
            "data",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "is_read",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Composite index: (user_id, is_read, created_at DESC)
    op.create_index(
        "idx_notif_user",
        "notifications",
        ["user_id", "is_read", "created_at"],
        postgresql_ops={"created_at": "DESC"},
    )


def downgrade() -> None:
    op.drop_index("idx_notif_user", table_name="notifications")
    op.drop_table("notifications")

    op.execute("DROP INDEX IF EXISTS idx_alerts_trip_unresolved")
    op.drop_index("idx_alerts_school_sev", table_name="alerts")
    op.drop_table("alerts")
