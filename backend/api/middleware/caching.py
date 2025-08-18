"""
Caching middleware for Korean Real Estate RAG AI Chatbot
"""

import logging
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class CacheMiddleware(BaseHTTPMiddleware):
    """Cache middleware for response caching"""
    
    def __init__(self, app, cache_ttl: int = 300):
        super().__init__(app)
        self.cache_ttl = cache_ttl
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with caching"""
        
        # Skip caching for certain paths
        skip_cache_paths = ["/docs", "/redoc", "/openapi.json", "/health"]
        if any(request.url.path.startswith(path) for path in skip_cache_paths):
            return await call_next(request)
        
        # Skip caching for non-GET requests
        if request.method != "GET":
            return await call_next(request)
        
        # TODO: Implement actual caching logic with Redis
        # For now, just pass through
        response = await call_next(request)
        
        # Add cache control headers
        if response.status_code == 200:
            response.headers["Cache-Control"] = f"public, max-age={self.cache_ttl}"
        
        return response