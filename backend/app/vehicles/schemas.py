"""
Vehicle + Driver Pydantic schemas.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.core.pagination import Page

# ---------------------------------------------------------------------------
# Vehicle schemas
# ---------------------------------------------------------------------------

VehicleTypeEnum = Literal["bus", "van", "minibus", "car", "other"]


class VehicleIn(BaseModel):
    plate_number: str = Field(min_length=1, max_length=20)
    vehicle_type: VehicleTypeEnum = "bus"
    capacity: int = Field(gt=0)
    make: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=100)
    year: int | None = Field(default=None, ge=1900, le=2100)
    insurance_expiry: date | None = None
    fitness_expiry: date | None = None


class VehicleUpdate(BaseModel):
    plate_number: str | None = Field(default=None, min_length=1, max_length=20)
    vehicle_type: VehicleTypeEnum | None = None
    capacity: int | None = Field(default=None, gt=0)
    make: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=100)
    year: int | None = Field(default=None, ge=1900, le=2100)
    insurance_expiry: date | None = None
    fitness_expiry: date | None = None
    is_active: bool | None = None


class VehicleOut(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    plate_number: str
    vehicle_type: str
    capacity: int
    make: str | None
    model: str | None
    year: int | None
    insurance_expiry: date | None
    fitness_expiry: date | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# Page[VehicleOut] — uses the generic Page from core.pagination
VehiclePage = Page[VehicleOut]


# ---------------------------------------------------------------------------
# Driver schemas (drivers are users with role=driver)
# ---------------------------------------------------------------------------


class DriverIn(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=20)


class DriverUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=20)
    is_active: bool | None = None


class DriverOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    phone: str | None
    role: str
    school_id: uuid.UUID | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class DriverCreateOut(BaseModel):
    """Returned only on POST /drivers — includes the one-time temp password."""

    driver: DriverOut
    temp_password: str


class AssignVehicleIn(BaseModel):
    vehicle_id: uuid.UUID


# Page[DriverOut]
DriverPage = Page[DriverOut]
