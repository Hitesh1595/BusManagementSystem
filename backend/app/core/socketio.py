import structlog
import socketio

from app.config import get_settings

settings = get_settings()
log = structlog.get_logger(__name__)

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=[settings.FRONTEND_URL],
)
sio_app = socketio.ASGIApp(sio)


@sio.event
async def connect(sid: str, environ: dict, auth: dict | None = None) -> None:
    """Accept the connection — JWT auth added in Chunk 4."""
    log.info("socket.connect", sid=sid)


@sio.event
async def disconnect(sid: str) -> None:
    log.info("socket.disconnect", sid=sid)
