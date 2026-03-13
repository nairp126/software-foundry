"""Rate limiting middleware using Redis."""

import time
from typing import Callable
from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware

from foundry.redis_client import redis_client


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using sliding window algorithm."""

    def __init__(self, app, default_limit: int = 60, window_seconds: int = 60):
        """Initialize rate limiter.
        
        Args:
            app: FastAPI application
            default_limit: Default requests per window
            window_seconds: Time window in seconds
        """
        super().__init__(app)
        self.default_limit = default_limit
        self.window_seconds = window_seconds

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with rate limiting.
        
        Args:
            request: Incoming request
            call_next: Next middleware/handler
            
        Returns:
            Response from handler
            
        Raises:
            HTTPException: If rate limit exceeded
        """
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/", "/docs", "/openapi.json"]:
            return await call_next(request)
        
        # Get identifier (API key or IP address)
        api_key = request.headers.get("X-API-Key")
        identifier = api_key if api_key else request.client.host
        
        # Check rate limit
        is_allowed, remaining, reset_time = await self._check_rate_limit(
            identifier,
            self.default_limit,
            self.window_seconds,
        )
        
        if not is_allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Try again in {int(reset_time - time.time())} seconds",
                headers={
                    "X-RateLimit-Limit": str(self.default_limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(reset_time)),
                    "Retry-After": str(int(reset_time - time.time())),
                },
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.default_limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(reset_time))
        
        return response

    async def _check_rate_limit(
        self,
        identifier: str,
        limit: int,
        window: int,
    ) -> tuple[bool, int, float]:
        """Check if request is within rate limit.
        
        Args:
            identifier: Unique identifier (API key or IP)
            limit: Max requests per window
            window: Time window in seconds
            
        Returns:
            Tuple of (is_allowed, remaining_requests, reset_timestamp)
        """
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
