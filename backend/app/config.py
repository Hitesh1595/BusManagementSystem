from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Search for .env in CWD first, then one directory up (repo root when running from backend/).
_HERE = Path(__file__).resolve().parent  # backend/app/
_ENV_PATHS = (
    Path(".env"),          # wherever the process is launched from
    _HERE.parent / ".env", # backend/.env (if placed there)
    _HERE.parent.parent / ".env",  # repo root .env
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[str(p) for p in _ENV_PATHS],
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core
    APP_ENV: str = "dev"
    APP_TIMEZONE: str = "Asia/Kolkata"
    SECRET_KEY: str
    FRONTEND_URL: str = "http://localhost:5173"

    # Database
    DATABASE_URL: str
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30

    # Redis
    REDIS_URL: str

    # Auth
    ACCESS_TOKEN_TTL_MIN: int = 15
    REFRESH_TOKEN_TTL_DAYS: int = 30
    ACCOUNT_LOCKOUT_THRESHOLD: int = 5
    ACCOUNT_LOCKOUT_TTL_MIN: int = 15
    BCRYPT_ROUNDS: int = 12

    # Rate limiting — Redis sliding window (spec §9.4)
    RATELIMIT_WINDOW_SEC: int = 60
    RATELIMIT_AUTH_PER_MIN: int = 5      # /api/v1/auth/* per client IP
    RATELIMIT_API_PER_MIN: int = 100     # all other routes per user (IP fallback)

    # Email
    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "YatraTrack <no-reply@yatratrack.in>"

    # Maps / Geocoding
    STADIA_API_KEY: str = ""
    MAPTILER_API_KEY: str = ""

    # Observability
    SENTRY_DSN: str = ""
    LOG_LEVEL: str = "DEBUG"
    LOG_RETENTION_DAYS: int = 30

    # Scheduling
    TRIP_AUTOGEN_ENABLED: bool = True
    TRIP_AUTOGEN_HOUR: int = 6
    SCHOOL_HOURS_START: int = 6
    SCHOOL_HOURS_END: int = 18

    # GPS
    GPS_FLUSH_INTERVAL_SEC: int = 30
    GPS_STALE_THRESHOLD_SEC: int = 30
    GPS_RETENTION_DAYS: int = 90


@lru_cache
def get_settings() -> Settings:
    return Settings()
