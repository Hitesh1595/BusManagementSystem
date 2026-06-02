import os
import time

import jwt
import pytest

# Ensure env vars are set before importing security (which imports config at module level)
os.environ.setdefault("SECRET_KEY", "test-secret-for-security-tests")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from app.config import get_settings  # noqa: E402
from app.core import security  # noqa: E402


def test_token_round_trip():
    token = security.encode_access_token(
        sub="user-123",
        school_id="school-456",
        role="school_admin",
    )
    claims = security.decode_access_token(token)
    assert claims["sub"] == "user-123"
    assert claims["school_id"] == "school-456"
    assert claims["role"] == "school_admin"
    assert "jti" in claims


def test_expired_token_raises():
    settings = get_settings()
    payload = {
        "sub": "user-999",
        "school_id": None,
        "role": "parent",
        "iat": int(time.time()) - 3600,
        "exp": int(time.time()) - 1800,  # expired 30 min ago
        "jti": "test-jti",
    }
    expired_token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    with pytest.raises(jwt.ExpiredSignatureError):
        security.decode_access_token(expired_token)


def test_password_round_trip():
    h = security.hash_password("hunter2")
    assert h != "hunter2"
    assert security.verify_password("hunter2", h)
    assert not security.verify_password("wrong-password", h)
