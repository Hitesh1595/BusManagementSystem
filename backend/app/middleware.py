"""
ASGI middleware stack for YatraTrack.

RequestContextMiddleware — request_id, structlog contextvars, per-request log line.
RateLimitMiddleware      — Redis sliding-window rate limits (spec §9.4, §17.3).
"""

import time
import uuid

import structlog
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import get_settings
from app.redis_client import get_redis

log = structlog.get_logger(__name__)
settings = get_settings()

# ---------------------------------------------------------------------------
# Request context middleware
# ---------------------------------------------------------------------------


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Per-request middleware that:
    1. Generates a request_id (UUID4) and sets it as a response header.
    2. Binds request_id into structlog contextvars so every log line in the
       request carries it automatically.
    3. Logs one structured JSON line per request with method, path,
       status_code, and duration_ms.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())
        start = time.monotonic()

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            user_id=None,
            school_id=None,
        )

        response = await call_next(request)

        duration_ms = round((time.monotonic() - start) * 1000, 2)
        response.headers["X-Request-ID"] = request_id

        # Skip the per-request log for the healthcheck endpoint — the container
        # polls it every ~10s and it carries no diagnostic value.
        if request.url.path != "/health":
            log.info(
                "http.request",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
            )

        return response


# ---------------------------------------------------------------------------
# Rate-limit middleware — Redis sliding window
# Spec §9.4: auth endpoints 5/min per IP; API 100/min per user (or IP fallback).
# On Redis outage → skip limiting (logged), never fatal (spec §17.3).
# ---------------------------------------------------------------------------

_RATE_LIMIT_SCRIPT = """
local key = KEYS[1]
local window = tonumber(ARGV[1])
local limit  = tonumber(ARGV[2])
local now    = tonumber(ARGV[3])
local window_start = now - window * 1000

redis.call('ZREMRANGEBYSCORE', key, '-inf', window_start)
local count = redis.call('ZCARD', key)
if count >= limit then
  return 0
end
redis.call('ZADD', key, now, now .. '-' .. math.random(1, 1000000))
redis.call('PEXPIRE', key, window * 1000)
return 1
"""


async def _check_rate_limit(key: str, window_sec: int, limit: int) -> bool:
    """
    Returns True if the request is allowed, False if rate-limited.
    On Redis errors, returns True (allow) and logs a warning.
    """
    try:
        r = get_redis()
        now_ms = int(time.time() * 1000)
        result = await r.eval(
            _RATE_LIMIT_SCRIPT,
            1,
            key,
            str(window_sec),
            str(limit),
            str(now_ms),
        )
        return bool(result)
    except Exception as exc:
        log.warning("ratelimit.redis_unavailable", key=key, error=str(exc))
        return True  # Degrade gracefully — allow the request


def _rate_limit_response() -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "error": {
                "code": "rate_limited",
                "message": "Too many requests — please slow down",
                "details": {},
            }
        },
    )


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Sliding-window rate limiting:
    - /api/v1/auth/*  → 5 requests / 60 s per client IP
    - everything else → 100 requests / 60 s per user-id (falls back to IP)
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        client_ip = request.client.host if request.client else "unknown"

        if path.startswith("/api/v1/auth"):
            key = f"ratelimit:auth:{client_ip}"
            allowed = await _check_rate_limit(
                key, window_sec=settings.RATELIMIT_WINDOW_SEC, limit=settings.RATELIMIT_AUTH_PER_MIN
            )
        else:
            # For API routes use user-id from JWT if present, else fall back to IP
            auth = request.headers.get("authorization", "")
            if auth.lower().startswith("bearer "):
                # Cheap extraction — we do NOT verify here (auth dep handles that).
                try:
                    import jwt as _jwt

                    payload = _jwt.decode(
                        auth.split(" ", 1)[1],
                        options={"verify_signature": False},
                    )
                    identifier = payload.get("sub", client_ip)
                except Exception:
                    identifier = client_ip
            else:
                identifier = client_ip
            key = f"ratelimit:api:{identifier}"
            allowed = await _check_rate_limit(
                key, window_sec=settings.RATELIMIT_WINDOW_SEC, limit=settings.RATELIMIT_API_PER_MIN
            )

        if not allowed:
            log.warning("ratelimit.rejected", path=path, key=key)
            return _rate_limit_response()

        return await call_next(request)
