"""Rate limiting middleware."""

from __future__ import annotations

import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter. Replace with Redis-backed in production."""

    def __init__(self, app, requests_per_minute: int = 60):  # type: ignore[no-untyped-def]
        super().__init__(app)
        self.rpm = requests_per_minute
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        if request.url.path in ("/health", "/docs", "/openapi.json", "/redoc"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window = now - 60

        # Clean old entries
        self._requests[client_ip] = [t for t in self._requests[client_ip] if t > window]

        if len(self._requests[client_ip]) >= self.rpm:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded", "retry_after_seconds": 60},
            )

        self._requests[client_ip].append(now)
        return await call_next(request)
