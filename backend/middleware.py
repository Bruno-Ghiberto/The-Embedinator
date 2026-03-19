"""Middleware for CORS, trace ID injection, rate limiting, and structured logging."""

import re
import time
import uuid
from collections import defaultdict

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from backend.config import settings

logger = structlog.get_logger().bind(component=__name__)

_PROVIDER_KEY_PATTERN = re.compile(r"^/api/providers/[^/]+/key$")


class TraceIDMiddleware(BaseHTTPMiddleware):
    """Inject a unique trace ID into every request/response for observability."""

    async def dispatch(self, request: Request, call_next):
        trace_id = str(uuid.uuid4())
        request.state.trace_id = trace_id
        structlog.contextvars.bind_contextvars(trace_id=trace_id)
        try:
            response: Response = await call_next(request)
            response.headers["X-Trace-ID"] = trace_id
            return response
        finally:
            structlog.contextvars.clear_contextvars()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with structured JSON fields (T073)."""

    async def dispatch(self, request: Request, call_next):
        start = time.monotonic()
        trace_id = getattr(request.state, "trace_id", "unknown")

        response = await call_next(request)

        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.info(
            "http_request",
            method=request.method,
            path=str(request.url.path),
            status=response.status_code,
            duration_ms=duration_ms,
            trace_id=trace_id,
            client=request.client.host if request.client else "unknown",
        )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding window rate limiter per endpoint category.

    Limits (per IP, 60-second sliding window):
    - PUT/DELETE /api/providers/*/key: 5/min (provider key management)
    - POST /api/chat: 30/min
    - POST /api/collections/*/ingest: 10/min
    - All other endpoints: 120/min
    """

    def __init__(self, app):
        super().__init__(app)
        self._windows: dict[str, list[float]] = defaultdict(list)

    def _get_limit(self, path: str, method: str) -> int:
        if method in ("PUT", "DELETE") and _PROVIDER_KEY_PATTERN.match(path):
            return settings.rate_limit_provider_keys_per_minute
        if method == "POST" and path == "/api/chat":
            return settings.rate_limit_chat_per_minute
        if method == "POST" and "/ingest" in path:
            return settings.rate_limit_ingest_per_minute
        return settings.rate_limit_general_per_minute

    def _get_bucket(self, path: str, method: str, client_ip: str) -> str:
        if method in ("PUT", "DELETE") and _PROVIDER_KEY_PATTERN.match(path):
            return f"provider_key:{client_ip}"
        if method == "POST" and path == "/api/chat":
            return f"chat:{client_ip}"
        if method == "POST" and "/ingest" in path:
            return f"ingest:{client_ip}"
        return f"general:{client_ip}"

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path
        method = request.method

        bucket = self._get_bucket(path, method, client_ip)
        limit = self._get_limit(path, method)
        now = time.monotonic()
        window = 60.0  # 1-minute sliding window

        # Clean expired entries
        self._windows[bucket] = [
            t for t in self._windows[bucket] if now - t < window
        ]

        if len(self._windows[bucket]) >= limit:
            trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))
            logger.warning(
                "http_rate_limit_exceeded",
                client=client_ip,
                bucket=bucket,
                limit=limit,
                trace_id=trace_id,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": f"Rate limit exceeded: {limit} requests per minute",
                        "details": {"retry_after_seconds": 60},
                    },
                    "trace_id": trace_id,
                },
                headers={"Retry-After": "60"},
            )

        self._windows[bucket].append(now)
        return await call_next(request)
