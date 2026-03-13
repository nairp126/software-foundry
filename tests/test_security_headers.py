"""Tests for security headers middleware."""

import pytest


@pytest.mark.asyncio
class TestSecurityHeaders:
    """Test security headers are properly set."""

    async def test_hsts_header(self, client):
        """Test Strict-Transport-Security header is set."""
        response = await client.get("/health")
        assert "Strict-Transport-Security" in response.headers
        assert "max-age=31536000" in response.headers["Strict-Transport-Security"]
        assert "includeSubDomains" in response.headers["Strict-Transport-Security"]

    async def test_csp_header(self, client):
        """Test Content-Security-Policy header is set."""
        response = await client.get("/health")
        assert "Content-Security-Policy" in response.headers
        csp = response.headers["Content-Security-Policy"]
        assert "default-src 'self'" in csp
        assert "script-src" in csp
        assert "style-src" in csp

    async def test_x_frame_options(self, client):
        """Test X-Frame-Options header is set."""
        response = await client.get("/health")
        assert "X-Frame-Options" in response.headers
        assert response.headers["X-Frame-Options"] == "DENY"

    async def test_x_content_type_options(self, client):
        """Test X-Content-Type-Options header is set."""
        response = await client.get("/health")
        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"

    async def test_x_xss_protection(self, client):
        """Test X-XSS-Protection header is set."""
        response = await client.get("/health")
        assert "X-XSS-Protection" in response.headers
        assert "1; mode=block" in response.headers["X-XSS-Protection"]

    async def test_referrer_policy(self, client):
        """Test Referrer-Policy header is set."""
        response = await client.get("/health")
        assert "Referrer-Policy" in response.headers
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    async def test_permissions_policy(self, client):
        """Test Permissions-Policy header is set."""
        response = await client.get("/health")
        assert "Permissions-Policy" in response.headers
        permissions = response.headers["Permissions-Policy"]
        assert "geolocation=()" in permissions
        assert "microphone=()" in permissions
        assert "camera=()" in permissions

    async def test_all_security_headers_on_api_endpoints(self, client):
        """Test that all security headers are present on API endpoints."""
        response = await client.get("/projects")
        
        required_headers = [
            "Strict-Transport-Security",
            "Content-Security-Policy",
            "X-Frame-Options",
            "X-Content-Type-Options",
            "X-XSS-Protection",
            "Referrer-Policy",
            "Permissions-Policy",
        ]
        
        for header in required_headers:
            assert header in response.headers, f"Missing security header: {header}"
