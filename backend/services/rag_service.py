"""
Straightforward Retrieval-Augmented Generation service.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from core.config import settings

if TYPE_CHECKING:
    from services.ai_service import AIService
    from services.lightrag_service import LightRAGService
    from services.opensearch_service import OpenSearchVectorResult, OpenSearchVectorService
    from services.user_service import UserService


class RAGService:
    """Minimal orchestration layer for the chat flow."""

    def __init__(
        self,
        *,
        ai_service: AIService,
        vector_service: OpenSearchVectorService,
        user_service: UserService,
        lightrag_service: LightRAGService | None = None,
    ):
        self.ai_service = ai_service
        self.vector_service = vector_service
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
        context = await self._build_context(user_query, user_id, conversation_id, session_context or {})

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

        return {
            "user_query": user_query,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "user_profile": profile_dict,
            "entities": session_context.get("entities", {}),
            "properties": session_context.get("properties", []),
            "policies": session_context.get("policies", []),
            "market_context": session_context.get("market_context", {}),
            "conversation_history": session_context.get("conversation_history", []),
        }

    async def _query_lightrag(self, query: str) -> dict[str, Any] | None:
        if not self.lightrag_service:
            return None
        return await self.lightrag_service.query(query)

    async def _search_vectors(self, query: str) -> list[dict[str, Any]]:
        results = await self.vector_service.search(
            query_texts=[query],
            limit=self.max_results,
        )
        return [self._format_vector_result(res) for res in results]

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

    def _format_vector_result(self, result: OpenSearchVectorResult) -> dict[str, Any]:
        metadata = dict(result.metadata) if result.metadata else {}
        doc_type = (
            metadata.get("type")
            or metadata.get("document_type")
            or metadata.get("data_type")
            or metadata.get("category")
        )
        if doc_type and "type" not in metadata:
            metadata["type"] = doc_type

        return {
            "id": result.id,
            "score": result.score,
            "metadata": metadata,
            "document": result.document,
            "type": doc_type,
        }
