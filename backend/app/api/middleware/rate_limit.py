"""
In-memory sliding window rate limiter middleware — Phase 6 Guardrails.

Limits requests per unique client IP using a rolling 60-second window.
Thread-safe via asyncio.Lock — suitable for single-process deployments.

For multi-worker / distributed deployments, swap the in-memory store for
a Redis-backed counter (Phase 8 roadmap item).

Configuration
-------------
RATE_LIMIT_PER_MINUTE in .env (default: 60)

Exempt paths
------------
/docs, /redoc, /openapi.json, /api/v1/health
These are always allowed through regardless of rate limit.

Headers returned on 429
-----------------------
Retry-After: <seconds until the oldest request in the window expires>
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

log = structlog.get_logger(__name__)

_EXEMPT_PREFIXES = (
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/v1/health",
)

_RATE_LIMIT_RESPONSE = (
    '{"error":{"code":"RATE_LIMIT_EXCEEDED",'
    '"message":"Too many requests. Please slow down."}}'
)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Sliding window rate limiter keyed by client IP.

    Each IP is allowed ``requests_per_minute`` requests in any rolling
    60-second window. Excess requests receive HTTP 429 immediately.
    """

    def __init__(self, app, requests_per_minute: int = 60) -> None:
        super().__init__(app)
        self._rpm = requests_per_minute
        self._window = 60.0  # seconds
        # IP → deque of monotonic timestamps for requests in the window
        self._store: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if any(path.startswith(p) for p in _EXEMPT_PREFIXES):
            return await call_next(request)

        ip = _client_ip(request)
        now = time.monotonic()

        async with self._lock:
            window = self._store[ip]

            # Evict timestamps that have fallen outside the rolling window
            while window and window[0] <= now - self._window:
                window.popleft()

            if len(window) >= self._rpm:
                retry_after = max(1, int(self._window - (now - window[0])) + 1)
                log.warning(
                    "rate_limit_exceeded",
                    ip=ip,
                    requests_in_window=len(window),
                    limit=self._rpm,
                )
                return Response(
                    content=_RATE_LIMIT_RESPONSE,
                    status_code=429,
                    media_type="application/json",
                    headers={"Retry-After": str(retry_after)},
                )

            window.append(now)

        return await call_next(request)


def _client_ip(request: Request) -> str:
    """
    Extract the real client IP, trusting X-Forwarded-For from upstream proxies.

    WARNING: Only trust X-Forwarded-For when the app is behind a known reverse
    proxy (Nginx, AWS ALB, etc.). In direct-exposure deployments, the header
    can be spoofed by clients to bypass rate limiting.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
