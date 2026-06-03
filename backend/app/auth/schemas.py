"""
Auth Pydantic schemas — request bodies and response models.
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, EmailStr, Field

# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------


class RegisterIn(BaseModel):
    join_code: str
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=20)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str
    new_password: str = Field(min_length=8)


class MeUpdateIn(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=20)
    notification_prefs: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    school_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class TokenOut(BaseModel):
    access_token: str
    user: UserOut
