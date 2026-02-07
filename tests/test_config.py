"""Test configuration management."""

from foundry.config import settings


def test_settings_loaded():
    """Test that settings are loaded correctly."""
    assert settings.app_name == "autonomous-software-foundry"
    assert settings.app_version == "0.1.0"
    assert settings.environment == "development"


def test_database_url_configured():
    """Test that database URL is configured."""
    assert settings.database_url is not None
    assert "postgresql://" in settings.database_url


def test_redis_url_configured():
    """Test that Redis URL is configured."""
    assert settings.redis_url is not None
    assert "redis://" in settings.redis_url
