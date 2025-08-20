"""
FastAPI 메인 애플리케이션
Korean Real Estate RAG AI Chatbot API
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

# Core imports
from ..core.config import get_environment_config, settings
from ..core.database import cleanup_database, initialize_database

# Service imports
from ..services.ai_service import AIService
from ..services.policy_service import PolicyService
from ..services.property_service import PropertyService
from ..services.rag_service import RAGService
from ..services.user_service import UserService
from ..services.vector_service import VectorService
from .middleware.auth import AuthMiddleware

# Middleware imports
from .middleware.caching import CacheMiddleware

# Router imports
from .routers import chat, health, policies, properties, users

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.value),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global service instances
ai_service = None
vector_service = None
rag_service = None
property_service = None
policy_service = None
user_service = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    global ai_service, vector_service, rag_service, property_service, policy_service, user_service
    
    # Startup
    logger.info("Starting Korean Real Estate RAG AI Chatbot")
    
    try:
        # Initialize database
        logger.info("Initializing database connections...")
        await initialize_database()
        
        # Initialize services
        logger.info("Initializing AI services...")
        ai_service = AIService()
        await ai_service.initialize()
        
        logger.info("Initializing vector service...")
        vector_service = VectorService()
        await vector_service.initialize()
        
        logger.info("Initializing business services...")
        property_service = PropertyService()
        policy_service = PolicyService()
        user_service = UserService()
        
        logger.info("Initializing RAG service...")
        rag_service = RAGService(
            vector_service=vector_service,
            ai_service=ai_service,
            property_service=property_service,
            policy_service=policy_service,
            user_service=user_service
        )
        
        # Store services in app state for dependency injection
        app.state.ai_service = ai_service
        app.state.vector_service = vector_service
        app.state.rag_service = rag_service
        app.state.property_service = property_service
        app.state.policy_service = policy_service
        app.state.user_service = user_service
        
        logger.info("All services initialized successfully")
        
    except Exception as e:
        logger.error(f"Service initialization failed: {str(e)}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    
    try:
        if ai_service:
            await ai_service.close()
        
        await cleanup_database()
        
        logger.info("Application shutdown completed")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")

# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="Korean Real Estate RAG AI Chatbot - AI-powered personalized real estate recommendations",
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan
)

# Add middleware
# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Trusted host middleware  
if settings.ENVIRONMENT.value == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["yourdomain.com", "*.yourdomain.com"]
    )

# Custom middleware
app.add_middleware(CacheMiddleware)
app.add_middleware(AuthMiddleware)

# Include routers
app.include_router(chat.router, prefix=settings.API_V1_STR + "/chat", tags=["Chat"])
app.include_router(health.router, prefix=settings.API_V1_STR + "/health", tags=["Health"])
app.include_router(policies.router, prefix=settings.API_V1_STR + "/policies", tags=["Policies"])
app.include_router(properties.router, prefix=settings.API_V1_STR + "/properties", tags=["Properties"])
app.include_router(users.router, prefix=settings.API_V1_STR + "/users", tags=["Users"])

@app.get("/", response_model=dict[str, Any])
async def root():
    """API root endpoint"""
    return {
        "message": "Welcome to Korean Real Estate RAG AI Chatbot API!",
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs" if settings.DEBUG else None,
        "health": f"{settings.API_V1_STR}/health",
        "environment": settings.ENVIRONMENT.value
    }

@app.get(f"{settings.API_V1_STR}/info", response_model=dict[str, Any])
async def api_info():
    """API information"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "description": "Korean Real Estate RAG AI Chatbot - AI-powered personalized real estate recommendations",
        "features": [
            "Natural language real estate consultation",
            "Personalized property recommendations",
            "Government policy matching",
            "Real-time market information",
            "Conversation history management",
            "Vector-based similarity search",
            "Dual AI provider support (AWS Bedrock + Cloudflare)"
        ],
        "endpoints": {
            "chat": f"{settings.API_V1_STR}/chat",
            "policies": f"{settings.API_V1_STR}/policies", 
            "properties": f"{settings.API_V1_STR}/properties",
            "users": f"{settings.API_V1_STR}/users",
            "health": f"{settings.API_V1_STR}/health"
        },
        "architecture": {
            "framework": "FastAPI",
            "database": "Supabase PostgreSQL",
            "vector_db": "Qdrant",
            "cache": "Redis",
            "ai_providers": ["AWS Bedrock", "Cloudflare Workers AI"]
        }
    }

# Global exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred on the server.",
            "detail": str(exc) if settings.DEBUG else None,
            "timestamp": datetime.utcnow().isoformat()
        }
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.utcnow().isoformat()
        }
    )

# Custom OpenAPI schema
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Korean Real Estate RAG AI Chatbot - AI-powered personalized real estate recommendations",
        routes=app.routes,
    )
    
    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT"
        },
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key"
        }
    }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi


# Service dependency functions
async def get_rag_service() -> RAGService:
    """Dependency to get RAG service"""
    return app.state.rag_service

async def get_ai_service() -> AIService:
    """Dependency to get AI service"""
    return app.state.ai_service

async def get_vector_service() -> VectorService:
    """Dependency to get vector service"""
    return app.state.vector_service

async def get_property_service() -> PropertyService:
    """Dependency to get property service"""
    return app.state.property_service

async def get_policy_service() -> PolicyService:
    """Dependency to get policy service"""
    return app.state.policy_service

async def get_user_service() -> UserService:
    """Dependency to get user service"""
    return app.state.user_service


if __name__ == "__main__":
    # Development server
    env_config = get_environment_config()
    
    uvicorn.run(
        "backend.api.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=env_config["reload"],
        log_level=env_config["log_level"]
    )