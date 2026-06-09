"""User-management schemas — admin People screen + admin-initiated reset."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

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
