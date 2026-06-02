import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

log = structlog.get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Per-request middleware that:
    1. Generates a request_id (UUID4) and sets it as a response header.
    2. Binds request_id into structlog contextvars so every log line in the
       request carries it automatically.
    3. Logs one structured JSON line per request with method, path,
       status_code, and duration_ms.

    Note: user_id / school_id are bound here as empty strings and will be
    overwritten by the auth dependency once the JWT is decoded (Chunk 2).
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

        log.info(
            "http.request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

        return response
