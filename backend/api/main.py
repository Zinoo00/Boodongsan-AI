"""
FastAPI application entrypoint for the Korean Real Estate RAG AI Chatbot.
Simplified for local development: no fallback paths or defensive validation.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await initialize_database()

    ai_service = AIService()
    await ai_service.initialize()

    vector_service = OpenSearchVectorService()
    await vector_service.initialize()

    lightrag_service = LightRAGService() if settings.USE_LIGHTRAG else None
    if lightrag_service:
        await lightrag_service.initialize()

    data_service = DataService()
    user_service = UserService()

    city_data_service = SeoulCityDataService()
    await city_data_service.initialize()

    rag_service = RAGService(
        ai_service=ai_service,
        vector_service=vector_service,
        user_service=user_service,
        lightrag_service=lightrag_service,
    )

    app.state.ai_service = ai_service
    app.state.vector_service = vector_service
    app.state.data_service = data_service
    app.state.lightrag_service = lightrag_service
    app.state.rag_service = rag_service
    app.state.user_service = user_service
    app.state.citydata_service = city_data_service

    logger.info("Application services initialised")

    try:
        yield
    finally:
        await ai_service.close()
        if lightrag_service:
            await lightrag_service.finalize()
        await city_data_service.close()
        await cleanup_database()


app = FastAPI(
    title=settings.APP_NAME,
    description="Korean Real Estate RAG AI Chatbot",
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix=f"{settings.API_V1_STR}/chat", tags=["Chat"])
app.include_router(health.router, prefix=f"{settings.API_V1_STR}/health", tags=["Health"])
app.include_router(citydata.router, prefix=f"{settings.API_V1_STR}/citydata", tags=["City Data"])
app.include_router(policies.router, prefix=f"{settings.API_V1_STR}/policies", tags=["Policies"])
app.include_router(properties.router, prefix=f"{settings.API_V1_STR}/properties", tags=["Properties"])
app.include_router(users.router, prefix=f"{settings.API_V1_STR}/users", tags=["Users"])


@app.get("/", response_model=dict[str, Any])
async def root() -> dict[str, Any]:
    return {
        "message": "Welcome to the Korean Real Estate RAG AI Chatbot API",
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs" if settings.DEBUG else None,
        "health": f"{settings.API_V1_STR}/health",
        "environment": settings.ENVIRONMENT,
    }


@app.get(f"{settings.API_V1_STR}/info", response_model=dict[str, Any])
async def api_info() -> dict[str, Any]:
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "features": [
            "AI real estate chat",
            "Property recommendations",
            "Government policy suggestions",
            "Vector similarity search",
        ],
    }


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request, exc):  # pragma: no cover - simple dev handler
    logger.exception("Unhandled exception", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error", "detail": str(exc)},
    )


if __name__ == "__main__":
    config = get_environment_config()
    uvicorn.run(
        "backend.api.main:app",
        host=config["host"],
        port=config["port"],
        reload=config["reload"],
        log_level=config["log_level"],
        workers=config["workers"],
    )
