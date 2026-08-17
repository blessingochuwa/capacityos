"""Request correlation and duration logging (Phase 9 spec §5). One
middleware, not a framework: reads/generates an X-Request-ID, times the
request, logs exactly one structured line per request via
app.core.logging.JsonFormatter, and echoes the id back in the response
header so a caller can correlate a specific HTTP response with the exact
log lines it produced.

Sits OUTSIDE FastAPI's exception-handling layer (added before
register_exception_handlers wires up @app.exception_handler, per Starlette's
middleware-stack ordering), so by the time control returns here, any
exception a route raised has already become a normal Response via
app/core/exceptions.py's handlers — this middleware only ever sees
responses, never exceptions, keeping request-lifecycle logging and
error-detail logging in one place each rather than split across both.
"""

import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.core.logging import request_id_var

logger = logging.getLogger("capacityos.request")

REQUEST_ID_HEADER = "X-Request-ID"


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            level = logging.WARNING if response.status_code >= 500 else logging.INFO
            logger.log(
                level,
                "request completed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                },
            )
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            request_id_var.reset(token)


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    """Rejects a request whose declared Content-Length exceeds max_bytes
    before any body is read. A Content-Length check, not a streaming
    byte-count, so it only catches honestly-reported sizes — sufficient for
    this app's realistic threat model (an accidentally-or-deliberately huge
    JSON payload on a non-import endpoint), not a hardened anti-DoS measure.
    Set to the same ceiling as Settings.import_max_file_size_bytes by
    default so import uploads, this app's one legitimately larger body,
    aren't rejected here before reaching ImportService's own, more specific,
    Level-1 file-size error."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        content_length = request.headers.get("content-length")
        if content_length is not None and int(content_length) > self.max_bytes:
            return JSONResponse(
                status_code=413,
                content={"detail": "Request body exceeds the maximum allowed size."},
            )
        return await call_next(request)
