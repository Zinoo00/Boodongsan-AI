"""
User router backed by the lightweight JSON-based UserService.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.dependencies import get_user_service

if TYPE_CHECKING:
    from services.user_service import UserService

logger = logging.getLogger(__name__)

router = APIRouter()


class UserProfileResponse(BaseModel):
    """User profile payload."""

    user_id: str
    profile: dict[str, Any] | None = None


class ConversationListResponse(BaseModel):
    """Conversation history payload."""

    user_id: str
    conversation_id: str
    messages: list[dict[str, Any]]


@router.get("/{user_id}/profile", response_model=UserProfileResponse)
async def get_user_profile(
    user_id: str,
    user_service: UserService = Depends(get_user_service),
) -> UserProfileResponse:
    """Return the primary user profile."""
    try:
        profile = await user_service.get_primary_profile(user_id)
    except Exception as exc:  # pragma: no cover
        logger.exception("User profile lookup failed")
        raise HTTPException(status_code=500, detail="사용자 프로필을 불러오지 못했습니다.") from exc

    profile_dict = profile if isinstance(profile, dict) else None

    if not profile_dict:
        raise HTTPException(status_code=404, detail="사용자 프로필을 찾을 수 없습니다.")

    return UserProfileResponse(user_id=user_id, profile=profile_dict)


@router.get("/{user_id}/conversations/{conversation_id}", response_model=ConversationListResponse)
async def get_user_conversation(
    user_id: str,
    conversation_id: str,
    user_service: UserService = Depends(get_user_service),
    limit: int = Query(50, ge=1, le=200, description="조회할 메시지 수"),
) -> ConversationListResponse:
    """Return a stored conversation."""
    try:
        records = await user_service.get_conversation_history(user_id, conversation_id, limit)
    except Exception as exc:  # pragma: no cover
        logger.exception("Conversation history lookup failed")
        raise HTTPException(status_code=500, detail="대화 이력을 불러오지 못했습니다.") from exc

    messages: list[dict[str, Any]] = []
    for item in records:
        if isinstance(item, dict):
            messages.append(item)
        elif hasattr(item, "dict"):
            messages.append(item.dict())
        elif hasattr(item, "__dict__"):
            messages.append({k: v for k, v in item.__dict__.items() if not k.startswith("_")})
        else:
            messages.append({"value": item})

    return ConversationListResponse(
        user_id=user_id,
        conversation_id=conversation_id,
        messages=messages,
    )
