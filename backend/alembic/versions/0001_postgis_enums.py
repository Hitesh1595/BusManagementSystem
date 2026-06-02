"""0001 postgis + enums

Revision ID: 0001
Revises:
Create Date: 2026-06-03 00:00:00.000000

This migration:
1. Enables the PostGIS extension (idempotent via IF NOT EXISTS).
2. Creates all MVP enum types from spec §6.1.
3. Includes the V2 enum types so schema is forward-compatible.

NOTE: App tables are NOT created here — they land per-module in later chunks.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | tuple | None = None
depends_on: str | tuple | None = None


# ---------------------------------------------------------------------------
# MVP enum names + values (spec §6.1)
# ---------------------------------------------------------------------------
_MVP_ENUMS: list[tuple[str, list[str]]] = [
    ("user_role", ["super_admin", "school_admin", "driver", "parent"]),
    ("vehicle_type", ["bus", "van", "car", "minibus"]),
    ("schedule_type", ["morning", "evening", "both"]),
    ("request_status", ["pending", "approved", "rejected", "assigned"]),
    (
        "trip_status",
        [
            "scheduled",
            "in_progress",
            "pending_safeguard_check",
            "completed",
            "cancelled",
            "incident",
        ],
    ),
    ("attendance_status", ["boarded", "absent", "absent_parent_marked"]),
    ("drop_type", ["stop", "school"]),
    (
        "alert_type",
        [
            "child_not_boarded",
            "child_not_dropped",
            "driver_no_show",
            "sos",
            "route_deviation",
            "incident",
            "insurance_expiry",
            "driver_behavior_pattern",
        ],
    ),
    ("alert_severity", ["critical", "high", "medium", "low"]),
    ("auth_token_type", ["password_reset", "email_verification"]),
    (
        "notification_type",
        [
            "trip_started",
            "trip_ended",
            "attendance",
            "child_not_boarded",
            "child_not_dropped",
            "bus_approaching",
            "broadcast",
            "alert",
            "generic",
        ],
    ),
]

# V2 enum types — included now so the schema stays forward-compatible.
_V2_ENUMS: list[tuple[str, list[str]]] = [
    ("billing_cycle", ["one_time", "monthly", "quarterly", "term", "annual"]),
    ("invoice_status", ["draft", "sent", "paid", "overdue", "cancelled"]),
    ("payment_gateway", ["razorpay", "stripe", "manual", "offline"]),
    ("payment_status", ["pending", "completed", "failed", "refunded"]),
    ("complaint_against", ["driver", "route", "vehicle", "general"]),
    ("complaint_status", ["open", "in_review", "resolved", "closed"]),
    ("priority", ["low", "medium", "high", "urgent"]),
    ("report_type", ["compliance", "attendance", "incident", "trip_summary"]),
    ("report_format", ["pdf", "xlsx"]),
    ("report_status", ["pending", "generating", "completed", "failed"]),
]

_ALL_ENUMS = _MVP_ENUMS + _V2_ENUMS


def upgrade() -> None:
    # 1. PostGIS extension — idempotent.
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # 2. Create all enum types — each guarded so re-running is safe.
    for enum_name, values in _ALL_ENUMS:
        quoted = ", ".join(f"'{v}'" for v in values)
        op.execute(
            f"DO $$ BEGIN "
            f"  CREATE TYPE {enum_name} AS ENUM ({quoted}); "
            f"EXCEPTION WHEN duplicate_object THEN NULL; "
            f"END $$;"
        )


def downgrade() -> None:
    # Drop enum types in reverse order to handle any dependencies.
    for enum_name, _ in reversed(_ALL_ENUMS):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
    op.execute("DROP EXTENSION IF EXISTS postgis")
