"""API key model for authentication."""

import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import Column, String, Boolean, DateTime, Integer
# Remove postgres-specific INET import

from foundry.database import Base
from foundry.models.base import BaseModel


class APIKey(BaseModel, Base):
    """API key for authentication."""
    __tablename__ = "api_keys"

    name = Column(String(255), nullable=False, doc="Human-readable name for the key")
    key_hash = Column(String(64), nullable=False, unique=True, index=True, doc="SHA256 hash of the API key")
    key_prefix = Column(String(8), nullable=False, doc="First 8 chars for identification")
    
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    expires_at = Column(DateTime, nullable=True, doc="Expiration timestamp")
    last_used_at = Column(DateTime, nullable=True, doc="Last usage timestamp")
    last_used_ip = Column(String(45), nullable=True, doc="Last IP address used")
    
    # Rate limiting
    rate_limit_per_minute = Column(Integer, nullable=False, default=60, doc="Max requests per minute")
    
    def __repr__(self) -> str:
        return f"<APIKey {self.name} ({self.key_prefix}...)>"

    @staticmethod
    def generate_key() -> str:
        """Generate a new API key.
        
        Returns:
            A secure random API key string
        """
        return f"asf_{secrets.token_urlsafe(32)}"

    @staticmethod
    def hash_key(key: str) -> str:
        """Hash an API key for storage.
        
        Args:
            key: The API key to hash
            
        Returns:
            SHA256 hash of the key
        """
        return hashlib.sha256(key.encode()).hexdigest()

    @staticmethod
    def get_key_prefix(key: str) -> str:
        """Extract the prefix from an API key.
        
        Args:
            key: The API key
            
        Returns:
            First 8 characters of the key
        """
        return key[:8] if len(key) >= 8 else key

    def is_valid(self) -> bool:
        """Check if the API key is valid.
        
        Returns:
            True if active and not expired
        """
        if not self.is_active:
            return False
        if self.expires_at and datetime.utcnow() >= self.expires_at:
            return False
        return True

    def verify_key(self, key: str) -> bool:
        """Verify a key against this record.
        
        Args:
            key: The API key to verify
            
        Returns:
            True if the key matches and is valid
        """
        if not self.is_valid():
            return False
        return self.key_hash == self.hash_key(key)
