"""
Minimal School model for Chunk 2.

NOTE: Chunk 3 expands this table with:
  address, phone, email, logo_url, timezone, school_location (Point)
Those columns are present in the spec §6.2 full schools table DDL.
The migration 0003 (Chunk 3) will ALTER TABLE schools ADD COLUMN ... for each of them.
This model is kept minimal so the User FK resolves now.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class School(Base):
    __tablename__ = "schools"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    join_code: Mapped[str] = mapped_column(String(12), nullable=False, unique=True)
    settings: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
