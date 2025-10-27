"""
Government policy router backed by DataService (Supabase).
"""

from __future__ import annotations

import logging
from typing import Annotated, TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.main import get_data_service

if TYPE_CHECKING:
    from services.data_service import DataService

logger = logging.getLogger(__name__)

router = APIRouter()


class PolicySearchRequest(BaseModel):
    """Policy search request."""

    policy_type: str | None = Field(None, description="정책 유형")
    target_demographic: str | None = Field(None, description="대상 계층")
    region: str | None = Field(None, description="적용 가능한 지역")


class PolicyMatchRequest(BaseModel):
    """Policy matching request using user profile."""

    user_profile: dict[str, Any] = Field(..., description="사용자 프로필 정보")


class PolicyListResponse(BaseModel):
    """Policy list response."""

    policies: list[dict[str, Any]]
    total_count: int
    filters: dict[str, Any]


@router.post("/match", response_model=PolicyListResponse)
async def match_policies(
    request: PolicyMatchRequest,
    data_service: Annotated["DataService", Depends(get_data_service)],
) -> PolicyListResponse:
    """Match eligible policies for the given user profile."""
    try:
        policies = await data_service.match_policies_for_user(request.user_profile)
        return PolicyListResponse(
            policies=policies,
            total_count=len(policies),
            filters={"type": "match"},
        )
    except Exception as exc:  # pragma: no cover
        logger.exception("Policy matching failed")
        raise HTTPException(status_code=500, detail="정책 매칭 중 오류가 발생했습니다.") from exc


@router.post("/search", response_model=PolicyListResponse)
async def search_policies(
    request: PolicySearchRequest,
    data_service: Annotated["DataService", Depends(get_data_service)],
) -> PolicyListResponse:
    """Search policies using filters."""
    filters = {k: v for k, v in request.model_dump().items() if v}
    try:
        policies = await data_service.search_policies(filters=filters)
        return PolicyListResponse(
            policies=policies,
            total_count=len(policies),
            filters=filters,
        )
    except Exception as exc:  # pragma: no cover
        logger.exception("Policy search failed")
        raise HTTPException(status_code=500, detail="정책 검색 중 오류가 발생했습니다.") from exc


@router.get("/", response_model=PolicyListResponse)
async def list_policies(
    data_service: Annotated["DataService", Depends(get_data_service)],
    active_only: bool = Query(True, description="활성 정책만 조회"),
    limit: int = Query(20, ge=1, le=100, description="최대 조회 개수"),
) -> PolicyListResponse:
    """Return highlighted policies."""
    try:
        policies = await data_service.get_all_policies(active_only=active_only)
        return PolicyListResponse(
            policies=policies[:limit],
            total_count=len(policies),
            filters={"active_only": active_only, "limit": limit},
        )
    except Exception as exc:  # pragma: no cover
        logger.exception("Policy listing failed")
        raise HTTPException(status_code=500, detail="정책 목록을 불러오지 못했습니다.") from exc


@router.get("/{policy_id}")
async def get_policy_detail(
    policy_id: str,
    data_service: Annotated["DataService", Depends(get_data_service)],
) -> dict[str, Any]:
    """Return policy detail."""
    policy = await data_service.get_policy(policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="해당 정책을 찾을 수 없습니다.")
    return {"policy": policy}
