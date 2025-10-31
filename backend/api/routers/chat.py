"""
Chat router powered by the simplified RAG pipeline.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from api.dependencies import get_rag_service, get_user_service

if TYPE_CHECKING:
    from services.rag_service import RAGService
    from services.user_service import UserService

router = APIRouter()


class ChatRequest(BaseModel):
    """Chat request payload."""

    message: str
    user_id: str
    conversation_id: str | None = None
    session_context: dict[str, Any] | None = None


class ChatResponse(BaseModel):
    """Chat response payload."""

    user_id: str
    conversation_id: str
    response: str
    knowledge_mode: str | None = None
    processing_time_ms: float
    vector_results: list[dict[str, Any]] = Field(default_factory=list)
    rag_context: dict[str, Any] = Field(default_factory=dict)


class ConversationHistoryResponse(BaseModel):
    """Conversation history response."""

    conversation_id: str
    messages: list[dict[str, Any]] = Field(default_factory=list)
    total_count: int


class UserContextResponse(BaseModel):
    """Aggregated user context for dashboards."""

    user_id: str
    profile: dict[str, Any] | None = None
    recent_conversations: list[dict[str, Any]] = Field(default_factory=list)


@router.post("/send", response_model=ChatResponse)
async def send_message(
    payload: ChatRequest,
    rag_service: "RAGService" = Depends(get_rag_service),
) -> ChatResponse:
    """Process a chat message through the RAG pipeline."""
    conversation_id = payload.conversation_id or str(uuid.uuid4())
    rag_result = await rag_service.process_query(
        user_query=payload.message,
        user_id=payload.user_id,
        conversation_id=conversation_id,
        session_context=payload.session_context,
    )

    ai_response = rag_result["ai_response"]["text"]
    knowledge = rag_result.get("knowledge") or {}

    return ChatResponse(
        user_id=payload.user_id,
        conversation_id=conversation_id,
        response=ai_response,
        knowledge_mode=knowledge.get("mode"),
        processing_time_ms=rag_result.get("processing_time_ms", 0.0),
        vector_results=rag_result.get("vector_results", []),
        rag_context=rag_result.get("context", {}),
    )


@router.get(
    "/history/{conversation_id}",
    response_model=ConversationHistoryResponse,
    summary="대화 이력 조회",
)
async def get_conversation_history(
    conversation_id: str,
    user_service: "UserService" = Depends(get_user_service),
    user_id: str = Query(..., description="사용자 ID"),
    limit: int = Query(20, ge=1, le=200, description="가져올 메시지 수"),
) -> ConversationHistoryResponse:
    """Return the stored conversation history."""
    records = await user_service.get_conversation_history(user_id, conversation_id, limit=limit)

    messages: list[dict[str, Any]] = []
    for item in records:
        if hasattr(item, "dict"):
            messages.append(item.dict())
        elif hasattr(item, "__dict__"):
            messages.append({k: v for k, v in item.__dict__.items() if not k.startswith("_")})
        else:
            messages.append(item)

    return ConversationHistoryResponse(
        conversation_id=conversation_id,
        messages=messages,
        total_count=len(messages),
    )


@router.get(
    "/context/{user_id}",
    response_model=UserContextResponse,
    summary="사용자 컨텍스트 조회",
)
async def get_user_context(
    user_id: str,
    user_service: "UserService" = Depends(get_user_service),
) -> UserContextResponse:
    """Return basic user profile and recent conversation snippets."""
    profile = await user_service.get_primary_profile(user_id)
    profile_dict = None
    if profile:
        if hasattr(profile, "model_dump"):
            profile_dict = profile.model_dump()
        elif hasattr(profile, "dict"):
            profile_dict = profile.dict()
        else:
            profile_dict = {k: getattr(profile, k) for k in dir(profile) if not k.startswith("_")}

    return UserContextResponse(
        user_id=user_id,
        profile=profile_dict,
        recent_conversations=[],
    )
