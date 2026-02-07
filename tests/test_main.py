"""Test FastAPI application."""

import pytest
from httpx import AsyncClient
from foundry.main import app


@pytest.mark.asyncio
async def test_root_endpoint():
    """Test root endpoint returns correct response."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "autonomous-software-foundry"
        assert data["version"] == "0.1.0"
        assert data["status"] == "running"


@pytest.mark.asyncio
async def test_health_endpoint():
    """Test health check endpoint."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
