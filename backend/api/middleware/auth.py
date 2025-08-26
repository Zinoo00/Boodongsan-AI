"""
Authentication middleware for Korean Real Estate RAG AI Chatbot
"""

import logging
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """Authentication middleware"""

    def __init__(self, app):
        super().__init__(app)

        # Public endpoints that don't require authentication
        self.public_endpoints = [
            "/",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/v1/health",
            "/api/v1/info",
        ]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with authentication"""

        # Skip authentication for public endpoints
        if request.url.path in self.public_endpoints:
            return await call_next(request)

        # TODO: Implement actual authentication logic
        # For now, just pass through
        # In production, you would:
        # 1. Extract JWT token from Authorization header
        # 2. Validate token
        # 3. Set user context in request state

        response = await call_next(request)
        return response
