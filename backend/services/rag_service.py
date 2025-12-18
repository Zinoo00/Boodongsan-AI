"""
Straightforward Retrieval-Augmented Generation service using LightRAG.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from core.config import settings

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from services.ai_service import AIService
    from services.lightrag_service import LightRAGService
    from services.user_service import UserService


class RAGService:
    """Minimal orchestration layer for the chat flow using LightRAG."""

    def __init__(
        self,
        *,
        ai_service: AIService,
        user_service: UserService,
        lightrag_service: LightRAGService,
    ):
        self.ai_service = ai_service
        self.user_service = user_service
        self.lightrag_service = lightrag_service
        self.max_results = settings.MAX_SEARCH_RESULTS

    async def process_query(
        self,
        user_query: str,
        user_id: str,
        conversation_id: str,
        session_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        context = await self._build_context(
            user_query, user_id, conversation_id, session_context or {}
        )

        start_time = time.time()
        knowledge = await self._query_lightrag(user_query)
        vector_results = await self._search_vectors(user_query)

        context["knowledge_answer"] = knowledge.get("answer") if knowledge else None
        context["knowledge_mode"] = knowledge.get("mode") if knowledge else None
        context["vector_results"] = vector_results

        ai_response = await self.ai_service.generate_rag_response(context)

        await self._persist_conversation(
            user_id=user_id,
            conversation_id=conversation_id,
            user_query=user_query,
            ai_payload=ai_response,
            context=context,
        )

        processing_time_ms = (time.time() - start_time) * 1000

        return {
            "query": user_query,
            "knowledge": knowledge,
            "vector_results": vector_results,
            "ai_response": ai_response,
            "context": context,
            "processing_time_ms": processing_time_ms,
        }

    async def _build_context(
        self,
        user_query: str,
        user_id: str,
        conversation_id: str,
        session_context: dict[str, Any],
    ) -> dict[str, Any]:
        profile = await self.user_service.get_primary_profile(user_id)
        profile_dict = self._profile_to_dict(profile)

        # 이전 대화 이력 가져오기 (멀티턴 지원)
        conversation_history = session_context.get("conversation_history", [])
        if not conversation_history and conversation_id:
            try:
                history_records = await self.user_service.get_conversation_history(
                    user_id, conversation_id, limit=10
                )
                # 딕셔너리 리스트에서 대화 이력 추출 (키 접근)
                conversation_history = [
                    {"role": r.get("role"), "content": r.get("content")}
                    for r in history_records
                    if r.get("role") and r.get("content")
                ]
                logger.debug(
                    "대화 이력 로드 성공: user=%s, conv=%s, count=%d",
                    user_id, conversation_id, len(conversation_history)
                )
            except Exception as e:
                logger.warning(
                    "대화 이력 로드 실패: user=%s, conv=%s, error=%s",
                    user_id, conversation_id, str(e)
                )
                conversation_history = []

        return {
            "user_query": user_query,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "user_profile": profile_dict,
            "entities": session_context.get("entities", {}),
            "properties": session_context.get("properties", []),
            "policies": session_context.get("policies", []),
            "market_context": session_context.get("market_context", {}),
            "conversation_history": conversation_history,
        }

    async def _query_lightrag(self, query: str) -> dict[str, Any] | None:
        """Query LightRAG knowledge graph."""
        return await self.lightrag_service.query(query, mode="local")

    async def _search_vectors(self, query: str) -> list[dict[str, Any]]:
        """Vector search using LightRAG (NanoVectorDB)."""
        results = await self.lightrag_service.search_vectors(query, limit=self.max_results)
        return results

    async def _persist_conversation(
        self,
        *,
        user_id: str,
        conversation_id: str,
        user_query: str,
        ai_payload: dict[str, Any],
        context: dict[str, Any],
    ) -> None:
        await self.user_service.save_conversation_message(
            user_id=user_id,
            conversation_id=conversation_id,
            role="user",
            content=user_query,
            entities=context.get("entities"),
        )
        await self.user_service.save_conversation_message(
            user_id=user_id,
            conversation_id=conversation_id,
            role="assistant",
            content=ai_payload.get("text", ""),
            entities=context.get("entities"),
            search_results=[
                result["id"] for result in context.get("vector_results", []) if result.get("id")
            ],
            model_used=ai_payload.get("model_used"),
        )

    def _profile_to_dict(self, profile: Any | None) -> dict[str, Any]:
        if profile is None:
            return {}
        if isinstance(profile, dict):
            return profile
        if hasattr(profile, "model_dump"):
            return profile.model_dump()
        if hasattr(profile, "dict"):
            return profile.dict()

        data = {}
        for field in [
            "user_id",
            "age",
            "annual_income",
            "household_size",
            "max_budget",
            "preferred_locations",
            "preferred_property_types",
        ]:
            if hasattr(profile, field):
                data[field] = getattr(profile, field)
        return data
