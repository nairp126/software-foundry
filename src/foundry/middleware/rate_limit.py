"""Rate limiting middleware using Redis."""

import time
from typing import Callable
from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware

from foundry.redis_client import redis_client


from starlette.types import ASGIApp, Receive, Scope, Send


class RateLimitMiddleware:
    """Rate limiting middleware using pure ASGI to avoid loop issues on Windows."""

    def __init__(self, app: ASGIApp, default_limit: int = 60, window_seconds: int = 60):
        self.app = app
        self.default_limit = default_limit
        self.window_seconds = window_seconds

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        
        # Get identifier (API key or IP address)
        api_key = request.headers.get("X-API-Key")
        # client is a tuple of (host, port)
        client_host = scope.get("client", ["", 0])[0]
        identifier = api_key if api_key else client_host
        
        # Check rate limit (do this for all requests to get remaining/reset headers)
        is_allowed, remaining, reset_time = await self._check_rate_limit(
            identifier,
            self.default_limit,
            self.window_seconds,
        )
        
        # Check if this path should bypass rate limit enforcement
        path = scope.get("path", "")
        is_bypassed = path in ["/health", "/", "/docs", "/openapi.json"]
        
        if not is_allowed and not is_bypassed:
            wait_time = int(reset_time - time.time())
            await send({
                "type": "http.response.start",
                "status": status.HTTP_429_TOO_MANY_REQUESTS,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"x-ratelimit-limit", str(self.default_limit).encode()),
                    (b"x-ratelimit-remaining", b"0"),
                    (b"x-ratelimit-reset", str(int(reset_time)).encode()),
                    (b"retry-after", str(wait_time).encode()),
                ],
            })
            await send({
                "type": "http.response.body",
                "body": f'{{"detail": "Rate limit exceeded. Try again in {wait_time} seconds"}}'.encode(),
            })
            return

        async def send_wrapper(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                # Update headers with rate limit info
                headers.append((b"X-RateLimit-Limit", str(self.default_limit).encode()))
                headers.append((b"X-RateLimit-Remaining", str(remaining).encode()))
                headers.append((b"X-RateLimit-Reset", str(int(reset_time)).encode()))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)

    async def _check_rate_limit(
        self,
        identifier: str,
        limit: int,
        window: int,
    ) -> tuple[bool, int, float]:
        """Check if request is within rate limit."""
        redis = redis_client.client
        key = f"rate_limit:{identifier}"
        now = time.time()
        window_start = now - window
        
        # Use Redis sorted set for sliding window
        pipe = redis.pipeline()
        
        # Remove old entries
        pipe.zremrangebyscore(key, 0, window_start)
        
        # Count current requests
        pipe.zcard(key)
        
        # Add current request
        pipe.zadd(key, {str(now): now})
        
        # Set expiry
        pipe.expire(key, window)
        
        results = await pipe.execute()
        current_count = results[1]
        
        # Calculate remaining and reset time
        is_allowed = current_count < limit
        remaining = max(0, limit - current_count - 1)
        reset_time = now + window
        
        return is_allowed, remaining, reset_time
