"""Per-worker rate limits; configure edge limits for multi-worker deployment."""
from collections import deque
from time import monotonic
from threading import Lock
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.core.config import get_settings


class RequestLimits(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.buckets = {}
        self.lock = Lock()

    async def dispatch(self, request, call_next):
        settings = get_settings()
        if settings.RATE_LIMIT_ENABLED and request.method != "OPTIONS":
            path = request.url.path
            group = "auth" if path.startswith('/auth/') and request.method == 'POST' else "ai" if path.startswith('/ai/') and request.method == 'POST' else "general"
            maximum = {"auth": 30, "ai": 20, "general": 240}[group]
            key = (request.client.host if request.client else "unknown", group)
            now = monotonic()
            with self.lock:
                if len(self.buckets) > 10000:
                    self.buckets = {k: v for k, v in self.buckets.items() if v and now - v[-1] < 60}
                bucket = self.buckets.setdefault(key, deque())
                while bucket and now - bucket[0] >= 60:
                    bucket.popleft()
                if len(bucket) >= maximum:
                    return JSONResponse({"detail": "Too many requests. Please try again shortly."}, status_code=429, headers={"Retry-After": "60"})
                bucket.append(now)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if settings.ENVIRONMENT == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
