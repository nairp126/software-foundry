"""Redis client configuration and connection management."""

from typing import Optional
import logging
import redis.asyncio as redis
from foundry.config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis client wrapper for caching and session management."""

    def __init__(self) -> None:
        """Initialize Redis client."""
        self._client: Optional[redis.Redis] = None

    async def connect(self) -> None:
        """Establish connection to Redis."""
        try:
            self._client = await redis.from_url(
                settings.redis_url,
                max_connections=settings.redis_max_connections,
                encoding="utf-8",
                decode_responses=True,
            )
            # Test connection
            await self._client.ping()
        except Exception as e:
            logger.warning(f"Failed to connect to Redis at {settings.redis_url}: {e}. "
                           "Rate limiting and other Redis-dependent features will be degraded.")
            self._client = None

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()

    @property
    def is_connected(self) -> bool:
        """Check if Redis is connected."""
        return self._client is not None

    @property
    def client(self) -> redis.Redis:
        """Get Redis client instance. Raises RuntimeError if not connected."""
        if not self._client:
            raise RuntimeError("Redis client not connected. Call connect() first.")
        return self._client

    @property
    def safe_client(self) -> Optional[redis.Redis]:
        """Get Redis client instance or None if not connected."""
        return self._client


# Global Redis client instance
redis_client = RedisClient()


async def get_redis() -> redis.Redis:
    """Dependency for getting Redis client."""
    return redis_client.client
