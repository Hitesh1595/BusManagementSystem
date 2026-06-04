"""
Schools — Pydantic schemas (spec §8.2, §5.3, §6.2).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

# ---------------------------------------------------------------------------
# Nested sub-schemas
# ---------------------------------------------------------------------------


class LatLng(BaseModel):
    lat: float
    lng: float


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------


class SchoolOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    address: str | None
    phone: str | None
    email: str | None
    logo_url: str | None
    timezone: str
    school_location: LatLng | None = None
    join_code: str
    settings: dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Update school profile (PUT /{id})
# ---------------------------------------------------------------------------


class SchoolUpdateIn(BaseModel):
    name: str | None = None
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    logo_url: str | None = None
    timezone: str | None = None
    school_location: LatLng | None = None  # None = leave unchanged


# ---------------------------------------------------------------------------
# Update settings (PUT /{id}/settings) — deep-merge payload into JSONB
# ---------------------------------------------------------------------------


class SchoolSettingsIn(BaseModel):
    """Arbitrary key/value pairs to merge into schools.settings."""

    model_config = ConfigDict(extra="allow")

    @field_validator("*", mode="before")
    @classmethod
    def _allow_any(cls, v: Any) -> Any:  # noqa: ANN201
        return v

    def to_dict(self) -> dict[str, Any]:
        return dict(self.model_extra or {}) | {
            k: v
            for k, v in self.__dict__.items()
            if not k.startswith("_") and k != "model_extra"
        }


class SchoolSettingsPayload(BaseModel):
    """Flat dict — use model_config extra='allow' to accept any key."""

    model_config = ConfigDict(extra="allow")

    def merged_into(self, existing: dict[str, Any]) -> dict[str, Any]:
        """Return a new dict with *self*'s keys merged (shallow) over *existing*."""
        payload = self.model_dump(exclude_none=False)
        return {**existing, **payload}


# ---------------------------------------------------------------------------
# Regenerate join code — response
# ---------------------------------------------------------------------------


class JoinCodeOut(BaseModel):
    join_code: str
