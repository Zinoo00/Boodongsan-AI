"""
Dependency helpers for retrieving services stored on the FastAPI application state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import Request

if TYPE_CHECKING:
    from services.ai_service import AIService
    from services.lightrag_service import LightRAGService
    from services.opensearch_service import OpenSearchVectorService
    from services.rag_service import RAGService
    from services.seoul_city_data_service import SeoulCityDataService
    from services.user_service import UserService
    from services.data_service import DataService


def _get_service(request: Request, attr: str) -> Any:
    service = getattr(request.app.state, attr, None)
    if service is None:
        raise RuntimeError(f"{attr} is not initialised on application state.")
    return service


def get_rag_service(request: Request) -> "RAGService":
    return _get_service(request, "rag_service")


def get_ai_service(request: Request) -> "AIService":
    return _get_service(request, "ai_service")


def get_user_service(request: Request) -> "UserService":
    return _get_service(request, "user_service")


def get_vector_service(request: Request) -> "OpenSearchVectorService":
    return _get_service(request, "vector_service")


def get_data_service(request: Request) -> "DataService":
    return _get_service(request, "data_service")


def get_lightrag_service(request: Request) -> "LightRAGService | None":
    return getattr(request.app.state, "lightrag_service", None)


def get_citydata_service(request: Request) -> "SeoulCityDataService | None":
    return getattr(request.app.state, "citydata_service", None)
