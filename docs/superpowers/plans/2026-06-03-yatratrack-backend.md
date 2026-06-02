# YatraTrack Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Use the `fastapi` skill conventions throughout (Annotated deps, return types, router-level prefix/tags, one HTTP op per function).

**Goal:** Build the YatraTrack FastAPI backend through the MVP demo — auth, multi-school entity CRUD, real-time GPS tracking, and the child-safety system — per `docs/YATRATRACK-BUILD-SPEC.md`.

**Architecture:** Single ASGI process (FastAPI + python-socketio mounted together). Modular monolith — feature modules with explicit `include_router()`. PostgreSQL 16 + PostGIS 3.4 (async SQLAlchemy 2.0 + GeoAlchemy2), Redis 7 (GPS buffer, rate-limit, lockout). APScheduler in-process for periodic jobs; asyncio task for GPS flush. No Celery, no object storage in MVP.

**Tech Stack:** Python 3.12, FastAPI 0.115+, SQLAlchemy 2.0 async, Alembic, GeoAlchemy2, python-socketio 5.x, PyJWT, passlib[bcrypt], Redis (redis-py async), APScheduler 3.x, structlog, Sentry, Resend (transactional email), pytest + pytest-asyncio + httpx, Ruff. Managed with `uv`.

**Scope:** This plan covers backend **Steps 1–5** (Phase 1 + Phase 2 backend). The React SPA (Step 6) and all V2 work are separate plans. Build chunks in order; each chunk's acceptance criteria = definition of done. Tag per `§21` of the spec.

**Conventions used in every task:**
- Each module dir: `router.py · models.py · schemas.py · services.py · tests/`. Registration explicit in `main.py`.
- All timestamps `TIMESTAMPTZ` (UTC stored, IST rendered). UUID PKs except `gps_logs`/`audit_logs` (BIGSERIAL).
- Every tenant query filters `school_id` from the JWT claim via the `get_school_scope` dependency.
- Error envelope `{"error":{"code","message","details"}}`. Lists paginated `?limit=50&offset=0` → `{items,total,limit,offset}`.
- TDD: write failing test → run red → minimal impl → run green → commit. Conventional Commits (`feat(scope): …`).

---

## File Structure (backend/)

```
backend/
  pyproject.toml            # uv project, deps, ruff, [tool.fastapi] entrypoint
  Dockerfile                # multi-stage, runs uvicorn (FastAPI+SIO+APScheduler+flusher)
  alembic.ini
  alembic/
    env.py                  # async migrations, imports all models' metadata
    versions/
  app/
    main.py                 # FastAPI + SIO mount + APScheduler start + include_router()
    config.py               # Pydantic Settings (env)
    database.py             # async engine/session, Base
    deps.py                 # get_db, get_current_user, require_role, get_school_scope
    middleware.py           # request_id, CORS, rate limiting, school scope
    redis_client.py         # async redis pool + degradation helper
    errors.py               # error envelope + exception handlers
    core/
      logging.py            # structlog chain + sensitive-data scrubbing
      scheduler.py          # APScheduler registration
      socketio.py           # SIO server + connect auth + ASGIApp
      security.py           # JWT encode/decode, bcrypt hash/verify
      pagination.py         # paginate() helper + Page schema
      geo.py                # lat/lng <-> WKT/Point helpers, geocoding client
    auth/      {router,models,schemas,services}.py + tests/
    schools/   {router,models,schemas,services}.py + tests/
    vehicles/  {router,models,schemas,services}.py + tests/   # vehicles + drivers
    routes/    {router,models,schemas,services}.py + tests/   # routes + stops + transport_requests
    tracking/  {router,models,schemas,services}.py + socket_handlers.py + safety.py + tests/
    notifications/ {router,models,schemas,services}.py + tests/
  tests/
    conftest.py             # async app/client/db fixtures, test DB lifecycle
    factories.py            # create_school/user/vehicle/route(+stops)/student/trip
  docker/logrotate.conf
docker-compose.yml          # app + postgres/postgis + redis(AOF) — at repo root
.github/workflows/ci.yml    # ruff + pytest + coverage gate
```

---

## CHUNK 1 — Scaffold & Core Infra  (Spec Step 1)

**Goal:** `docker compose up` brings up app + PostGIS + Redis; `/health` returns 200 with db+redis status; `pytest` green; structured JSON logs with scrubbing; CI pipeline green. Tag `step-1`.

**Files:**
- Create: `backend/pyproject.toml`, `backend/Dockerfile`, `docker-compose.yml`, `.github/workflows/ci.yml`
- Create: `backend/app/{config,database,redis_client,errors,main,deps,middleware}.py`
- Create: `backend/app/core/{logging,scheduler,socketio,security,pagination,geo}.py`
- Create: `backend/alembic.ini`, `backend/alembic/env.py`
- Create: `backend/tests/{conftest,factories}.py`, `backend/tests/test_health.py`

### Task 1.1: uv project + dependencies

- [ ] **Step 1: Create `backend/pyproject.toml`**

```toml
[project]
name = "yatratrack-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "sqlalchemy[asyncio]>=2.0.30",
    "asyncpg>=0.29",
    "geoalchemy2>=0.15",
    "alembic>=1.13",
    "python-socketio>=5.11",
    "pyjwt>=2.8",
    "passlib[bcrypt]>=1.7",
    "redis>=5.0",
    "apscheduler>=3.10",
    "structlog>=24.1",
    "sentry-sdk[fastapi]>=2.0",
    "pydantic-settings>=2.2",
    "resend>=2.0",
    "httpx>=0.27",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5.0",
    "ruff>=0.5",
]

[tool.fastapi]
entrypoint = "app.main:app"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "ASYNC"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
addopts = "-q --cov=app --cov-report=term-missing"
```

- [ ] **Step 2: Install & verify** — Run: `cd backend && uv sync`. Expected: lockfile created, venv populated, exit 0.

- [ ] **Step 3: Commit** — `git add backend/pyproject.toml && git commit -m "chore(config): scaffold uv project + deps"`

### Task 1.2: Pydantic Settings (config.py)

- [ ] **Step 1: Write `backend/tests/test_config.py`** (failing test)

```python
def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    from app.config import Settings
    s = Settings()
    assert s.SECRET_KEY == "test-secret"
    assert s.ACCESS_TOKEN_TTL_MIN == 15          # default
    assert s.APP_TIMEZONE == "Asia/Kolkata"      # default
```

- [ ] **Step 2: Run red** — `cd backend && uv run pytest tests/test_config.py -v`. Expected: FAIL (`app.config` missing).

- [ ] **Step 3: Write `backend/app/config.py`** (canonical env list from spec §5.2)

```python
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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
```

- [ ] **Step 4: Run green** — `cd backend && uv run pytest tests/test_config.py -v`. Expected: PASS.

- [ ] **Step 5: Commit** — `git commit -am "feat(config): add Pydantic settings"`

### Task 1.3: Async DB engine + Base (database.py)

- [ ] **Step 1: Write `backend/app/database.py`**

```python
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    echo=False,
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
```

- [ ] **Step 2: Commit** — `git commit -am "feat(db): async SQLAlchemy engine + Base + get_db"`

### Task 1.4: Redis client + degradation (redis_client.py)

- [ ] **Step 1: Write `backend/app/redis_client.py`** — async pool + a `redis_ok()` ping used by `/health` and degradation logic (spec §17.3).

```python
import redis.asyncio as redis

from app.config import get_settings

settings = get_settings()
_pool = redis.ConnectionPool.from_url(settings.REDIS_URL, decode_responses=True)


def get_redis() -> redis.Redis:
    return redis.Redis(connection_pool=_pool)


async def redis_ok() -> bool:
    try:
        return await get_redis().ping()
    except Exception:
        return False
```

- [ ] **Step 2: Commit** — `git commit -am "feat(config): async redis client + health ping"`

### Task 1.5: structlog with scrubbing (core/logging.py)

- [ ] **Step 1: Write `backend/tests/test_logging.py`** (failing — verifies scrubbing per spec §18.2)

```python
from app.core.logging import scrub_sensitive

def test_scrub_masks_phone_gps_email_token():
    event = {
        "phone": "+919876543210",
        "lat": 28.612894, "lng": 77.229446,
        "email": "ramesh@school.com",
        "url": "/socket?token=abc.def.ghi&x=1",
        "password": "hunter2",
    }
    out = scrub_sensitive(None, None, dict(event))
    assert out["phone"].endswith("3210") and out["phone"].startswith("***")
    assert out["lat"] == 28.61 and out["lng"] == 77.23      # rounded to 2dp
    assert out["email"] == "***@school.com"
    assert "token=" not in out["url"] or out["url"].split("token=")[1].startswith("***")
    assert out["password"] == "***"
```

- [ ] **Step 2: Run red** — `cd backend && uv run pytest tests/test_logging.py -v`. Expected: FAIL.

- [ ] **Step 3: Write `backend/app/core/logging.py`**

```python
import logging
import re

import structlog

_TOKEN_RE = re.compile(r"(token=)[^&\s]+")


def scrub_sensitive(logger, method_name, event_dict):
    for key in ("password", "new_password", "token", "access_token", "refresh_token"):
        if key in event_dict:
            event_dict[key] = "***"
    if "phone" in event_dict and isinstance(event_dict["phone"], str):
        p = event_dict["phone"]
        event_dict["phone"] = "***" + p[-4:] if len(p) >= 4 else "***"
    for k in ("lat", "lng"):
        if isinstance(event_dict.get(k), (int, float)):
            event_dict[k] = round(event_dict[k], 2)
    if isinstance(event_dict.get("email"), str) and "@" in event_dict["email"]:
        event_dict["email"] = "***@" + event_dict["email"].split("@", 1)[1]
    if isinstance(event_dict.get("url"), str):
        event_dict["url"] = _TOKEN_RE.sub(r"\1***", event_dict["url"])
    return event_dict


def configure_logging(level: str = "DEBUG") -> None:
    logging.basicConfig(format="%(message)s", level=getattr(logging, level.upper(), logging.INFO))
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.contextvars.merge_contextvars,
            scrub_sensitive,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )
```

- [ ] **Step 4: Run green** — `cd backend && uv run pytest tests/test_logging.py -v`. Expected: PASS.

- [ ] **Step 5: Commit** — `git commit -am "feat(config): structlog chain with sensitive-data scrubbing"`

### Task 1.6: Error envelope + handlers (errors.py)

- [ ] **Step 1: Write `backend/app/errors.py`** — `AppError` exception + handlers producing `{"error":{code,message,details}}`; map FastAPI `RequestValidationError` → `validation_error` (422).

```python
from fastapi import FastAPI, Request status as _s  # noqa: E999  -> see note
```

> NOTE: replace the malformed import line above with the real implementation below — kept intentionally minimal so the engineer writes it explicitly:

```python
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(self, code: str, message: str, status: int = 400, details: dict | None = None):
        self.code, self.message, self.status, self.details = code, message, status, details or {}


def _envelope(code: str, message: str, details: dict) -> dict:
    return {"error": {"code": code, "message": message, "details": details}}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return JSONResponse(exc.status, content=_envelope(exc.code, exc.message, exc.details))

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        return JSONResponse(422, content=_envelope("validation_error", "Invalid input", {"errors": exc.errors()}))
```

- [ ] **Step 2: Commit** — `git commit -am "feat(api): standard error envelope + handlers"`

### Task 1.7: Pagination helper + JWT/bcrypt security stubs

- [ ] **Step 1: Write `backend/app/core/pagination.py`** — generic `Page` model (`items,total,limit,offset`) + `paginate(query, db, limit, offset)` running a `count()` then the sliced select; clamp limit to max 100, default 50.
- [ ] **Step 2: Write `backend/app/core/security.py`** — `hash_password`/`verify_password` (passlib bcrypt, rounds from settings); `encode_access_token(sub, school_id, role)` / `decode_access_token` (PyJWT, claims `sub,school_id,role,exp,iat,jti`, 15-min TTL). (Full bodies written/tested in Chunk 2; here just the module + a smoke test that a token round-trips.)
- [ ] **Step 3: Write `backend/tests/test_security.py`** — encode then decode returns same `sub`/`role`; expired token raises. Run red → impl → green.
- [ ] **Step 4: Commit** — `git commit -am "feat(core): pagination helper + JWT/bcrypt security"`

### Task 1.8: Socket.IO server + APScheduler skeleton

- [ ] **Step 1: Write `backend/app/core/socketio.py`** — create `socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=[settings.FRONTEND_URL])` and `socketio.ASGIApp(sio)`. Empty `connect`/`disconnect` handlers for now (JWT auth added in Chunk 4).
- [ ] **Step 2: Write `backend/app/core/scheduler.py`** — `AsyncIOScheduler(timezone=settings.APP_TIMEZONE)`; `start_scheduler()` / `shutdown_scheduler()`; jobs registered in later chunks. Also a `start_gps_flusher()` asyncio-task placeholder (logs a tick; real flush in Chunk 4).
- [ ] **Step 3: Commit** — `git commit -am "feat(core): Socket.IO server + APScheduler skeleton"`

### Task 1.9: App assembly + /health + middleware

- [ ] **Step 1: Write `backend/tests/test_health.py`** (failing)

```python
import pytest


@pytest.mark.anyio
async def test_health_ok(client):
    r = await client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["db"] == "connected"
    assert "redis" in body
```

- [ ] **Step 2: Run red** — `cd backend && uv run pytest tests/test_health.py -v`. Expected: FAIL (no app / fixture).

- [ ] **Step 3: Write `backend/app/middleware.py`** — `RequestContextMiddleware`: generate `request_id`, bind `request_id`/`user_id`/`school_id` into `structlog.contextvars`, log one JSON line per request (`method,path,status_code,duration_ms`). (Rate-limit middleware added in Chunk 2.)

- [ ] **Step 4: Write `backend/app/main.py`** — assemble everything:

```python
import sentry_sdk
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import get_settings
from app.core.logging import configure_logging
from app.core.scheduler import start_scheduler, shutdown_scheduler, start_gps_flusher
from app.core.socketio import sio_app
from app.database import engine
from app.errors import register_error_handlers
from app.middleware import RequestContextMiddleware
from app.redis_client import redis_ok

settings = get_settings()
configure_logging(settings.LOG_LEVEL)
if settings.SENTRY_DSN:
    sentry_sdk.init(dsn=settings.SENTRY_DSN, environment=settings.APP_ENV)


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    flusher = await start_gps_flusher()
    yield
    flusher.cancel()
    shutdown_scheduler()


app = FastAPI(title="YatraTrack API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)
app.add_middleware(RequestContextMiddleware)
register_error_handlers(app)


@app.get("/health")
async def health():
    db = "connected"
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        db = "down"
    status = 200 if db == "connected" else 503
    from fastapi.responses import JSONResponse
    return JSONResponse(status, {
        "status": "ok" if db == "connected" else "degraded",
        "db": db,
        "redis": "connected" if await redis_ok() else "degraded",
        "last_gps_event_at": None,
    })


# Mount Socket.IO last so REST routes win path matching.
app.mount("/socket.io", sio_app)
# include_router() calls added per chunk:
# app.include_router(auth.router); app.include_router(schools.router); ...
```

- [ ] **Step 5: Write `backend/tests/conftest.py`** — `anyio_backend` fixture; `client` fixture using `httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")`; a `db` fixture that creates a schema in a test database and rolls back per test (transactional). Document `DATABASE_URL` for tests points at the compose Postgres.

- [ ] **Step 6: Run green** — `cd backend && uv run pytest tests/test_health.py -v`. Expected: PASS (db connected via test DB).

- [ ] **Step 7: Commit** — `git commit -am "feat(api): app assembly, /health, request-context middleware"`

### Task 1.10: Alembic async setup

- [ ] **Step 1: Write `backend/alembic.ini`** + `backend/alembic/env.py` configured for async engine, importing `Base.metadata` from `app.database` and all module `models` (added as modules land). Enable PostGIS-aware autogenerate (GeoAlchemy2 types).
- [ ] **Step 2: Create initial migration** that runs `CREATE EXTENSION IF NOT EXISTS postgis;` and all enum types from spec §6.1. Run: `cd backend && uv run alembic revision -m "0001 postgis + enums"` then hand-edit, then `uv run alembic upgrade head`. Expected: `SELECT PostGIS_Version();` works.
- [ ] **Step 3: Commit** — `git commit -am "feat(db): alembic async setup + postgis extension + enum types"`

### Task 1.11: Docker Compose + Dockerfile + CI

- [ ] **Step 1: Write `docker-compose.yml`** at repo root — services: `app` (build `backend/`, depends on db+redis, runs `uvicorn app.main:app --host 0.0.0.0 --port 8000`), `db` (`postgis/postgis:16-3.4`, healthcheck), `redis` (`redis:7` with `--appendonly yes --appendfsync everysec`). Env via `.env`.
- [ ] **Step 2: Write `backend/Dockerfile`** — multi-stage: builder installs deps via `uv`; runtime copies venv + app, runs uvicorn.
- [ ] **Step 3: Write `.github/workflows/ci.yml`** — services postgres(postgis)+redis; steps: `uv sync` → `uv run ruff check` → `uv run pytest`; fail if coverage <70% on new code (`--cov-fail-under` scoped per spec §19 — start lenient, document the gate).
- [ ] **Step 4: Verify** — `docker compose up -d` then `curl localhost:8000/health` returns 200 with `db:"connected"`. `docker compose down`.
- [ ] **Step 5: Commit + tag** —
```bash
git commit -am "feat(config): docker-compose, Dockerfile, CI pipeline"
git tag -a step-1 -m "Step 1: Scaffolding & core infra — acceptance passed"
git push origin step-1
```

**Chunk 1 acceptance:** `docker compose up` starts all services; `SELECT PostGIS_Version()` works; `/health` 200 with db+redis; `pytest` green; JSON logs show masked phone/GPS/email/token; CI green.

---

## CHUNK 2 — Auth & Users  (Spec Step 2)

**Goal:** JWT access (15m) + refresh (30d, HttpOnly cookie) with rotation + family theft detection; parent self-register via `join_code`; admin-created drivers/admins; bootstrap seed; account lockout (Redis); password reset via Resend; `GET/PUT /me`; `require_role` + `get_school_scope` deps. Tag `step-2`.

**Files:**
- Create: `backend/app/auth/{models,schemas,services,router}.py`, `backend/app/auth/tests/`
- Create: `backend/app/deps.py` (current-user, require_role, school scope)
- Modify: `backend/app/middleware.py` (rate-limit), `backend/app/main.py` (include auth router, bind user/school to log context)
- Create: `backend/app/core/email.py` (Resend wrapper), `backend/scripts/seed.py` (bootstrap)
- New migration: users, refresh_tokens, auth_tokens, schools (join_code), audit_logs

### Task 2.1: User & token models + migration

- [ ] **Step 1: Write `backend/app/auth/models.py`** — SQLAlchemy 2.0 mapped classes for `User`, `RefreshToken`, `AuthToken` matching spec §6.2/§6.6 exactly (enums `user_role`, `auth_token_type`; `users` has `school_id` nullable, `email_verified`, `notification_prefs JSONB`, `last_login_at`). Also `Schools` model lives in `schools/models.py` but is needed here for FK — import it; if Chunk 3 not built yet, define a minimal `schools` table in this migration (id, name, join_code, settings, is_active, timestamps) and expand it in Chunk 3.

```python
import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, ForeignKey, DateTime, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

ROLE = ("super_admin", "school_admin", "driver", "parent")


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()")
    school_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("schools.id"))
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20))
    role: Mapped[str] = mapped_column(SAEnum(*ROLE, name="user_role"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    email_verified: Mapped[bool] = mapped_column(Boolean, server_default="false")
    notification_prefs: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
# RefreshToken (token_hash, device_id, family_id, issued_at, expires_at, revoked_at)
# AuthToken (token_hash, type, expires_at, used_at) — full fields per spec §6.6
```

- [ ] **Step 2: Generate + apply migration** — `uv run alembic revision -m "0002 users tokens"`, hand-edit to include `idx_users_email_lower` (unique, `lower(email)`) and `idx_users_school_role`, then `uv run alembic upgrade head`.
- [ ] **Step 3: Commit** — `git commit -am "feat(auth): user/token models + migration"`

### Task 2.2: Password hashing + token helpers (complete security.py)

- [ ] **Step 1: Write `backend/app/auth/tests/test_security.py`** (failing)

```python
from app.core import security

def test_password_round_trip():
    h = security.hash_password("hunter2")
    assert h != "hunter2"
    assert security.verify_password("hunter2", h)
    assert not security.verify_password("wrong", h)

def test_refresh_token_hash_is_deterministic_and_opaque():
    raw = security.new_refresh_token()
    assert len(raw) >= 32
    assert security.hash_token(raw) == security.hash_token(raw)
    assert security.hash_token(raw) != raw
```

- [ ] **Step 2: Run red** → implement in `core/security.py`:

```python
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from app.config import get_settings

settings = get_settings()
_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=settings.BCRYPT_ROUNDS)


def hash_password(p: str) -> str: return _pwd.hash(p)
def verify_password(p: str, h: str) -> bool: return _pwd.verify(p, h)

def new_refresh_token() -> str: return secrets.token_urlsafe(32)
def hash_token(raw: str) -> str: return hashlib.sha256(raw.encode()).hexdigest()


def encode_access_token(sub: str, school_id: str | None, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub, "school_id": school_id, "role": role,
        "iat": now, "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_TTL_MIN),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
```

- [ ] **Step 3: Run green** → **Commit** `git commit -am "feat(core): bcrypt + JWT + opaque refresh token helpers"`

### Task 2.3: Account lockout (Redis)

- [ ] **Step 1: Write `backend/app/auth/tests/test_lockout.py`** — after `THRESHOLD` failures `is_locked(email)` true with TTL; success resets. Use a real test Redis (compose). Test with monkeypatched threshold=2.
- [ ] **Step 2: Implement in `auth/services.py`**: `record_failed_login(email)` → `INCR login_attempts:{lower(email)}`, set `EXPIRE` = `ACCOUNT_LOCKOUT_TTL_MIN*60` when count reaches threshold; `is_locked(email)` checks count ≥ threshold; `reset_attempts(email)` → `DEL`. On Redis outage, skip (log warning) — never fatal (spec §17.3).
- [ ] **Step 3: Commit** — `git commit -am "feat(auth): redis account lockout"`

### Task 2.4: Refresh-token rotation + family theft detection (core logic)

- [ ] **Step 1: Write `backend/app/auth/tests/test_refresh_rotation.py`** (the critical security test)

```python
import pytest

@pytest.mark.anyio
async def test_rotation_revokes_previous(db):
    from app.auth import services
    user_id = await _make_user(db)
    raw1, fam = await services.issue_refresh_token(db, user_id, device_id="d1")
    raw2, _ = await services.rotate_refresh_token(db, raw1)          # rotate
    # old token now revoked; new token valid
    assert await services.refresh_is_valid(db, raw2)
    assert not await services.refresh_is_valid(db, raw1)

@pytest.mark.anyio
async def test_reuse_of_revoked_token_revokes_family(db):
    from app.auth import services
    user_id = await _make_user(db)
    raw1, fam = await services.issue_refresh_token(db, user_id, device_id="d1")
    raw2, _ = await services.rotate_refresh_token(db, raw1)
    # attacker replays the already-rotated raw1 -> whole family dies
    with pytest.raises(services.TokenReuseError):
        await services.rotate_refresh_token(db, raw1)
    assert not await services.refresh_is_valid(db, raw2)            # family revoked
```

- [ ] **Step 2: Run red** → implement in `auth/services.py`:

```python
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, update
from app.auth.models import RefreshToken
from app.core.security import new_refresh_token, hash_token
from app.config import get_settings

settings = get_settings()


class TokenReuseError(Exception): ...


async def issue_refresh_token(db, user_id, device_id=None, family_id=None):
    raw = new_refresh_token()
    fam = family_id or uuid.uuid4()
    db.add(RefreshToken(
        user_id=user_id, token_hash=hash_token(raw), device_id=device_id, family_id=fam,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_TTL_DAYS),
    ))
    await db.commit()
    return raw, fam


async def _get_by_hash(db, raw):
    res = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw)))
    return res.scalar_one_or_none()


async def rotate_refresh_token(db, raw):
    row = await _get_by_hash(db, raw)
    if row is None:
        raise TokenReuseError("unknown token")
    if row.revoked_at is not None:
        # reuse of a rotated/revoked token -> kill the whole family
        await db.execute(
            update(RefreshToken).where(RefreshToken.family_id == row.family_id,
                                       RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )
        await db.commit()
        raise TokenReuseError("token reuse detected; family revoked")
    if row.expires_at < datetime.now(timezone.utc):
        raise TokenReuseError("expired")
    row.revoked_at = datetime.now(timezone.utc)
    await db.commit()
    return await issue_refresh_token(db, row.user_id, row.device_id, row.family_id)


async def refresh_is_valid(db, raw):
    row = await _get_by_hash(db, raw)
    return bool(row and row.revoked_at is None and row.expires_at > datetime.now(timezone.utc))


async def revoke_all_families_for_user(db, user_id):
    await db.execute(update(RefreshToken).where(RefreshToken.user_id == user_id,
                     RefreshToken.revoked_at.is_(None)).values(revoked_at=datetime.now(timezone.utc)))
    await db.commit()
```

- [ ] **Step 3: Run green** — `cd backend && uv run pytest app/auth/tests/test_refresh_rotation.py -v`. Expected: both PASS.
- [ ] **Step 4: Commit** — `git commit -am "feat(auth): refresh rotation + family theft detection"`

### Task 2.5: Auth dependencies (deps.py)

- [ ] **Step 1: Write `backend/app/deps.py`**

```python
from typing import Annotated
from uuid import UUID
from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.core.security import decode_access_token
from app.errors import AppError

DbDep = Annotated[AsyncSession, Depends(get_db)]


async def get_current_claims(authorization: Annotated[str | None, Header()] = None) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AppError("unauthorized", "Missing bearer token", 401)
    try:
        return decode_access_token(authorization.split(" ", 1)[1])
    except Exception:
        raise AppError("unauthorized", "Invalid or expired token", 401)

ClaimsDep = Annotated[dict, Depends(get_current_claims)]


def require_role(*roles: str):
    async def _dep(claims: ClaimsDep) -> dict:
        if claims["role"] not in roles:
            raise AppError("forbidden", "Insufficient role", 403)
        return claims
    return _dep


async def get_school_scope(claims: ClaimsDep) -> UUID | None:
    # super_admin (school_id NULL) bypasses scoping; everyone else is scoped.
    sid = claims.get("school_id")
    return UUID(sid) if sid else None

SchoolScopeDep = Annotated[UUID | None, Depends(get_school_scope)]
```

- [ ] **Step 2: Commit** — `git commit -am "feat(auth): current-user, require_role, school scope deps"`

### Task 2.6: Resend email + password reset

- [ ] **Step 1: Write `backend/app/core/email.py`** — thin Resend wrapper `send_email(to, subject, html)`; in `dev` log instead of sending when `RESEND_API_KEY` empty (sandbox).
- [ ] **Step 2: Write `auth/tests/test_password_reset.py`** — `forgot-password` always 200 (no enumeration); creates `auth_tokens(type=password_reset)` only if user exists; `reset-password` validates hash+expiry+unused, sets new hash, marks `used_at`, **revokes all refresh families**. Token is hashed, 1-hr expiry.
- [ ] **Step 3: Implement** reset logic in `auth/services.py` (`request_password_reset`, `reset_password`) using `core/email.py` + `revoke_all_families_for_user`.
- [ ] **Step 4: Run green → Commit** `git commit -am "feat(auth): password reset via Resend with family revoke"`

### Task 2.7: Schemas + router (endpoints)

- [ ] **Step 1: Write `backend/app/auth/schemas.py`** — Pydantic models: `RegisterIn{join_code,email,password,full_name,phone}`, `LoginIn{email,password}`, `TokenOut{access_token,user:UserOut}`, `UserOut{id,email,full_name,role,school_id}`, `ForgotIn{email}`, `ResetIn{token,new_password}`, `MeUpdateIn{full_name?,phone?,notification_prefs?}`. Use `EmailStr`; password `min_length=8`.

- [ ] **Step 2: Write `auth/tests/test_auth_endpoints.py`** — integration tests via `client`:
  - register parent with valid `join_code` → 200; bad join_code → 422; duplicate email → 409
  - login → 200 returns `access_token` + sets HttpOnly refresh cookie; wrong pw → 401; locked after 5 → 423
  - `/refresh` rotates (new access); reused cookie → 401 + family revoked
  - `/logout` revokes family + clears cookie; `GET /me` returns profile; `PUT /me` updates

- [ ] **Step 3: Run red → Write `backend/app/auth/router.py`** (`APIRouter(prefix="/api/v1/auth", tags=["auth"])`). One function per HTTP op. Refresh cookie set with `httponly=True, secure=True, samesite="strict", path="/api/v1/auth"`. Endpoints exactly per spec §8.1:

```
POST /register  POST /login  POST /refresh  POST /logout
POST /forgot-password  POST /reset-password  GET /me  PUT /me
```

Registration validates `join_code` against `schools.join_code`, creates `parent` scoped to that school. Login returns access token + sets refresh cookie via `issue_refresh_token`. `/refresh` reads cookie, calls `rotate_refresh_token` (catches `TokenReuseError` → 401), returns new access + sets new cookie.

- [ ] **Step 4: Register router** in `main.py` (`app.include_router(auth.router)`) and bind `user_id`/`school_id` to log context in middleware after auth.
- [ ] **Step 5: Run green** — `cd backend && uv run pytest app/auth -v`. Expected: all PASS.
- [ ] **Step 6: Commit** — `git commit -am "feat(auth): register/login/refresh/logout/me endpoints"`

### Task 2.8: Rate limiting + bootstrap seed

- [ ] **Step 1: Add rate-limit middleware** in `middleware.py` — Redis sliding window: `ratelimit:auth:{ip}` 5/min on `/auth/*`, `ratelimit:api:{user}` 100/min elsewhere → 429 envelope. On Redis outage, skip (logged). Test with monkeypatched low limits.
- [ ] **Step 2: Write `backend/scripts/seed.py`** — idempotent CLI: create first school (random `join_code`) + first `school_admin` (email/pw from args/env) + a `super_admin`. Run: `uv run python -m scripts.seed`.
- [ ] **Step 3: Commit + tag** —
```bash
git commit -am "feat(auth): rate limiting + bootstrap seed"
git tag -a step-2 -m "Step 2: Auth & users — acceptance passed"
git push origin step-2
```

**Chunk 2 acceptance:** all auth endpoints pass integration tests; refresh reuse revokes family; lockout after 5 fails, unlocks after 15m; access token carries `school_id`+`role`; password-reset email sends in dev (Resend sandbox); parent cannot register without valid `join_code`.

---

## CHUNK 3 — Schools & Entity CRUD  (Spec Step 3)

**Goal:** Schools CRUD + settings + join_code regen + `school_location`; vehicles, drivers, routes, stops (reorder + GIST), students, transport requests + `suggest-stop` (geocode → `ST_Distance` top-3); assignment with capacity guard; optimistic `version` lock. Every query scoped by `school_id`. Tag `step-3` + `v0.3.0-alpha`.

**Files:**
- Create modules: `schools/`, `vehicles/` (vehicles + drivers), `routes/` (routes + stops + transport_requests). Each: `{models,schemas,services,router}.py + tests/`.
- Create: `app/core/geo.py` (lat/lng↔Point, geocoding client per `APP_ENV`), shared `app/crud.py` helper.
- New migrations expanding `schools` and adding `students,vehicles,routes,route_stops,student_route_assignments,transport_requests` per spec §6.2/§6.3.

### Task 3.0: Shared school-scoped CRUD helper + geo utils

- [ ] **Step 1: Write `backend/app/crud.py`** — generic helpers so every endpoint stays DRY and scoping is enforced in one place:

```python
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.errors import AppError


async def get_scoped_or_404(db: AsyncSession, model, obj_id: UUID, school_id: UUID | None):
    stmt = select(model).where(model.id == obj_id)
    if school_id is not None:                          # super_admin (None) bypasses
        stmt = stmt.where(model.school_id == school_id)
    obj = (await db.execute(stmt)).scalar_one_or_none()
    if obj is None:
        raise AppError("not_found", f"{model.__name__} not found", 404)
    return obj


def scoped_select(model, school_id: UUID | None, active_only: bool = True):
    stmt = select(model)
    if school_id is not None:
        stmt = stmt.where(model.school_id == school_id)
    if active_only and hasattr(model, "is_active"):
        stmt = stmt.where(model.is_active.is_(True))
    return stmt
```

- [ ] **Step 2: Write `backend/app/core/geo.py`** — helpers:
  - `to_point(lat, lng) -> WKTElement` (`SRID=4326;POINT(lng lat)`), `from_point(geom) -> {lat,lng}`.
  - `linestring_from_stops(points) -> WKTElement` for `route_path`.
  - `geocode(address) -> {lat,lng} | None` — Nominatim public in dev, MapTiler (`MAPTILER_API_KEY`) in prod, chosen by `APP_ENV`, via httpx.
- [ ] **Step 3: Test geo helpers** (`tests/test_geo.py`): round-trip `to_point`/`from_point`; geocode mocked via httpx transport. Run red→green.
- [ ] **Step 4: Commit** — `git commit -am "feat(db): scoped CRUD helper + PostGIS geo utils"`

### Task 3.1: Schools module

- [ ] **Step 1: Write `schools/models.py`** — full `School` per spec §6.2 (expand the minimal table from Chunk 2: add `address,phone,email,logo_url,timezone,school_location(Point),settings JSONB`). Migration to alter table.
- [ ] **Step 2: Write `schools/tests/test_schools.py`** — admin can `GET/PUT` own school; `PUT /settings` merges JSONB (not replace); `POST /regenerate-join-code` rotates; admin of School A gets 404 on School B. Run red.
- [ ] **Step 3: Write `schools/{schemas,services,router}.py`** — router `prefix="/api/v1/schools"`. Endpoints per spec §8.2:
```
POST / (super_admin V2)   GET / (super_admin V2)   GET /{id}   PUT /{id}
PUT /{id}/settings        POST /{id}/regenerate-join-code
```
  `PUT /{id}/settings` deep-merges into `settings` JSONB. `school_location` accepted as `{lat,lng}` → `to_point`.
- [ ] **Step 4: Run green → register router → Commit** `git commit -am "feat(schools): CRUD + settings merge + join-code regen"`

### Task 3.2: Vehicles module (the reference CRUD — full code)

This is the canonical CRUD pattern; later modules follow it.

- [ ] **Step 1: Write `vehicles/models.py`** — `Vehicle` per spec §6.3 (`plate_number,vehicle_type,capacity>0,make,model,year,insurance_expiry,fitness_expiry,is_active`, `UNIQUE(school_id,plate_number)`).
- [ ] **Step 2: Write `vehicles/tests/test_vehicles.py`** (failing)

```python
import pytest

@pytest.mark.anyio
async def test_vehicle_crud_and_scope(client, admin_token, other_admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    r = await client.post("/api/v1/vehicles", json={"plate_number": "DL1PC1234", "capacity": 40}, headers=h)
    assert r.status_code == 201
    vid = r.json()["id"]
    # duplicate plate in same school -> 409
    r2 = await client.post("/api/v1/vehicles", json={"plate_number": "DL1PC1234", "capacity": 30}, headers=h)
    assert r2.status_code == 409
    # other school cannot see it -> 404
    r3 = await client.get(f"/api/v1/vehicles/{vid}", headers={"Authorization": f"Bearer {other_admin_token}"})
    assert r3.status_code == 404
    # capacity must be > 0 -> 422
    r4 = await client.post("/api/v1/vehicles", json={"plate_number": "X", "capacity": 0}, headers=h)
    assert r4.status_code == 422
```

- [ ] **Step 3: Run red → Write `vehicles/schemas.py`** — `VehicleIn`, `VehicleUpdate`, `VehicleOut`. `capacity: int = Field(gt=0)`.
- [ ] **Step 4: Write `vehicles/services.py`** — uses `app.crud`; create catches unique violation → `AppError("conflict",409)`; `delete` is soft (`is_active=false`) and **blocked (409) if vehicle has active/scheduled trip** (query `trips` once that table exists — until Chunk 4, leave a guarded check that no-ops if table absent, with a TODO referencing Chunk 4).
- [ ] **Step 5: Write `vehicles/router.py`** (`prefix="/api/v1/vehicles", tags=["vehicles"]`, router-level `dependencies=[Depends(require_role("school_admin","super_admin"))]`):

```python
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from app.deps import DbDep, SchoolScopeDep, require_role
from app.vehicles import schemas, services

router = APIRouter(prefix="/api/v1/vehicles", tags=["vehicles"],
                   dependencies=[Depends(require_role("school_admin", "super_admin"))])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_vehicle(body: schemas.VehicleIn, db: DbDep, school_id: SchoolScopeDep) -> schemas.VehicleOut:
    return await services.create(db, body, school_id)


@router.get("")
async def list_vehicles(db: DbDep, school_id: SchoolScopeDep,
                        limit: Annotated[int, Query(le=100)] = 50,
                        offset: Annotated[int, Query(ge=0)] = 0) -> schemas.VehiclePage:
    return await services.list_(db, school_id, limit, offset)


@router.get("/{vehicle_id}")
async def get_vehicle(vehicle_id: UUID, db: DbDep, school_id: SchoolScopeDep) -> schemas.VehicleOut:
    return await services.get(db, vehicle_id, school_id)


@router.put("/{vehicle_id}")
async def update_vehicle(vehicle_id: UUID, body: schemas.VehicleUpdate, db: DbDep,
                         school_id: SchoolScopeDep) -> schemas.VehicleOut:
    return await services.update(db, vehicle_id, body, school_id)


@router.delete("/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vehicle(vehicle_id: UUID, db: DbDep, school_id: SchoolScopeDep) -> None:
    await services.soft_delete(db, vehicle_id, school_id)
```

- [ ] **Step 6: Run green → register → Commit** `git commit -am "feat(vehicles): vehicle CRUD with scope + capacity + plate-unique"`

### Task 3.3: Drivers (admin-created users, role=driver)

- [ ] **Step 1: Write `vehicles/tests/test_drivers.py`** — admin `POST /drivers` creates a `users` row (role=driver) scoped to school + emails/returns a temp password once; `GET /drivers` lists school drivers; `POST /{id}/assign {vehicle_id}` writes an `audit_logs` row; `GET /{id}/schedule` and `/{id}/trips` (stubbed until Chunk 4) return empty lists.
- [ ] **Step 2: Implement** in `vehicles/services.py` + a `drivers` router (`prefix="/api/v1/drivers"`) reusing `auth` user creation + `core/email.py`. Endpoints per spec §8.4.
- [ ] **Step 3: Run green → Commit** `git commit -am "feat(drivers): admin-managed driver users + assign + audit"`

### Task 3.4: Routes + stops

- [ ] **Step 1: Write `routes/models.py`** — `Route` (`route_path LineString,schedule_type,version`), `RouteStop` (`location Point NOT NULL,stop_order,arrival_time`, `UNIQUE(route_id,stop_order)`, GIST index), per spec §6.3.
- [ ] **Step 2: Write `routes/tests/test_routes.py`** — create route; add stops (lat/lng → Point); reorder via `{ordered_stop_ids}` renumbers `stop_order`; **optimistic lock**: `PUT` with stale `version` → 409; `route_path` auto-built as LineString from ordered stops.
- [ ] **Step 3: Implement** `routes/{schemas,services,router}.py` (`prefix="/api/v1/routes"`). Endpoints per spec §8.5:
```
POST/GET/GET{id}/PUT{id}/DELETE{id}   POST /{id}/stops   PUT /{id}/stops/{sid}
DELETE /{id}/stops/{sid}              PUT /{id}/stops/reorder
GET /{id}/students                    POST /{id}/students {student_id,stop_id} (capacity-checked)
```
  Update checks `body.version == route.version` else `AppError("conflict",409)`; on success `version += 1`. Reorder updates `stop_order` in one transaction. After stop changes, rebuild `route_path` via `geo.linestring_from_stops`.
- [ ] **Step 4: Run green → register → Commit** `git commit -am "feat(routes): routes + stops + reorder + optimistic lock"`

### Task 3.5: Students + transport requests + suggest-stop (the PostGIS feature)

- [ ] **Step 1: Write models** — `Student` (parent-owned, `pickup_location Point`, GIST), `StudentRouteAssignment` (`UNIQUE(student_id,route_id)`), `TransportRequest` (`status enum,assigned_route_id,assigned_stop_id,admin_notes`), per spec §6.2/§6.3.
- [ ] **Step 2: Write `routes/tests/test_transport_requests.py`** — covers the full flow + the geospatial query:

```python
import pytest

@pytest.mark.anyio
async def test_suggest_stop_returns_nearest_first(client, parent_token, seeded_route_with_stops):
    # stops seeded at known coords; query a point ~180m from "Sector 12 Gate"
    h = {"Authorization": f"Bearer {parent_token}"}
    r = await client.get("/api/v1/transport-requests/suggest-stop?lat=28.6129&lng=77.2295", headers=h)
    assert r.status_code == 200
    s = r.json()["suggestions"]
    assert len(s) <= 3
    assert s[0]["distance_m"] <= s[-1]["distance_m"]      # ascending by distance

@pytest.mark.anyio
async def test_assign_creates_assignment_with_capacity_guard(client, admin_token, pending_request, full_route):
    h = {"Authorization": f"Bearer {admin_token}"}
    r = await client.put(f"/api/v1/transport-requests/{pending_request}",
                         json={"status": "assigned", "assigned_route_id": full_route["id"],
                               "assigned_stop_id": full_route["stop_id"]}, headers=h)
    assert r.status_code == 409          # route at capacity
```

- [ ] **Step 3: Run red → Implement** `suggest-stop`: geocode if address given, else use `lat/lng`; PostGIS query ordered by distance:

```python
from geoalchemy2.functions import ST_Distance, ST_DWithin
from app.core.geo import to_point

async def suggest_stops(db, school_id, lat, lng, k=3):
    pt = to_point(lat, lng)
    stmt = (
        select(
            RouteStop.id, RouteStop.route_id, RouteStop.name, RouteStop.arrival_time,
            ST_Distance(RouteStop.location, pt).label("distance_m"),
        )
        .join(Route, Route.id == RouteStop.route_id)
        .where(Route.school_id == school_id, Route.is_active.is_(True))
        .order_by("distance_m")
        .limit(k)
    )
    rows = (await db.execute(stmt)).all()
    return [{"stop_id": str(r.id), "route_id": str(r.route_id), "name": r.name,
             "distance_m": round(r.distance_m), "arrival_time": r.arrival_time} for r in rows]
```

  Endpoints per spec §8.6: `POST/GET/GET{id}/PUT{id}` + `GET /suggest-stop`. On `PUT status='assigned'`, create `student_route_assignments` row inside the same transaction with a **capacity check** (count active assignments on route vs `vehicle.capacity`) → 409 if full. Parents see only own requests; admins see all (filter `?status=`).
- [ ] **Step 4: Run green → register → Commit** `git commit -am "feat(routes): students + transport requests + suggest-stop + capacity guard"`

### Task 3.6: Cross-tenant isolation test + tag

- [ ] **Step 1: Write `tests/test_tenant_isolation.py`** — seed School A and School B; assert every list/detail endpoint for an A-admin never returns B data and vice-versa (loop over vehicles/routes/students/requests).
- [ ] **Step 2: Run full suite** — `cd backend && uv run pytest -v`. Expected: all green.
- [ ] **Step 3: Commit + tag** —
```bash
git commit -am "test(api): cross-tenant isolation coverage"
git tag -a step-3 -m "Step 3: Schools & entity CRUD — acceptance passed"
git tag -a v0.3.0-alpha -m "Alpha: entity layer complete"
git push origin step-3 v0.3.0-alpha
```

**Chunk 3 acceptance:** full CRUD works; transport-request flow completes end-to-end; suggest-stop returns nearest within 1 km; School-A data invisible to School-B users; capacity guard returns 409 on overflow; stale `version` update returns 409.

---

## CHUNK 4 — Trips & Real-Time GPS  (Spec Step 4)

**Goal:** Trip model + `POST /trips` + `POST /trips/generate` + `generate_daily_trips` job + `check_driver_no_show` job; Socket.IO connect-auth + `join_trip` room auth; `location_update` (driver-only, ≤1/3s) → broadcast to room + Redis buffer; 30s asyncio flush → partitioned `gps_logs`; ETA (straight-line) + `bus_approaching`; `tracking_paused` at >30s. Tag `step-4`.

**Files:**
- Create: `tracking/models.py` (`Trip`, `GpsLog`), `tracking/{schemas,services,router}.py`, `tracking/socket_handlers.py`, `tracking/gps_buffer.py`
- Modify: `core/socketio.py` (JWT connect auth), `core/scheduler.py` (real flusher + jobs), `main.py` (`last_gps_event_at` in `/health`)
- New migration: `trips` (+ indexes incl. `UNIQUE(route_id,scheduled_date,slot)`), `gps_logs` partitioned by `recorded_at` + initial partitions

### Task 4.1: Trip model + GPS log (partitioned)

- [ ] **Step 1: Write `tracking/models.py`** — `Trip` per spec §6.4 (all columns incl. `scheduled_departure_at`, `slot CHECK in (morning,evening)`, `current_stop_order`, `safeguarding_checked`, substitute-flow cols). `GpsLog` mapped to the partitioned table (composite PK `(id,recorded_at)`).
- [ ] **Step 2: Migration** — create `trips` with all four indexes from spec (incl. `idx_trips_route_date_slot UNIQUE`). Create `gps_logs` as `PARTITION BY RANGE (recorded_at)` with the two indexes; create the current + next month partitions inline. Apply.
- [ ] **Step 3: Commit** — `git commit -am "feat(trips): trip + partitioned gps_logs models + migration"`

### Task 4.2: Trip generation (endpoint + service)

- [ ] **Step 1: Write `tracking/tests/test_trip_generate.py`**

```python
import pytest

@pytest.mark.anyio
async def test_generate_is_idempotent_and_sets_departure(client, admin_token, route_both_slots):
    h = {"Authorization": f"Bearer {admin_token}"}
    r1 = await client.post("/api/v1/trips/generate", json={"scheduled_date": "2026-06-04"}, headers=h)
    assert r1.status_code == 200
    n1 = r1.json()["created"]
    assert n1 == 2                       # 'both' route -> morning + evening
    r2 = await client.post("/api/v1/trips/generate", json={"scheduled_date": "2026-06-04"}, headers=h)
    assert r2.json()["created"] == 0     # idempotent (UNIQUE route,date,slot)
    # scheduled_departure_at set from first stop's arrival_time on that date
    trips = (await client.get("/api/v1/trips?date=2026-06-04", headers=h)).json()["items"]
    assert all(t["scheduled_departure_at"] for t in trips)
```

- [ ] **Step 2: Run red → Implement `generate_trips(db, school_id, scheduled_date)`** in `tracking/services.py` — for each active route with `trip_autogen_enabled` (per school settings) and a driver+vehicle, create a trip per slot (`both`→2). `scheduled_departure_at` = combine `scheduled_date` + first stop's `arrival_time` in school timezone → UTC. Rely on `UNIQUE(route_id,date,slot)` + `ON CONFLICT DO NOTHING` for idempotency; return `{created}`.
- [ ] **Step 3: Implement endpoints** (`prefix="/api/v1/trips"`) per spec §8.7: `POST /` (manual), `POST /generate`, `GET /` (filter `?date=&route_id=&status=`), `GET /{id}` (driver phone conditional — full logic in Chunk 5; here return `phone:null`), `GET /active`, `GET /{id}/gps-log` (GeoJSON LineString). Driver-only: `PUT /{id}/start`, `PUT /{id}/end` (end is stubbed → completed; real safeguard gate in Chunk 5), admin: `PUT /{id}/cancel`.
- [ ] **Step 4: Run green → register → Commit** `git commit -am "feat(trips): generate + CRUD + start/cancel endpoints"`

### Task 4.3: Socket.IO connect auth + rooms

- [ ] **Step 1: Write `tracking/tests/test_socket_auth.py`** — using `socketio.AsyncClient` (or `AsyncServer.handle_request` harness): connect without token → refused; with valid access token → connected; `join_trip` for a parent whose child is on the trip's route → ack ok; unrelated parent → rejected.
- [ ] **Step 2: Implement connect auth in `core/socketio.py`**

```python
import socketio
from app.config import get_settings
from app.core.security import decode_access_token

settings = get_settings()
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=[settings.FRONTEND_URL])
sio_app = socketio.ASGIApp(sio)


@sio.event
async def connect(sid, environ, auth):
    token = (auth or {}).get("token") or _token_from_qs(environ)
    try:
        claims = decode_access_token(token)
    except Exception:
        raise socketio.exceptions.ConnectionRefusedError("unauthorized")
    await sio.save_session(sid, {"user_id": claims["sub"], "school_id": claims.get("school_id"),
                                 "role": claims["role"]})
```

- [ ] **Step 3: Implement `join_trip`/`leave_trip` in `tracking/socket_handlers.py`** — `join_trip {trip_id}`: authorize per spec §9.2 (requester's child assigned to trip's route OR is the trip's driver OR school admin of that school) → `sio.enter_room(sid, f"trip:{trip_id}")`; admins also join `school:{school_id}`. Reject otherwise. Register handlers on import; import in `main.py`.
- [ ] **Step 4: Run green → Commit** `git commit -am "feat(socket): JWT connect auth + room join authorization"`

### Task 4.4: GPS ingestion, buffer, broadcast, ETA

- [ ] **Step 1: Write `tracking/tests/test_location_update.py`** — emit `location_update` as the trip's driver → a subscribed parent client receives a `location_update`; a 2nd update within 3s is dropped (rate limit); a non-driver emitting is ignored; point lands in `gps:buffer:{trip_id}` Redis list.
- [ ] **Step 2: Implement `location_update` handler** in `socket_handlers.py` (synchronous, sub-ms — no blocking DB calls per spec §17.2):

```python
import json
from app.redis_client import get_redis
from app.tracking.eta import eta_and_approaching

LOC_RATE_KEY = "ratelimit:loc:{sid}"


@sio.event
async def location_update(sid, data):
    sess = await sio.get_session(sid)
    trip_id = data["trip_id"]
    if not await _is_trip_driver(sess["user_id"], trip_id):     # cached check
        return
    r = get_redis()
    # rate limit ≤1/3s per connection; drop excess silently
    if not await r.set(LOC_RATE_KEY.format(sid=sid), "1", nx=True, ex=3):
        return
    point = {"lat": data["lat"], "lng": data["lng"], "speed": data.get("speed"),
             "heading": data.get("heading"), "accuracy": data.get("accuracy"), "ts": data["ts"]}
    await r.rpush(f"gps:buffer:{trip_id}", json.dumps(point))     # 3c buffer
    eta_s, approaching = await eta_and_approaching(trip_id, data["lat"], data["lng"])  # 3d
    await sio.emit("location_update", {**point, "trip_id": trip_id, "eta_next_stop_s": eta_s},
                   room=f"trip:{trip_id}")                        # 3b broadcast
    if approaching:
        await sio.emit("bus_approaching", approaching, room=f"trip:{trip_id}")
    await r.set(f"gps:last:{trip_id}", data["ts"])               # for tracking_paused + /health
```

- [ ] **Step 3: Write `tracking/eta.py`** — straight-line distance (haversine) to next stop ÷ rolling-avg speed (from recent buffered points); if within `bus_approaching_radius_m` (school setting, default 200) of next stop → return approaching payload `{trip_id,stop_id,distance_m,eta_s}`. Pure-Python, no DB round-trip on the hot path (stop coords cached in Redis on trip start).
- [ ] **Step 4: Run green → Commit** `git commit -am "feat(gps): location_update ingest + rate-limit + broadcast + ETA"`

### Task 4.5: Redis→Postgres flusher + tracking_paused

- [ ] **Step 1: Write `tracking/gps_buffer.py`** — `flush_gps_buffer()`: scan `gps:buffer:*` keys, `LRANGE`+`LTRIM` drain each, batch `INSERT` into `gps_logs` (monthly partition by `recorded_at`). On Redis outage, the `location_update` handler falls back to direct PG insert (spec §17.3) — implement that fallback path too.
- [ ] **Step 2: Replace the Chunk-1 flusher placeholder** in `core/scheduler.py` with a real asyncio task looping every `GPS_FLUSH_INTERVAL_SEC`, calling `flush_gps_buffer()`; flush once more on shutdown.
- [ ] **Step 3: Implement `tracking_paused`** — a lightweight APScheduler job (or piggyback the flusher) that, for each in-progress trip, checks `gps:last:{trip_id}`; if older than `GPS_STALE_THRESHOLD_SEC`, emit `tracking_paused {trip_id,last_lat,last_lng,last_updated_at}` to the room (once per stale period).
- [ ] **Step 4: Write `tracking/tests/test_flush.py`** — push N points to a buffer, run `flush_gps_buffer()`, assert N rows in `gps_logs` and buffer emptied. **Test idempotency/no-loss** under a simulated Redis-down (fallback writes directly).
- [ ] **Step 5: Wire `/health`** `last_gps_event_at` from the newest `gps:last:*` (or `MAX(recorded_at)`).
- [ ] **Step 6: Run green → Commit** `git commit -am "feat(gps): 30s buffer flush + tracking_paused + health wiring"`

### Task 4.6: Scheduled jobs (autogen + no-show + partitions)

- [ ] **Step 1: Write `tracking/tests/test_jobs.py`** — call jobs directly (not via scheduler):
  - `check_driver_no_show`: a `scheduled` trip with `scheduled_departure_at + 15min < now` → creates one `alerts(type=driver_no_show,severity=high)` + admin notifications; running twice doesn't double-alert (idempotent).
  - `generate_daily_trips`: creates today's trips for autogen-enabled routes.
  - `ensure_gps_partitions`: creates next-month partition if missing.
- [ ] **Step 2: Implement jobs** in `core/scheduler.py` registration (all idempotent, emit structured logs `task_name,duration_ms,status,school_id`) per spec §11:
```
generate_daily_trips    06:00 IST
check_driver_no_show     every 5 min, 06:00–18:00 IST
check_vehicle_compliance 07:00 IST (insurance/fitness 30/7/1-day → alert; on expiry deactivate)
ensure_gps_partitions    00:30 IST
cleanup_gps_logs         01:00 IST (drop partitions > GPS_RETENTION_DAYS)
```
  (Add `driver_no_show` to `alert_type` enum — already in spec §6.1; ensure migration includes it.) Note: `alerts`/`notifications` tables are needed here — create them now (spec §6.5/§6.6) since the safety chunk and these jobs both use them.
- [ ] **Step 3: Run green → Commit + tag** —
```bash
git commit -am "feat(jobs): autogen, no-show, compliance, partition lifecycle"
git tag -a step-4 -m "Step 4: Trips & real-time GPS — acceptance passed"
git push origin step-4
```

**Chunk 4 acceptance:** driver shares location → parent sees update <1s; GPS persists to partitioned `gps_logs`; unauthorized socket rejected; rate limit enforced; stale GPS shows "tracking paused"; no-show alert fires 15 min past `scheduled_departure_at`.

---

## CHUNK 5 — Safety System  (Spec Step 5, §10)

**Goal:** The product's core differentiator. Attendance batch (UPSERT) = stop-complete trigger → not-boarded detection; drop-off endpoints (school/stop); not-dropped safeguarding gate → `pending_safeguard_check`; **atomic, idempotent** trip completion; parent absent-marking; driver-phone disclosure (§10.5) + audit log; in-app notifications persisted + emitted. Tag `step-5`.

**Files:**
- Create: `tracking/safety.py` (all four behaviors), `tracking/attendance_schemas.py`
- Modify: `tracking/router.py` (attendance/drop/absent endpoints), `tracking/services.py` (end-trip gate), `notifications/` (persist + emit)
- New migration (if not already in Chunk 4): `attendance_records`, `alerts`, `notifications` per spec §6.5/§6.6 (with all indexes; `UNIQUE(trip_id,student_id)`)

> **Why one chunk:** §10 explicitly states all four behaviors interconnect so no false alerts fire. Build and test them together.

### Task 5.1: Attendance model + notifications plumbing

- [ ] **Step 1: Write `tracking/models.py` additions** — `AttendanceRecord` per spec §6.5 (`stop_id` nullable, `status attendance_status`, `marked_by`, `marked_location`, `drop_type`, `drop_stop_id`, `dropped_at`, `UNIQUE(trip_id,student_id)`). `Alert` per §6.5. (Tables created in Chunk 4 migration if you front-loaded them; else migrate now.)
- [ ] **Step 2: Write `notifications/services.py`** — `notify(db, user_id, school_id, type, title, body, data)`: insert a `notifications` row AND `sio.emit("notification", {...}, room=user_room(user_id))` if connected. Also a helper `emit_to_school(school_id, event, payload)`. Test: row persisted; emit called (mock sio).
- [ ] **Step 3: Commit** — `git commit -am "feat(safety): attendance/alert models + notification dispatch"`

### Task 5.2: Not-boarded detection (§10.1)

- [ ] **Step 1: Write `tracking/tests/test_not_boarded.py`**

```python
import pytest

@pytest.mark.anyio
async def test_unmarked_assigned_student_triggers_alert(client, driver_token, trip_with_two_assigned):
    h = {"Authorization": f"Bearer {driver_token}"}
    trip = trip_with_two_assigned
    # submit attendance for ONLY one of the two assigned students at the stop
    body = {"attendance": [{"student_id": trip["student_boarded"], "status": "boarded"}]}
    r = await client.post(f"/api/v1/trips/{trip['id']}/stops/{trip['stop_id']}/attendance",
                          json=body, headers=h)
    assert r.status_code == 200
    assert r.json()["alerts_triggered"] == 1            # the unmarked student
    # the alert exists and targets the missing student
    # (and a child_not_boarded socket event + notifications to parent + admins)

@pytest.mark.anyio
async def test_parent_absent_student_does_not_alert(client, driver_token, trip_with_absent_marked):
    h = {"Authorization": f"Bearer {driver_token}"}
    trip = trip_with_absent_marked       # one student pre-marked absent_parent_marked
    body = {"attendance": [{"student_id": trip["other_student"], "status": "boarded"}]}
    r = await client.post(f"/api/v1/trips/{trip['id']}/stops/{trip['stop_id']}/attendance",
                          json=body, headers=h)
    assert r.json()["alerts_triggered"] == 0            # absent student silently skipped
```

- [ ] **Step 2: Run red → Implement `process_stop_attendance` in `safety.py`**:

```python
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.routes.models import StudentRouteAssignment
from app.tracking.models import AttendanceRecord, Trip
from app.alerts.models import Alert  # or tracking-local Alert model


async def process_stop_attendance(db, sio, trip: Trip, stop_id, entries):
    # 1. UPSERT each submitted record (this submit == "stop complete")
    for e in entries:
        stmt = pg_insert(AttendanceRecord).values(
            school_id=trip.school_id, trip_id=trip.id, student_id=e["student_id"],
            stop_id=stop_id, status=e["status"], marked_by=trip.driver_id,
        ).on_conflict_do_update(
            index_elements=["trip_id", "student_id"],
            set_={"status": e["status"], "stop_id": stop_id},
        )
        await db.execute(stmt)

    # 2. not-boarded detection: assigned to THIS stop but neither submitted nor parent-absent
    assigned = (await db.execute(
        select(StudentRouteAssignment.student_id).where(
            StudentRouteAssignment.route_id == trip.route_id,
            StudentRouteAssignment.stop_id == stop_id,
            StudentRouteAssignment.is_active.is_(True),
        )
    )).scalars().all()
    submitted = {e["student_id"] for e in entries}
    existing = {r.student_id: r.status for r in (await db.execute(
        select(AttendanceRecord).where(AttendanceRecord.trip_id == trip.id))).scalars()}

    alerts = 0
    for student_id in assigned:
        if student_id in submitted:
            continue
        if existing.get(student_id) == "absent_parent_marked":
            continue                                   # expected absence, no alert
        await _raise_not_boarded(db, sio, trip, student_id, stop_id)
        alerts += 1
    await db.commit()
    return {"processed": len(entries), "alerts_triggered": alerts}
```

  `_raise_not_boarded`: create `alerts(type=child_not_boarded,severity=high,metadata={student_id,stop_id})`, emit `child_not_boarded` to parent + `school:{id}`, `notify()` parent + admins.
- [ ] **Step 3: Wire endpoint** `POST /trips/{trip_id}/stops/{stop_id}/attendance` (driver-only) → `process_stop_attendance`. Add `GET /trips/{trip_id}/attendance` + per-stop variant.
- [ ] **Step 4: Run green → Commit** `git commit -am "feat(safety): not-boarded detection on stop-complete"`

### Task 5.3: Drop-off + the atomic safeguarding gate (§10.2 — the critical one)

- [ ] **Step 1: Write `tracking/tests/test_safeguarding_gate.py`** (the mandatory safety tests, spec §19)

```python
import asyncio
import pytest

@pytest.mark.anyio
async def test_end_trip_blocks_when_boarded_not_dropped(client, driver_token, trip_one_boarded):
    h = {"Authorization": f"Bearer {driver_token}"}
    r = await client.put(f"/api/v1/trips/{trip_one_boarded['id']}/end", headers=h)
    assert r.status_code == 200
    assert r.json()["status"] == "pending_safeguard_check"
    assert trip_one_boarded["student"] in r.json()["unresolved_students"]
    # trip cannot be 'completed'
    detail = (await client.get(f"/api/v1/trips/{trip_one_boarded['id']}", headers=h)).json()
    assert detail["status"] == "pending_safeguard_check"

@pytest.mark.anyio
async def test_drop_resolves_and_completes_exactly_once(client, driver_token, trip_pending_safeguard):
    h = {"Authorization": f"Bearer {driver_token}"}
    body = {"student_ids": [trip_pending_safeguard["student"]], "drop_type": "school"}
    r = await client.post(f"/api/v1/trips/{trip_pending_safeguard['id']}/drop", json=body, headers=h)
    assert r.status_code == 200
    detail = (await client.get(f"/api/v1/trips/{trip_pending_safeguard['id']}", headers=h)).json()
    assert detail["status"] == "completed"

@pytest.mark.anyio
async def test_completion_is_idempotent_under_concurrent_resolve_and_drop(db, trip_pending_safeguard):
    # fire admin-resolve and driver-drop concurrently; trip_ended emitted exactly once
    from app.tracking import safety
    results = await asyncio.gather(
        safety.resolve_alert_and_maybe_complete(db, trip_pending_safeguard["alert_id"]),
        safety.drop_students(db, trip_pending_safeguard["id"], [trip_pending_safeguard["student"]], "school"),
        return_exceptions=True,
    )
    completed_emits = sum(1 for r in results if getattr(r, "completed", False))
    assert completed_emits == 1            # exactly one caller transitioned to completed
```

- [ ] **Step 2: Run red → Implement the gate in `safety.py`**:

```python
from datetime import datetime, timezone
from sqlalchemy import select, update, func
from app.tracking.models import Trip, AttendanceRecord


async def end_trip(db, sio, trip: Trip):
    unresolved = (await db.execute(
        select(AttendanceRecord.student_id).where(
            AttendanceRecord.trip_id == trip.id,
            AttendanceRecord.status == "boarded",
            AttendanceRecord.dropped_at.is_(None),
        )
    )).scalars().all()

    if not unresolved:
        await _complete_trip(db, sio, trip.id)         # atomic; emits trip_ended
        return {"status": "completed", "unresolved_students": []}

    # block: raise CRITICAL per student, flip to pending_safeguard_check
    for sid in unresolved:
        await _raise_not_dropped(db, sio, trip, sid)   # alerts(child_not_dropped,critical) + emit school
    await db.execute(update(Trip).where(Trip.id == trip.id, Trip.status == "in_progress")
                     .values(status="pending_safeguard_check"))
    await db.commit()
    return {"status": "pending_safeguard_check", "unresolved_students": [str(s) for s in unresolved]}


async def _complete_trip(db, sio, trip_id):
    # rows_affected guards double-fire under concurrency (spec §10.2)
    res = await db.execute(
        update(Trip).where(Trip.id == trip_id,
                           Trip.status.in_(("in_progress", "pending_safeguard_check")))
        .values(status="completed", safeguarding_checked=True)
    )
    await db.commit()
    if res.rowcount > 0:                                # only the winning caller emits
        await sio.emit("trip_ended", {"trip_id": str(trip_id)}, room=f"trip:{trip_id}")
        return type("R", (), {"completed": True})()
    return type("R", (), {"completed": False})()


async def drop_students(db, sio, trip_id, student_ids, drop_type, drop_stop_id=None):
    await db.execute(
        update(AttendanceRecord).where(AttendanceRecord.trip_id == trip_id,
                                       AttendanceRecord.student_id.in_(student_ids))
        .values(dropped_at=datetime.now(timezone.utc), drop_type=drop_type, drop_stop_id=drop_stop_id)
    )
    # auto-resolve matching child_not_dropped alerts for these students
    await _resolve_not_dropped_alerts(db, trip_id, student_ids)
    await db.commit()
    return await _complete_if_clear(db, sio, trip_id)


async def _complete_if_clear(db, sio, trip_id):
    remaining = (await db.execute(
        select(func.count()).select_from(AttendanceRecord).where(
            AttendanceRecord.trip_id == trip_id,
            AttendanceRecord.status == "boarded",
            AttendanceRecord.dropped_at.is_(None),
        )
    )).scalar_one()
    if remaining == 0:
        return await _complete_trip(db, sio, trip_id)
    return type("R", (), {"completed": False})()
```

  `resolve_alert_and_maybe_complete(db, alert_id)` (admin path, `PUT /alerts/{id}/resolve`): mark alert resolved, then `_complete_if_clear`. Both paths converge on `_complete_trip`'s `rowcount` guard → idempotent.
- [ ] **Step 3: Wire endpoints** — `PUT /trips/{id}/end` → `end_trip`; `POST /trips/{id}/drop` (spec §8.8 body: school = one tap for all; stop = per-stop with `stop_id`) → `drop_students`. Create `alerts` router (`GET /alerts`, `PUT /{id}/acknowledge`, `PUT /{id}/resolve`) per spec §8.10.
- [ ] **Step 4: Run green** — `cd backend && uv run pytest tracking/tests/test_safeguarding_gate.py -v`. Expected: all PASS incl. the concurrency test.
- [ ] **Step 5: Commit** — `git commit -am "feat(safety): atomic idempotent not-dropped gate + drop-off"`

### Task 5.4: Parent absent-marking (§10.3)

- [ ] **Step 1: Write `tracking/tests/test_absent_marking.py`** — parent `POST /trips/{id}/absent/{student_id}` before `in_progress` → creates `attendance(status=absent_parent_marked,marked_by=parent)` + emits `child_absent_marked` to driver; after `in_progress` → 409; `DELETE` cancels only while not `in_progress`; only the child's own parent may mark (else 403).
- [ ] **Step 2: Implement** endpoints per spec §8.9 (`POST`/`DELETE /trips/{id}/absent/{student_id}`, `GET /trips/{id}/absences` for driver). Cutoff check: `trip.status == "scheduled"` to allow.
- [ ] **Step 3: Run green → Commit** `git commit -am "feat(safety): parent absent-marking with start cutoff"`

### Task 5.5: Driver-phone disclosure + audit (§10.5)

- [ ] **Step 1: Write `tracking/tests/test_driver_phone.py`** — `GET /trips/{id}` returns `driver.phone` ONLY if requester is the child's parent AND `trip.status=='in_progress'` AND `school.settings.driver_phone_visible==true`; each disclosure writes `audit_logs(action='driver_phone_viewed')`; otherwise `phone:null` and no audit row.
- [ ] **Step 2: Implement** the conditional in the `GET /trips/{id}` serializer (replace the Chunk-4 `phone:null` stub). Write audit row inside the same request.
- [ ] **Step 3: Run green → Commit** `git commit -am "feat(safety): conditional driver-phone disclosure + audit log"`

### Task 5.6: Full safety suite + tag

- [ ] **Step 1: Run mandatory safety tests together** — `cd backend && uv run pytest -k "safety or boarded or dropped or absent or phone" -v`. All green.
- [ ] **Step 2: Run full suite + coverage** — `cd backend && uv run pytest`. Coverage ≥70% on business logic.
- [ ] **Step 3: Commit + tag** —
```bash
git tag -a step-5 -m "Step 5: Safety system — acceptance passed"
git push origin step-5
```

**Chunk 5 acceptance:** unmarked assigned student → parent gets `child_not_boarded` <2s; parent-absent student → no alert + driver sees greyed; end trip with boarded-not-dropped → CRITICAL alert + status `pending_safeguard_check`, cannot reach `completed`; resolving last alert (admin) or marking drop (driver) completes trip exactly once (idempotent under concurrency); driver phone disclosed only under all three §10.5 conditions + audited.

---

## After Chunk 5

Backend MVP API is feature-complete. Remaining MVP work is **Step 6 (React SPA)** — a separate plan (use the `ui-ux-pro-max` and `frontend-design` skills). The Week-8 demo (`v1.0.0-mvp` tag) ships after Step 6 integrates against this API.

**V2 backend** (Steps 7–11: RLS hardening, deviation/push/SOS, substitute driver/broadcasts, feedback/complaints/reports/payments) are separate plans — the schema already reserves their tables (spec §6.7).

---

## Self-Review

- **Spec coverage:** Steps 1–5 of §21 each map to a chunk; §6 tables created across chunks (core+auth in 1–2, fleet/routing in 3, trips/gps in 4, safety/alerts/notifications in 4–5); §7 auth, §8 endpoints, §9 socket, §10 safety, §11 jobs all covered. V2 tables (§6.7) intentionally deferred.
- **Type consistency:** `get_school_scope`/`SchoolScopeDep`, `require_role`, `AppError`, `process_stop_attendance`, `end_trip`/`_complete_trip`/`drop_students` names used consistently across chunks.
- **Known forward-references handled:** `alerts`/`notifications` tables are needed by both Chunk 4 jobs and Chunk 5 — plan front-loads their migration into Chunk 4 (Task 4.6 Step 2) and reuses in Chunk 5. Vehicle soft-delete's "active trip" guard (Task 3.2) depends on `trips` (Chunk 4) — guarded as a no-op until then.

