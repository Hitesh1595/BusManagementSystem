"""User-management schemas — admin People screen + admin-initiated reset."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.core.pagination import Page


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    school_id: uuid.UUID | None
    phone: str | None
    is_active: bool

    model_config = {"from_attributes": True}


UserPage = Page[UserOut]


class ResetPasswordIn(BaseModel):
    new_password: str = Field(min_length=8)


class ResetPasswordOut(BaseModel):
    status: str  # "reset"


class StaffCreateIn(BaseModel):
    """Create a staff account. Parents self-register; super_admins are seed-only."""

    role: Literal["driver", "school_admin"]
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=20)
    # super_admin only: which school to create the account in. Ignored for school_admin
    # (their own school is always used).
    school_id: uuid.UUID | None = None


class StaffCreateOut(BaseModel):
    user: UserOut
    temp_password: str


class UserUpdateIn(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=20)
