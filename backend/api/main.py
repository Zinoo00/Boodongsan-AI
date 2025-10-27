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

from api.middleware.auth import AuthMiddleware
from api.middleware.caching import CacheMiddleware
from api.routers import chat, citydata, health, policies, properties, users
from core.config import get_environment_config, settings
from core.database import cleanup_database, initialize_database
from services.ai_service import AIService
from services.data_service import DataService
from services.lightrag_service import LightRAGService
from services.opensearch_service import OpenSearchVectorService
from services.rag_service import RAGService
from services.seoul_city_data_service import SeoulCityDataService
from services.user_service import UserService

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.value),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    ai_service: AIService | None = None
    vector_service: OpenSearchVectorService | None = None
    data_service: DataService | None = None
    lightrag_service: LightRAGService | None = None
    user_service: UserService | None = None
    rag_service: RAGService | None = None
    city_data_service: SeoulCityDataService | None = None

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

        logger.info("Initializing OpenSearch vector service...")
        vector_service = OpenSearchVectorService()
        await vector_service.initialize()

        lightrag_service = None
        if settings.USE_LIGHTRAG:
            logger.info("Initializing LightRAG service...")
            lightrag_service = LightRAGService()
            try:
                await lightrag_service.initialize()
            except Exception as exc:
                logger.warning(
                    "LightRAG initialization failed - continuing with vector fallback",
                    extra={"error": str(exc)},
                )
                lightrag_service = None

        logger.info("Initializing business services...")
        data_service = DataService()
        user_service = UserService()

        logger.info("Initializing Seoul city data service...")
        city_data_service = SeoulCityDataService()
        try:
            await city_data_service.initialize()
        except Exception as exc:
            logger.warning(
                "Seoul city data service initialisation failed", extra={"error": str(exc)}
            )
            city_data_service = None

        logger.info("Initializing RAG service...")
        rag_service = RAGService(
            ai_service=ai_service,
            vector_service=vector_service,
            data_service=data_service,
            user_service=user_service,
            lightrag_service=lightrag_service,
        )

        # Store services in app state for dependency injection
        app.state.ai_service = ai_service
        app.state.vector_service = vector_service
        app.state.data_service = data_service
        app.state.lightrag_service = lightrag_service
        app.state.rag_service = rag_service
        app.state.user_service = user_service
        app.state.citydata_service = city_data_service

        logger.info("All services initialized successfully")

    except Exception as e:
        logger.error(f"Service initialization failed: {str(e)}")
        raise

    try:
        yield
    finally:
        logger.info("Shutting down application...")

        try:
            ai_instance = getattr(app.state, "ai_service", ai_service)
            if ai_instance:
                await ai_instance.close()

            lightrag_instance = getattr(app.state, "lightrag_service", lightrag_service)
            if lightrag_instance:
                await lightrag_instance.finalize()

            citydata_instance = getattr(app.state, "citydata_service", city_data_service)
            if citydata_instance:
                await citydata_instance.close()

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
    lifespan=lifespan,
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
    allowed_hosts = settings.ALLOWED_HOSTS if settings.ALLOWED_HOSTS else ["*"]
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

# Custom middleware
app.add_middleware(CacheMiddleware)
app.add_middleware(AuthMiddleware)

# Include routers
app.include_router(chat.router, prefix=settings.API_V1_STR + "/chat", tags=["Chat"])
app.include_router(health.router, prefix=settings.API_V1_STR + "/health", tags=["Health"])
app.include_router(
    citydata.router, prefix=settings.API_V1_STR + "/citydata", tags=["City Data"]
)
app.include_router(policies.router, prefix=settings.API_V1_STR + "/policies", tags=["Policies"])
app.include_router(
    properties.router, prefix=settings.API_V1_STR + "/properties", tags=["Properties"]
)
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
        "environment": settings.ENVIRONMENT.value,
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
            "Dual AI provider support (AWS Bedrock + Cloudflare)",
        ],
        "endpoints": {
            "chat": f"{settings.API_V1_STR}/chat",
            "policies": f"{settings.API_V1_STR}/policies",
            "properties": f"{settings.API_V1_STR}/properties",
            "users": f"{settings.API_V1_STR}/users",
            "health": f"{settings.API_V1_STR}/health",
        },
        "architecture": {
            "framework": "FastAPI",
            "asgi_server": "Uvicorn",
            "database": "Supabase PostgreSQL",
            "vector_db": "AWS OpenSearch",
            "cache": "Redis",
            "ai_providers": ["AWS Bedrock", "Cloudflare Workers AI"],
        },
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
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.utcnow().isoformat(),
        },
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
        "BearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"},
        "ApiKeyAuth": {"type": "apiKey", "in": "header", "name": "X-API-Key"},
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


async def get_user_service() -> UserService:
    """Dependency to get user service"""
    return app.state.user_service


async def get_vector_service() -> OpenSearchVectorService:
    """Dependency to get OpenSearch vector service"""
    return app.state.vector_service


async def get_data_service() -> DataService:
    """Dependency to get unified data service"""
    return app.state.data_service


async def get_lightrag_service() -> LightRAGService | None:
    """Dependency to get LightRAG service (may be None if disabled)"""
    return app.state.lightrag_service


async def get_citydata_service() -> SeoulCityDataService | None:
    """Dependency to get Seoul city data service (may be None if not initialised)"""
    return app.state.citydata_service

if __name__ == "__main__":
    # Development server using Uvicorn (per README architecture)
    env_config = get_environment_config()
    
    if settings.ASGI_SERVER == "granian":
        # Granian server support (if requested)
        try:
            import granian

            granian.run(
                "backend.api.main:app",
                interface="asgi",
                host=settings.HOST,
                port=settings.PORT,
                workers=settings.WORKERS,
                reload=env_config["reload"],
            )
        except ImportError:
            logger.warning("Granian not installed, falling back to Uvicorn")
            uvicorn.run(
                "backend.api.main:app",
                host=settings.HOST,
                port=settings.PORT,
                reload=env_config["reload"],
                log_level=env_config["log_level"],
            )
    else:
        # Default Uvicorn server (recommended per architecture)
        uvicorn.run(
            "backend.api.main:app",
            host=settings.HOST,
            port=settings.PORT,
            reload=env_config["reload"],
            log_level=env_config["log_level"],
        )
