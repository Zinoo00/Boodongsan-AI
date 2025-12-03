"""
Minimal health endpoints for development.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.dependencies import get_ai_service
from core.config import settings
from core.database import database_health_check
from services.ai_service import AIService

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    services: dict[str, Any] = Field(default_factory=dict)


def _get_model_info(provider: str) -> dict[str, str]:
    """AI 프로바이더 기반 모델 정보 반환."""
    model_map = {
        "anthropic": settings.ANTHROPIC_MODEL_ID,
        "bedrock": settings.BEDROCK_MODEL_ID,
    }
    return {
        "provider": provider,
        "model": model_map.get(provider, "N/A"),
    }


@router.get("/", response_model=HealthResponse)
async def health_check(ai_service: AIService = Depends(get_ai_service)) -> HealthResponse:
    redis_status = await database_health_check()
    await ai_service.initialize()

    model_info = _get_model_info(ai_service.provider)
    services = {
        "database": redis_status["redis"],
        "ai_service": {
            "status": ai_service.is_ready(),
            **model_info,
        },
    }

    is_healthy = all(bool(item.get("status")) for item in services.values())

    return HealthResponse(
        status="healthy" if is_healthy else "unhealthy",
        timestamp=datetime.utcnow().isoformat(),
        services=services,
    )


@router.get("/database", response_model=dict[str, Any])
async def database_health() -> dict[str, Any]:
    return await database_health_check()


@router.get("/ai", response_model=dict[str, Any])
async def ai_health(ai_service: AIService = Depends(get_ai_service)) -> dict[str, Any]:
    await ai_service.initialize()
    model_info = _get_model_info(ai_service.provider)
    return {
        "status": ai_service.is_ready(),
        "timestamp": datetime.utcnow().isoformat(),
        **model_info,
    }
