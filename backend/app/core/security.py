import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from passlib.context import CryptContext

from app.config import get_settings

settings = get_settings()
_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=settings.BCRYPT_ROUNDS)


def hash_password(p: str) -> str:
    return _pwd.hash(p)


def verify_password(p: str, h: str) -> bool:
    return _pwd.verify(p, h)


def new_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def temp_password() -> str:
    """Generate a human-readable temporary password: 12 random URL-safe chars."""
    return secrets.token_urlsafe(9)  # 12 base64url chars


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def encode_access_token(sub: str, school_id: str | None, role: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": sub,
        "school_id": school_id,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_TTL_MIN),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
