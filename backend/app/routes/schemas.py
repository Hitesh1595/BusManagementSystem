"""
Route + RouteStop Pydantic schemas.
"""

from __future__ import annotations

import uuid
from datetime import datetime, time
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.core.pagination import Page

ScheduleTypeEnum = Literal["morning", "evening", "both"]


# ---------------------------------------------------------------------------
# Location sub-schema (lat/lng pair)
# ---------------------------------------------------------------------------


class LatLng(BaseModel):
    lat: float = Field(ge=-90.0, le=90.0)
    lng: float = Field(ge=-180.0, le=180.0)


# ---------------------------------------------------------------------------
# Stop schemas
# ---------------------------------------------------------------------------


class StopIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    location: LatLng
    address: str | None = None
    stop_order: int | None = Field(default=None, ge=0)
    arrival_time: time | None = None


class StopUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    location: LatLng | None = None
    address: str | None = None
    arrival_time: time | None = None


class StopOut(BaseModel):
    id: uuid.UUID
    route_id: uuid.UUID
    name: str
    location: LatLng
    address: str | None
    stop_order: int
    arrival_time: time | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Reorder schema
# ---------------------------------------------------------------------------


class ReorderIn(BaseModel):
    ordered_stop_ids: Annotated[list[uuid.UUID], Field(min_length=1)]


# ---------------------------------------------------------------------------
# Route schemas
# ---------------------------------------------------------------------------


class RouteIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    schedule_type: ScheduleTypeEnum = "both"
    vehicle_id: uuid.UUID | None = None
    driver_id: uuid.UUID | None = None


class RouteUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    schedule_type: ScheduleTypeEnum | None = None
    vehicle_id: uuid.UUID | None = None
    driver_id: uuid.UUID | None = None
    is_active: bool | None = None
    # version is REQUIRED for optimistic locking
    version: int


class RouteOut(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    name: str
    description: str | None
    vehicle_id: uuid.UUID | None
    driver_id: uuid.UUID | None
    schedule_type: str
    version: int
    is_active: bool
    # route_path: exposed as a flag (True = has geometry); callers use stops for coords.
    # We don't serialize the raw WKB bytes — clients reconstruct from stops.
    has_route_path: bool
    stops: list[StopOut]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# Page type aliases
RoutePage = Page[RouteOut]
StopPage = Page[StopOut]
