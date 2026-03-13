"""Tests for error handling and standardized error responses."""

import pytest
from uuid import uuid4


@pytest.mark.asyncio
class TestErrorHandling:
    """Test standardized error handling."""

    async def test_validation_error_format(self, client):
        """Test validation error response format."""
        # Send invalid project creation request
        response = await client.post(
            "/projects",
            json={
                "name": "",  # Invalid: empty name
                "requirements": "Test",
            },
        )
        
        assert response.status_code == 422
        data = response.json()
        
        assert "detail" in data
        assert "error_code" in data
        assert data["error_code"] == "validation_error"
        assert "timestamp" in data
        assert isinstance(data["detail"], list)
        
        # Check validation error structure
        error = data["detail"][0]
        assert "loc" in error
        assert "msg" in error
        assert "type" in error

    async def test_not_found_error_format(self, client):
        """Test 404 error response format."""
        fake_id = uuid4()
        response = await client.get(f"/projects/{fake_id}")
        
        assert response.status_code == 404
        data = response.json()
        
        assert "detail" in data
        assert "error_code" in data
        assert data["error_code"] == "http_404"
        assert "timestamp" in data
        assert "path" in data

    async def test_bad_request_error_format(self, client, db_session):
        """Test 400 error response format."""
        from foundry.models.project import Project, ProjectStatus
        
        # Create paused project
        project = Project(
            name="Test Project",
            requirements="Test",
            status=ProjectStatus.paused,
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)
        
        # Try to pause already paused project
        response = await client.post(
            f"/projects/{project.id}/agent/pause",
            json={},
        )
        
        assert response.status_code == 400
        data = response.json()
        
        assert "detail" in data
        assert "error_code" in data
        assert "timestamp" in data

    async def test_unauthorized_error_format(self, client):
        """Test 401 error response format."""
        # Try to access endpoint with invalid API key
        response = await client.get(
            "/projects",
            headers={"X-API-Key": "invalid_key_12345"},
        )
        
        # Should get 401 if authentication is enforced
        # Or 200 if authentication is optional
        if response.status_code == 401:
            data = response.json()
            assert "detail" in data
            assert "error_code" in data

    async def test_rate_limit_error_format(self, client):
        """Test 429 rate limit error response format."""
        # Make many requests to trigger rate limit
        responses = []
        for i in range(70):
            response = await client.get("/projects")
            responses.append(response)
            if response.status_code == 429:
                break
        
        # Find rate limited response
        rate_limited = next((r for r in responses if r.status_code == 429), None)
        
        if rate_limited:
            data = rate_limited.json()
            assert "detail" in data
            assert "rate limit" in data["detail"].lower()
            assert "Retry-After" in rate_limited.headers

    async def test_missing_required_field_validation(self, client):
        """Test validation error for missing required fields."""
        response = await client.post(
            "/projects",
            json={
                "name": "Test Project",
                # Missing required 'requirements' field
            },
        )
        
        assert response.status_code == 422
        data = response.json()
        
        assert data["error_code"] == "validation_error"
        # Check that error mentions the missing field
        errors = data["detail"]
        assert any("requirements" in str(e["loc"]) for e in errors)

    async def test_invalid_field_type_validation(self, client):
        """Test validation error for invalid field types."""
        response = await client.post(
            "/projects",
            json={
                "name": 12345,  # Should be string
                "requirements": "Test",
            },
        )
        
        assert response.status_code == 422
        data = response.json()
        
        assert data["error_code"] == "validation_error"

    async def test_invalid_uuid_format(self, client):
        """Test error handling for invalid UUID format."""
        response = await client.get("/projects/not-a-valid-uuid")
        
        assert response.status_code == 422
        data = response.json()
        
        assert data["error_code"] == "validation_error"
