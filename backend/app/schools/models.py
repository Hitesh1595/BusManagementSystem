"""
School model — full §6.2 columns.

Chunk 2 had a minimal model (id, name, join_code, settings, is_active, timestamps).
Chunk 3 (migration 0003) ALTERs the table to add the 6 new columns below;
this ORM model reflects the final schema.
"""

import uuid

from geoalchemy2 import Geography
from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class School(Base, TimestampMixin):
    __tablename__ = "schools"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    # -- added in migration 0003 --
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default="Asia/Kolkata"
    )
    school_location = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=True
    )
    # -- end chunk-3 additions --

    join_code: Mapped[str] = mapped_column(String(12), nullable=False, unique=True)
    settings: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
