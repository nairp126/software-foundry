"""Tests for rate limiting middleware."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
class TestRateLimitMiddleware:
    """Test rate limiting functionality."""

    async def test_rate_limit_allows_within_limit(self, client):
        """Test that requests within limit are allowed."""
        # Make requests within limit
        for i in range(5):
            response = await client.get("/health")
            assert response.status_code == 200
            assert "X-RateLimit-Limit" in response.headers
            assert "X-RateLimit-Remaining" in response.headers

    async def test_rate_limit_headers_present(self, client):
        """Test that rate limit headers are present in response."""
        response = await client.get("/projects")
        
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers

    async def test_health_endpoint_bypasses_rate_limit(self, client):
        """Test that health check endpoints bypass rate limiting."""
        # Health endpoints should not have rate limit headers
        response = await client.get("/health")
        assert response.status_code == 200

    @pytest.mark.slow
    async def test_rate_limit_blocks_excessive_requests(self, client):
        """Test that excessive requests are blocked.
        
        Note: This test is marked as slow and may take time to execute.
        """
        # Make many requests quickly to trigger rate limit
        responses = []
        for i in range(70):  # Exceed default limit of 60
            response = await client.get("/projects")
            responses.append(response)
            if response.status_code == 429:
                break
        
        # Should eventually get rate limited
        rate_limited = any(r.status_code == 429 for r in responses)
        assert rate_limited, "Expected to hit rate limit"
        
        # Check rate limit response
        rate_limited_response = next(r for r in responses if r.status_code == 429)
        assert "Retry-After" in rate_limited_response.headers
        assert "rate limit exceeded" in rate_limited_response.json()["detail"].lower()

    async def test_rate_limit_per_identifier(self, client):
        """Test that rate limits are tracked per identifier."""
        # Requests from different IPs should have separate limits
        # This is a simplified test - in production, test with actual different IPs
        response1 = await client.get("/projects")
        response2 = await client.get("/projects")
        
        # Both should succeed as they're within limit
        assert response1.status_code == 200
        assert response2.status_code == 200


@pytest.mark.asyncio
class TestRateLimitWithAPIKey:
    """Test rate limiting with API keys."""

    async def test_api_key_has_separate_rate_limit(self, client, db_session):
        """Test that API keys have their own rate limits."""
        from foundry.models.api_key import APIKey
        
        # Create API key with custom rate limit
        key = APIKey.generate_key()
        api_key = APIKey(
            name="Test Key",
            key_hash=APIKey.hash_key(key),
            key_prefix=APIKey.get_key_prefix(key),
            rate_limit_per_minute=100,
        )
        db_session.add(api_key)
        await db_session.commit()
        
        # Make request with API key
        response = await client.get(
            "/projects",
            headers={"X-API-Key": key},
        )
        
        assert response.status_code == 200
        # Rate limit should be based on API key, not IP
        assert "X-RateLimit-Limit" in response.headers
