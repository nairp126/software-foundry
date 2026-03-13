"""Middleware components for FastAPI application."""

from foundry.middleware.auth import get_api_key, require_api_key, api_key_header
from foundry.middleware.rate_limit import RateLimitMiddleware
from foundry.middleware.security import SecurityHeadersMiddleware

__all__ = [
    "get_api_key",
    "require_api_key",
    "api_key_header",
    "RateLimitMiddleware",
    "SecurityHeadersMiddleware",
]
