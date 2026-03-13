"""Authentication middleware for API key validation."""

from typing import Optional
from datetime import datetime
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy import select

from foundry.database import AsyncSessionLocal
from foundry.models.api_key import APIKey


# API key header scheme
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_api_key(
    api_key: Optional[str] = Security(api_key_header),
) -> Optional[APIKey]:
    """Validate API key from request header.
    
    Args:
        api_key: API key from X-API-Key header
        
    Returns:
        APIKey model if valid, None if no key provided
        
    Raises:
        HTTPException: If key is invalid or expired
    """
    if not api_key:
        return None
    
    # Extract key hash
    key_hash = APIKey.hash_key(api_key)
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(APIKey).where(APIKey.key_hash == key_hash)
        )
        api_key_record = result.scalar_one_or_none()
        
        if not api_key_record:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
            )
        
        if not api_key_record.is_valid():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key is inactive or expired",
            )
        
        # Update last used timestamp
        api_key_record.last_used_at = datetime.utcnow()
        await session.commit()
        
        return api_key_record


async def require_api_key(
    api_key: Optional[APIKey] = Security(get_api_key),
) -> APIKey:
    """Require a valid API key for the endpoint.
    
    Args:
        api_key: API key from get_api_key dependency
        
    Returns:
        APIKey model
        
    Raises:
        HTTPException: If no valid API key provided
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return api_key
