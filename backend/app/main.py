from contextlib import asynccontextmanager

import sentry_sdk
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.alerts.router import router as alerts_router
from app.auth import router as auth_router
from app.config import get_settings
from app.core.logging import configure_logging
from app.core.scheduler import shutdown_scheduler, start_gps_flusher, start_scheduler
from app.core.socketio import sio_app
from app.database import engine
from app.errors import register_error_handlers
from app.middleware import RateLimitMiddleware, RequestContextMiddleware
from app.notifications.router import router as notifications_router
from app.redis_client import redis_ok
from app.routes.router import router as routes_router
from app.schools import router as schools_router
from app.students.router import students_router, transport_router
from app.super_admin.router import router as super_admin_router
from app.tracking.router import router as trips_router
from app.users.router import router as users_router
from app.vehicles.router import drivers_router, vehicles_router

settings = get_settings()
configure_logging(settings.LOG_LEVEL)

if settings.SENTRY_DSN:
    sentry_sdk.init(dsn=settings.SENTRY_DSN, environment=settings.APP_ENV)

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("app.startup", env=settings.APP_ENV)
    start_scheduler()
    flusher = await start_gps_flusher()
    yield
    flusher.cancel()
    shutdown_scheduler()
    log.info("app.shutdown")


app = FastAPI(title="YatraTrack API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestContextMiddleware)
register_error_handlers(app)


@app.get("/health", tags=["ops"])
async def health() -> JSONResponse:
    """
    Returns the current service health.
    - db: "connected" | "down"
    - redis: "connected" | "degraded"
    - last_gps_event_at: ISO timestamp from Redis or null
    """
    db_status = "connected"
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        db_status = "down"

    redis_status = "connected" if await redis_ok() else "degraded"

    # last_gps_event_at: newest gps:last:* value from Redis; fallback to DB MAX
    last_gps_event_at = None
    try:
        from app.redis_client import get_redis as _get_redis

        r = _get_redis()
        # Scan all gps:last:* keys and find the newest timestamp
        keys: list[str] = []
        cursor = 0
        while True:
            cursor, batch = await r.scan(cursor, match="gps:last:*", count=200)
            keys.extend(batch)
            if cursor == 0:
                break

        if keys:
            values = await r.mget(*keys)
            best: float | None = None
            for v in values:
                if v is None:
                    continue
                try:
                    ts = float(v)
                    if best is None or ts > best:
                        best = ts
                except ValueError:
                    try:
                        from datetime import datetime as _dt

                        ts2 = _dt.fromisoformat(v).timestamp()
                        if best is None or ts2 > best:
                            best = ts2
                    except Exception:
                        pass
            if best is not None:
                from datetime import UTC as _UTC
                from datetime import datetime as _dt

                last_gps_event_at = _dt.fromtimestamp(best, tz=_UTC).isoformat()
    except Exception:
        pass  # Redis degraded — last_gps_event_at stays None

    # DB fallback if Redis had nothing
    if last_gps_event_at is None and db_status == "connected":
        try:


            async with engine.connect() as conn:
                result = await conn.execute(
                    text("SELECT MAX(recorded_at) FROM gps_logs")
                )
                row = result.fetchone()
                if row and row[0] is not None:
                    last_gps_event_at = row[0].isoformat()
        except Exception:
            pass

    http_status = 200 if db_status == "connected" else 503
    return JSONResponse(
        status_code=http_status,
        content={
            "status": "ok" if db_status == "connected" else "degraded",
            "db": db_status,
            "redis": redis_status,
            "last_gps_event_at": last_gps_event_at,
        },
    )


app.include_router(auth_router.router)
app.include_router(schools_router.router)
app.include_router(vehicles_router)
app.include_router(drivers_router)
app.include_router(users_router)
app.include_router(routes_router)
app.include_router(students_router)
app.include_router(transport_router)
app.include_router(trips_router)
app.include_router(alerts_router)
app.include_router(notifications_router)
app.include_router(super_admin_router)

# Mount Socket.IO last so REST routes win path matching.
app.mount("/socket.io", sio_app)

# Import socket handlers so @sio.on(...) registrations run at startup.
# NOTE: use an aliased import — a bare `import app.tracking.socket_handlers`
# would rebind the module-level name `app` to the package, clobbering the
# FastAPI instance above.
from app.tracking import socket_handlers as _socket_handlers  # noqa: E402, F401

# Chunk 5B: alerts router registered above.
