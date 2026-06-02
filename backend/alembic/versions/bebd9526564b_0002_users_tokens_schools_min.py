"""0002 users tokens schools-min

Revision ID: bebd9526564b
Revises: 0001
Create Date: 2026-06-03

Creates:
  - schools table (MINIMAL — id, name, join_code, settings, is_active, timestamps).
    NOTE: Chunk 3 (migration 0003) will ALTER this table to add:
      address, phone, email, logo_url, timezone, school_location (geography Point).
  - users table (spec §6.2) with FK → schools.id
  - refresh_tokens table (spec §6.6) with family theft detection support
  - auth_tokens table (spec §6.6) for password_reset / email_verification

Indexes:
  - idx_users_email_lower   UNIQUE on lower(email) — case-insensitive uniqueness
  - idx_users_school_role   composite (school_id, role)
  - idx_rt_hash             on refresh_tokens(token_hash)
  - idx_rt_user             on refresh_tokens(user_id, revoked_at)
  - idx_rt_family           on refresh_tokens(family_id)
  - idx_authtok_hash        on auth_tokens(token_hash)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "bebd9526564b"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # schools (MINIMAL — Chunk 3 adds address/phone/email/logo/timezone/  #
    # school_location via ALTER TABLE)                                    #
    # ------------------------------------------------------------------ #
    op.create_table(
        "schools",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("join_code", sa.String(12), nullable=False),
        sa.Column(
            "settings",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
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
        sa.UniqueConstraint("join_code", name="uq_schools_join_code"),
    )

    # ------------------------------------------------------------------ #
    # users (spec §6.2)                                                   #
    # ------------------------------------------------------------------ #
    op.create_table(
        "users",
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
            nullable=True,
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column(
            "role",
            postgresql.ENUM(
                "super_admin",
                "school_admin",
                "driver",
                "parent",
                name="user_role",
                create_type=False,  # already created in migration 0001
            ),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "email_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "notification_prefs",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("push_subscription", postgresql.JSONB(), nullable=True),  # V2 web-push
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
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

    # UNIQUE on lower(email) — case-insensitive uniqueness (spec §6.2)
    op.execute("CREATE UNIQUE INDEX idx_users_email_lower ON users (lower(email))")
    op.create_index("idx_users_school_role", "users", ["school_id", "role"])

    # ------------------------------------------------------------------ #
    # refresh_tokens (spec §6.6)                                          #
    # ------------------------------------------------------------------ #
    op.create_table(
        "refresh_tokens",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("device_id", sa.String(120), nullable=True),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_index("idx_rt_hash", "refresh_tokens", ["token_hash"])
    op.create_index("idx_rt_user", "refresh_tokens", ["user_id", "revoked_at"])
    op.create_index("idx_rt_family", "refresh_tokens", ["family_id"])

    # ------------------------------------------------------------------ #
    # auth_tokens (spec §6.6) — password_reset (MVP), email_verify (V2)  #
    # ------------------------------------------------------------------ #
    op.create_table(
        "auth_tokens",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column(
            "type",
            postgresql.ENUM(
                "password_reset",
                "email_verification",
                name="auth_token_type",
                create_type=False,  # already created in migration 0001
            ),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_index("idx_authtok_hash", "auth_tokens", ["token_hash"])


def downgrade() -> None:
    op.drop_index("idx_authtok_hash", table_name="auth_tokens")
    op.drop_table("auth_tokens")

    op.drop_index("idx_rt_family", table_name="refresh_tokens")
    op.drop_index("idx_rt_user", table_name="refresh_tokens")
    op.drop_index("idx_rt_hash", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    op.execute("DROP INDEX IF EXISTS idx_users_email_lower")
    op.drop_index("idx_users_school_role", table_name="users")
    op.drop_table("users")

    op.drop_table("schools")
