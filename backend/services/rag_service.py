"""
Simplified Retrieval-Augmented Generation service.

This service orchestrates LightRAG (Neo4j-backed knowledge graph) with
AWS OpenSearch vector similarity search and AI response generation.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from core.config import settings
from core.exceptions import VectorServiceError

if TYPE_CHECKING:
    from services.ai_service import AIService
    from services.data_service import DataService
    from services.lightrag_service import LightRAGService
    from services.opensearch_service import OpenSearchVectorResult, OpenSearchVectorService
    from services.user_service import UserService

logger = logging.getLogger(__name__)


class RAGService:
    """High level RAG orchestrator for chat requests."""

    def __init__(
        self,
        *,
        ai_service: AIService,
        vector_service: OpenSearchVectorService,
        data_service: DataService,
        user_service: UserService,
        lightrag_service: LightRAGService | None = None,
    ):
        self.ai_service = ai_service
        self.vector_service = vector_service
        self.data_service = data_service
        self.user_service = user_service
        self.lightrag_service = lightrag_service

        self.use_lightrag = settings.USE_LIGHTRAG and lightrag_service is not None
        self.max_results = settings.MAX_SEARCH_RESULTS

    async def process_query(
        self,
        user_query: str,
        user_id: str,
        conversation_id: str,
        session_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Process a user query and return an enriched RAG response."""

        session_context = session_context or {}
        context = await self._build_context(user_query, user_id, conversation_id, session_context)

        start_time = time.time()

        knowledge = await self._run_lightrag(user_query)
        vector_results = []

        if not knowledge or not knowledge.get("answer"):
            vector_results = await self._search_vectors(user_query)

        context["knowledge_answer"] = knowledge.get("answer") if knowledge else None
        context["knowledge_mode"] = knowledge.get("mode") if knowledge else None
        context["knowledge_cached"] = knowledge.get("cached") if knowledge else False
        context["vector_results"] = vector_results

        # Generate final AI response
        ai_response = await self.ai_service.generate_rag_response(context)

        # Persist conversation asynchronously (best effort)
        await self._persist_conversation(
            user_id=user_id,
            conversation_id=conversation_id,
            user_query=user_query,
            ai_response=ai_response.get("text", ""),
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
        """Assemble the context dictionary consumed by AIService."""

        profile = await self.user_service.get_primary_profile(user_id)
        profile_dict = self._profile_to_dict(profile)

        conversation_history = session_context.get("conversation_history", [])
        entities = session_context.get("entities", {})
        properties = session_context.get("properties", [])
        policies = session_context.get("policies", [])
        market_context = session_context.get("market_context", {})

        return {
            "user_query": user_query,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "user_profile": profile_dict,
            "entities": entities,
            "properties": properties,
            "policies": policies,
            "market_context": market_context,
            "conversation_history": conversation_history,
        }

    async def _run_lightrag(self, query: str) -> dict[str, Any] | None:
        """Execute LightRAG query if enabled."""
        if not self.use_lightrag or not self.lightrag_service:
            return None

        try:
            return await self.lightrag_service.query(query)
        except VectorServiceError as exc:
            logger.warning(
                "LightRAG query failed, falling back to vector search",
                extra={"error": str(exc), "query": query[:80]},
            )
            return None

    async def _search_vectors(self, query: str) -> list[dict[str, Any]]:
        """Fallback similarity search using AWS OpenSearch vectors."""
        try:
            results = await self.vector_service.search(
                query_texts=[query],
                limit=self.max_results,
            )
        except VectorServiceError as exc:
            logger.error(
                "OpenSearch vector search failed",
                extra={"error": str(exc), "query": query[:80]},
            )
            return []

        return [self._format_vector_result(res) for res in results]

    async def _persist_conversation(
        self,
        *,
        user_id: str,
        conversation_id: str,
        user_query: str,
        ai_response: str,
        context: dict[str, Any],
    ) -> None:
        """Store user/assistant messages in Neo4j (best effort)."""
        try:
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
                content=ai_response,
                entities=context.get("entities"),
                search_results=[
                    result["id"] for result in context.get("vector_results", []) if result.get("id")
                ],
            )
        except Exception as exc:  # pragma: no cover - persistence errors shouldn't break flow
            logger.warning(
                "Failed to persist conversation history",
                extra={"error": str(exc), "conversation_id": conversation_id},
            )

    def _profile_to_dict(self, profile: Any | None) -> dict[str, Any]:
        """Convert profile objects to plain dicts that AIService understands."""
        if profile is None:
            return {}

        if hasattr(profile, "model_dump"):
            return profile.model_dump()

        if hasattr(profile, "dict"):
            return profile.dict()

        # Fallback: collect simple attributes
        attrs = {}
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
                attrs[field] = getattr(profile, field)
        return attrs

    def _format_vector_result(self, result: OpenSearchVectorResult) -> dict[str, Any]:
        """Normalize OpenSearch search results."""
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
