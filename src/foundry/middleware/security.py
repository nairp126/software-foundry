"""Security headers middleware."""

from typing import Callable
from fastapi import Request, Response
from starlette.types import ASGIApp, Receive, Scope, Send


class SecurityHeadersMiddleware:
    """Add security headers to all responses using pure ASGI to avoid loop issues."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                
                # Helper to add/update headers
                new_headers = [
                    (b"Strict-Transport-Security", b"max-age=31536000; includeSubDomains"),
                    (b"Content-Security-Policy", 
                     b"default-src 'self'; script-src 'self'; "
                     b"style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; "
                     b"font-src 'self' data:; connect-src 'self' ws: wss:;"),
                    (b"X-Frame-Options", b"DENY"),
                    (b"X-Content-Type-Options", b"nosniff"),
                    (b"X-XSS-Protection", b"1; mode=block"),
                    (b"Referrer-Policy", b"strict-origin-when-cross-origin"),
                    (b"Permissions-Policy", b"geolocation=(), microphone=(), camera=()"),
                ]
                
                # Convert to bytes if they aren't already
                for key, value in new_headers:
                    headers.append((key, value))
                
                message["headers"] = headers
            
            await send(message)

        await self.app(scope, receive, send_wrapper)
