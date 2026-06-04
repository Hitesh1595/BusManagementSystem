from contextlib import asynccontextmanager

import sentry_sdk
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.auth import router as auth_router
from app.config import get_settings
from app.core.logging import configure_logging
from app.core.scheduler import shutdown_scheduler, start_gps_flusher, start_scheduler
from app.core.socketio import sio_app
from app.database import engine
from app.errors import register_error_handlers
from app.middleware import RateLimitMiddleware, RequestContextMiddleware
from app.redis_client import redis_ok
from app.schools import router as schools_router

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

    # last_gps_event_at: populated in Chunk 4 when real GPS flush is live
    last_gps_event_at = None

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

# Mount Socket.IO last so REST routes win path matching.
app.mount("/socket.io", sio_app)

# Routers added per chunk:
# app.include_router(vehicles.router)
# app.include_router(routes.router)
# app.include_router(tracking.router)
# app.include_router(notifications.router)
