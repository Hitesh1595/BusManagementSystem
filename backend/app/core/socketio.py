from urllib.parse import parse_qs

import socketio
import structlog

from app.config import get_settings
from app.core.security import decode_access_token

settings = get_settings()
log = structlog.get_logger(__name__)

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=[settings.FRONTEND_URL],
)
sio_app = socketio.ASGIApp(sio)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def user_room(user_id: str) -> str:
    """Personal room for a user (used for `notification` events)."""
    return f"user:{user_id}"


def _token_from_qs(environ: dict) -> str | None:
    """Extract `?token=` from the ASGI/WSGI query string."""
    qs = environ.get("QUERY_STRING", "")
    params = parse_qs(qs)
    tokens = params.get("token", [])
    return tokens[0] if tokens else None


# ---------------------------------------------------------------------------
# Connect / Disconnect
# ---------------------------------------------------------------------------


@sio.event
async def connect(sid: str, environ: dict, auth: dict | None = None) -> None:
    """
    Authenticate the connection via JWT.
    Token sourced from auth["token"] (Socket.IO auth dict) or ?token= query string.
    On failure: raise ConnectionRefusedError so the client receives a "rejected" event.
    """
    token = (auth or {}).get("token") or _token_from_qs(environ)
    try:
        if not token:
            raise ValueError("no token")
        claims = decode_access_token(token)
    except Exception:
        raise socketio.exceptions.ConnectionRefusedError("unauthorized") from None

    user_id = claims["sub"]
    school_id = claims.get("school_id")
    role = claims.get("role", "")

    await sio.save_session(
        sid,
        {
            "user_id": user_id,
            "school_id": school_id,
            "role": role,
        },
    )

    # Each user gets their own personal room for targeted notifications.
    await sio.enter_room(sid, user_room(user_id))

    log.info("socket.connect", sid=sid, user_id=user_id, role=role)


@sio.event
async def disconnect(sid: str) -> None:
    log.info("socket.disconnect", sid=sid)
