"""
Chat router powered by the simplified RAG pipeline.
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.main import get_rag_service, get_user_service

if TYPE_CHECKING:
    from services.rag_service import RAGService
    from services.user_service import UserService

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatRequest(BaseModel):
    """Chat request payload."""

    message: str = Field(..., min_length=1, max_length=2000, description="사용자 메시지")
    user_id: str = Field(..., description="사용자 ID")
    conversation_id: str | None = Field(None, description="대화 ID (없으면 새로 생성)")
    session_context: dict[str, Any] | None = Field(
        default=None, description="선택적 세션 컨텍스트 (엔티티, 최근 기록 등)"
    )


class ChatResponse(BaseModel):
    """Chat response payload."""

    user_id: str
    conversation_id: str
    response: str
    knowledge_mode: str | None = None
    knowledge_cached: bool = False
    processing_time_ms: float
    vector_results: list[dict[str, Any]] = Field(default_factory=list)
    rag_context: dict[str, Any]


class ConversationHistoryResponse(BaseModel):
    """Conversation history response."""

    conversation_id: str
    messages: list[dict[str, Any]]
    total_count: int


class UserContextResponse(BaseModel):
    """Aggregated user context for dashboards."""

    user_id: str
    profile: dict[str, Any] | None = None
    recent_conversations: list[dict[str, Any]] = Field(default_factory=list)


@router.post("/send", response_model=ChatResponse)
async def send_message(
    payload: ChatRequest,
    rag_service: Annotated["RAGService", Depends(get_rag_service)],
) -> ChatResponse:
    """Process a chat message through the RAG pipeline."""
    conversation_id = payload.conversation_id or str(uuid.uuid4())

    try:
        rag_result = await rag_service.process_query(
            user_query=payload.message,
            user_id=payload.user_id,
            conversation_id=conversation_id,
            session_context=payload.session_context,
        )
    except Exception as exc:  # pragma: no cover - upstream exceptions handled via logging
        logger.exception("RAG processing failed")
        raise HTTPException(status_code=500, detail="메시지를 처리하는 중 오류가 발생했습니다.") from exc

    ai_response = rag_result["ai_response"].get("text") if rag_result.get("ai_response") else None

    # Fallback to knowledge answer if AI response missing
    if not ai_response:
        knowledge = rag_result.get("knowledge") or {}
        ai_response = knowledge.get("answer") or "답변을 생성하지 못했습니다."

    knowledge = rag_result.get("knowledge") or {}

    return ChatResponse(
        user_id=payload.user_id,
        conversation_id=conversation_id,
        response=ai_response,
        knowledge_mode=knowledge.get("mode"),
        knowledge_cached=knowledge.get("cached", False),
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
    user_service: Annotated["UserService", Depends(get_user_service)],
    user_id: str = Query(..., description="사용자 ID"),
    limit: int = Query(20, ge=1, le=200, description="가져올 메시지 수"),
) -> ConversationHistoryResponse:
    """Return the stored conversation history from Neo4j."""
    try:
        records = await user_service.get_conversation_history(user_id, conversation_id, limit=limit)
    except Exception as exc:  # pragma: no cover
        logger.exception("Conversation history lookup failed")
        raise HTTPException(status_code=500, detail="대화 이력을 불러오지 못했습니다.") from exc

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
    user_service: Annotated["UserService", Depends(get_user_service)],
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
