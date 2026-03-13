"""Tests for API key authentication system."""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from foundry.models.api_key import APIKey


class TestAPIKeyModel:
    """Test API key model functionality."""

    def test_generate_key(self):
        """Test API key generation."""
        key = APIKey.generate_key()
        assert key.startswith("asf_")
        assert len(key) > 20

    def test_hash_key(self):
        """Test API key hashing."""
        key = "asf_test_key_12345"
        hash1 = APIKey.hash_key(key)
        hash2 = APIKey.hash_key(key)
        
        # Same key should produce same hash
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 produces 64 hex chars

    def test_get_key_prefix(self):
        """Test key prefix extraction."""
        key = "asf_test_key_12345"
        prefix = APIKey.get_key_prefix(key)
        assert prefix == "asf_test"
        assert len(prefix) == 8

    def test_is_valid_active_key(self):
        """Test validation of active key without expiration."""
        api_key = APIKey(
            name="Test Key",
            key_hash="hash123",
            key_prefix="asf_test",
            is_active=True,
            expires_at=None,
        )
        assert api_key.is_valid() is True

    def test_is_valid_inactive_key(self):
        """Test validation of inactive key."""
        api_key = APIKey(
            name="Test Key",
            key_hash="hash123",
            key_prefix="asf_test",
            is_active=False,
            expires_at=None,
        )
        assert api_key.is_valid() is False

    def test_is_valid_expired_key(self):
        """Test validation of expired key."""
        api_key = APIKey(
            name="Test Key",
            key_hash="hash123",
            key_prefix="asf_test",
            is_active=True,
            expires_at=datetime.utcnow() - timedelta(days=1),
        )
        assert api_key.is_valid() is False

    def test_is_valid_not_yet_expired(self):
        """Test validation of key that hasn't expired yet."""
        api_key = APIKey(
            name="Test Key",
            key_hash="hash123",
            key_prefix="asf_test",
            is_active=True,
            expires_at=datetime.utcnow() + timedelta(days=1),
        )
        assert api_key.is_valid() is True

    def test_verify_key_correct(self):
        """Test key verification with correct key."""
        key = "asf_test_key_12345"
        api_key = APIKey(
            name="Test Key",
            key_hash=APIKey.hash_key(key),
            key_prefix=APIKey.get_key_prefix(key),
            is_active=True,
            expires_at=None,
        )
        assert api_key.verify_key(key) is True

    def test_verify_key_incorrect(self):
        """Test key verification with incorrect key."""
        key = "asf_test_key_12345"
        wrong_key = "asf_wrong_key_67890"
        api_key = APIKey(
            name="Test Key",
            key_hash=APIKey.hash_key(key),
            key_prefix=APIKey.get_key_prefix(key),
            is_active=True,
            expires_at=None,
        )
        assert api_key.verify_key(wrong_key) is False

    def test_verify_key_inactive(self):
        """Test key verification with inactive key."""
        key = "asf_test_key_12345"
        api_key = APIKey(
            name="Test Key",
            key_hash=APIKey.hash_key(key),
            key_prefix=APIKey.get_key_prefix(key),
            is_active=False,
            expires_at=None,
        )
        assert api_key.verify_key(key) is False


@pytest.mark.asyncio
class TestAPIKeyEndpoints:
    """Test API key management endpoints."""

    async def test_create_api_key(self, client):
        """Test creating a new API key."""
        response = await client.post(
            "/api-keys",
            json={
                "name": "Test API Key",
                "expires_in_days": 30,
                "rate_limit_per_minute": 100,
            },
        )
        assert response.status_code == 201
        data = response.json()
        
        assert "key" in data
        assert data["key"].startswith("asf_")
        assert data["name"] == "Test API Key"
        assert data["rate_limit_per_minute"] == 100
        assert "expires_at" in data

    async def test_create_api_key_no_expiration(self, client):
        """Test creating API key without expiration."""
        response = await client.post(
            "/api-keys",
            json={
                "name": "Permanent Key",
                "rate_limit_per_minute": 60,
            },
        )
        assert response.status_code == 201
        data = response.json()
        
        assert data["expires_at"] is None

    async def test_list_api_keys(self, client, db_session):
        """Test listing API keys."""
        # Create test keys
        for i in range(3):
            key = APIKey(
                name=f"Test Key {i}",
                key_hash=APIKey.hash_key(f"key_{i}"),
                key_prefix=f"asf_key{i}",
            )
            db_session.add(key)
        await db_session.commit()
        
        response = await client.get("/api-keys")
        assert response.status_code == 200
        data = response.json()
        
        assert len(data) >= 3
        # Verify actual key is not returned
        for item in data:
            assert "key" not in item
            assert "key_hash" not in item
            assert "key_prefix" in item

    async def test_delete_api_key(self, client, db_session):
        """Test deleting an API key."""
        # Create test key
        api_key = APIKey(
            name="To Delete",
            key_hash=APIKey.hash_key("delete_me"),
            key_prefix="asf_dele",
        )
        db_session.add(api_key)
        await db_session.commit()
        await db_session.refresh(api_key)
        
        response = await client.delete(f"/api-keys/{api_key.id}")
        assert response.status_code == 204

    async def test_deactivate_api_key(self, client, db_session):
        """Test deactivating an API key."""
        # Create test key
        api_key = APIKey(
            name="To Deactivate",
            key_hash=APIKey.hash_key("deactivate_me"),
            key_prefix="asf_deac",
            is_active=True,
        )
        db_session.add(api_key)
        await db_session.commit()
        await db_session.refresh(api_key)
        
        response = await client.patch(f"/api-keys/{api_key.id}/deactivate")
        assert response.status_code == 200
        data = response.json()
        
        assert data["is_active"] is False
