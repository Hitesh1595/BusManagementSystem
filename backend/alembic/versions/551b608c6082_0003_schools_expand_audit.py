"""0003 schools expand + audit

Revision ID: 551b608c6082
Revises: bebd9526564b
Create Date: 2026-06-04 18:20:03.490092

Changes:
  - ALTER TABLE schools ADD COLUMN address, phone, email, logo_url,
      timezone (NOT NULL DEFAULT 'Asia/Kolkata'), school_location (geography Point).
  - CREATE TABLE audit_logs (BIGSERIAL PK) with 2 indexes.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from geoalchemy2 import Geography
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "551b608c6082"
down_revision: str | Sequence[str] | None = "bebd9526564b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # schools — add the 6 columns from spec §6.2 (Chunk 2 was minimal)   #
    # ------------------------------------------------------------------ #
    op.add_column("schools", sa.Column("address", sa.Text(), nullable=True))
    op.add_column("schools", sa.Column("phone", sa.String(20), nullable=True))
    op.add_column("schools", sa.Column("email", sa.String(255), nullable=True))
    op.add_column("schools", sa.Column("logo_url", sa.Text(), nullable=True))
    op.add_column(
        "schools",
        sa.Column(
            "timezone",
            sa.String(64),
            nullable=False,
            server_default=sa.text("'Asia/Kolkata'"),
        ),
    )
    op.add_column(
        "schools",
        sa.Column(
            "school_location",
            Geography(geometry_type="POINT", srid=4326),
            nullable=True,
        ),
    )

    # ------------------------------------------------------------------ #
    # audit_logs (spec §6.6)                                              #
    # ------------------------------------------------------------------ #
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "school_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("schools.id"),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("entity_type", sa.String(40), nullable=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("old_values", postgresql.JSONB(), nullable=True),
        sa.Column("new_values", postgresql.JSONB(), nullable=True),
        sa.Column("ip_address", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_index(
        "idx_audit_school_time",
        "audit_logs",
        ["school_id", "created_at"],
    )
    op.create_index(
        "idx_audit_entity",
        "audit_logs",
        ["entity_type", "entity_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_audit_entity", table_name="audit_logs")
    op.drop_index("idx_audit_school_time", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_column("schools", "school_location")
    op.drop_column("schools", "timezone")
    op.drop_column("schools", "logo_url")
    op.drop_column("schools", "email")
    op.drop_column("schools", "phone")
    op.drop_column("schools", "address")
