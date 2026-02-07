"""Redis client configuration and connection management."""

from typing import Optional
import redis.asyncio as redis
from foundry.config import settings


class RedisClient:
    """Redis client wrapper for caching and session management."""

    def __init__(self) -> None:
        """Initialize Redis client."""
        self._client: Optional[redis.Redis] = None

    async def connect(self) -> None:
        """Establish connection to Redis."""
        self._client = await redis.from_url(
            settings.redis_url,
            max_connections=settings.redis_max_connections,
            encoding="utf-8",
            decode_responses=True,
        )

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()

    @property
    def client(self) -> redis.Redis:
        """Get Redis client instance."""
        if not self._client:
            raise RuntimeError("Redis client not connected. Call connect() first.")
        return self._client


# Global Redis client instance
redis_client = RedisClient()


async def get_redis() -> redis.Redis:
    """Dependency for getting Redis client."""
    return redis_client.client
