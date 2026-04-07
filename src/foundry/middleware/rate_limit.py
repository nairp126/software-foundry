"""Rate limiting middleware using Redis."""

import time
from typing import Callable
from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware

from foundry.redis_client import redis_client
from foundry.database import AsyncSessionLocal
from foundry.models.api_key import APIKey
from sqlalchemy import select
import logging

logger = logging.getLogger(__name__)


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
        
        # Get identifier (API key prefix or IP address)
        api_key = request.headers.get("X-API-Key")
        # client is a tuple of (host, port)
        client_host = scope.get("client", ["", 0])[0]
        
        # Use a more stable identifier (prefix for API keys)
        if api_key:
            identifier = APIKey.get_key_prefix(api_key)
        else:
            identifier = client_host
        
        # Check if this path should bypass rate limit enforcement
        path = scope.get("path", "")
        is_bypassed = path in ["/health", "/", "/docs", "/openapi.json"]

        # Check rate limit (do this for all requests to get remaining/reset headers)
        try:
            limit = self.default_limit
            if api_key:
                limit = await self._get_api_key_limit(api_key)
                
            is_allowed, remaining, reset_time = await self._check_rate_limit(
                identifier,
                limit,
                self.window_seconds,
            )
        except Exception as e:
            # Redis unavailable — allow the request through
            logger.warning(f"Rate limiting failed: {e}. Defaulting to allowing request.")
            is_allowed, remaining, reset_time = True, self.default_limit, time.time() + self.window_seconds
            limit = self.default_limit
        
        if not is_allowed and not is_bypassed:
            wait_time = int(reset_time - time.time())
            await send({
                "type": "http.response.start",
                "status": status.HTTP_429_TOO_MANY_REQUESTS,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"x-ratelimit-limit", str(limit).encode()),
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
                headers.append((b"X-RateLimit-Limit", str(limit).encode()))
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
        import hashlib
        redis = redis_client.client
        # Use a hash of the identifier for the Redis key for privacy and consistency
        identifier_hash = hashlib.sha256(identifier.encode()).hexdigest()[:16]
        key = f"rate_limit:{identifier_hash}"
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

    async def _get_api_key_limit(self, api_key: str) -> int:
        """Get custom rate limit from Redis cache or database."""
        redis = redis_client.client
        cache_key = f"api_key_limit:{api_key[:8]}"  # Prefix-based cache key
        
        # 1. Try Redis cache
        cached_limit = await redis.get(cache_key)
        if cached_limit:
            return int(cached_limit)
        
        # 2. Try Database lookup
        try:
            async with AsyncSessionLocal() as session:
                # API keys are stored as prefix/hashes, but identifier here is likely the key from the header
                # Middleware 'identifier' logic says it uses 'api_key' if provided.
                # Actually, the APIKey class has get_key_prefix(key).
                prefix = APIKey.get_key_prefix(api_key)
                result = await session.execute(
                    select(APIKey).where(APIKey.key_prefix == prefix, APIKey.is_active == True)
                )
                key_record = result.scalar_one_or_none()
                
                if key_record:
                    limit = key_record.rate_limit_per_minute
                    # Cache in Redis for 10 minutes
                    await redis.set(cache_key, str(limit), ex=600)
                    return limit
        except Exception as e:
            logger.error(f"Failed to lookup API key limit in DB: {e}")
            
        return self.default_limit
