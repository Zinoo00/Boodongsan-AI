"""
LightRAG service backed by Neo4j for the Korean Real Estate RAG chatbot.

This module configures LightRAG with AWS Bedrock adapters and Neo4j as the
graph store. Vector embeddings and KV storage use the lightweight JSON/Nano
implementations that persist inside ``settings.LIGHTRAG_WORKING_DIR``.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any

from core.config import settings
from core.database import cache_manager
from core.exceptions import AIServiceError, ErrorCode, VectorServiceError

logger = logging.getLogger(__name__)

# Type aliases for readability
QueryMode = str


class BedrockLLMAdapter:
    """Adapter that exposes AWS Bedrock Claude completion as an async callable for LightRAG."""

    def __init__(self, bedrock_client: Any, model_id: str):
        self._client = bedrock_client
        self._model_id = model_id

    async def __call__(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> str:
        max_tokens = kwargs.get("max_tokens", 4000)
        temperature = kwargs.get("temperature", 0.7)

        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }

        if system_prompt:
            body["system"] = system_prompt

        try:
            response = await asyncio.to_thread(
                self._client.invoke_model,
                modelId=self._model_id,
                body=json.dumps(body),
            )
        except Exception as exc:  # pragma: no cover - boto3 raises many runtime specific exceptions
            raise AIServiceError(
                message=f"Bedrock completion failed: {exc}",
                error_code=ErrorCode.AI_SERVICE_UNAVAILABLE,
                provider="aws_bedrock",
                model=self._model_id,
                cause=exc,
            ) from exc

        response_payload = json.loads(response["body"].read())
        return response_payload["content"][0]["text"]


class BedrockEmbeddingAdapter:
    """Adapter that exposes AWS Bedrock Titan embedding as an async callable for LightRAG."""

    def __init__(self, bedrock_client: Any, embedding_model_id: str):
        self._client = bedrock_client
        self._embedding_model_id = embedding_model_id

    async def __call__(self, texts: list[str]) -> list[list[float]]:
        try:
            embeddings = []
            for text in texts:
                response = await asyncio.to_thread(
                    self._client.invoke_model,
                    modelId=self._embedding_model_id,
                    body=json.dumps({"inputText": text}),
                )
                payload = json.loads(response["body"].read())
                embeddings.append(payload["embedding"])
            return embeddings
        except Exception as exc:  # pragma: no cover - boto3 raises runtime exceptions
            raise AIServiceError(
                message=f"Bedrock embedding failed: {exc}",
                error_code=ErrorCode.AI_SERVICE_UNAVAILABLE,
                provider="aws_bedrock",
                model=self._embedding_model_id,
                cause=exc,
            ) from exc


class LightRAGService:
    """Thin wrapper around LightRAG configured with Neo4j graph storage."""

    def __init__(self):
        self._rag = None
        self._init_lock = asyncio.Lock()
        self._initialized = False
        self._bedrock_client = None
        self._llm_adapter: BedrockLLMAdapter | None = None
        self._embedding_adapter: BedrockEmbeddingAdapter | None = None

        self._working_dir = Path(settings.LIGHTRAG_WORKING_DIR).resolve()
        self._working_dir.mkdir(parents=True, exist_ok=True)

        self._entity_types = [
            "Property",
            "Location",
            "Policy",
            "Demographic",
            "Institution",
            "PriceRange",
            "PropertyType",
            "Landmark",
        ]

    @property
    def initialized(self) -> bool:
        return self._initialized

    async def initialize(self) -> None:
        """Initialise LightRAG once and reuse the instance across requests."""
        if self._initialized:
            return

        async with self._init_lock:
            if self._initialized:
                return

            logger.info("Initializing LightRAG service with Neo4j backend")
            self._configure_environment()

            try:
                import boto3
                from lightrag import LightRAG
            except ImportError as exc:  # pragma: no cover - handled at runtime
                raise VectorServiceError(
                    message=(
                        "LightRAG or boto3 is not installed. "
                        "Install dependencies with `uv add lightrag-hku[api] boto3`."
                    ),
                    error_code=ErrorCode.VECTOR_SERVICE_ERROR,
                    operation="lightrag_import",
                    cause=exc,
                ) from exc

            # Bedrock clients
            try:
                self._bedrock_client = boto3.client(
                    "bedrock-runtime",
                    region_name=settings.AWS_REGION,
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.get_secret_value("AWS_SECRET_ACCESS_KEY"),
                )
            except Exception as exc:  # pragma: no cover - boto3 specific
                raise AIServiceError(
                    message=f"Failed to create Bedrock client: {exc}",
                    error_code=ErrorCode.AI_SERVICE_UNAVAILABLE,
                    provider="aws_bedrock",
                    cause=exc,
                ) from exc

            self._llm_adapter = BedrockLLMAdapter(
                bedrock_client=self._bedrock_client,
                model_id=settings.BEDROCK_MODEL_ID,
            )
            self._embedding_adapter = BedrockEmbeddingAdapter(
                bedrock_client=self._bedrock_client,
                embedding_model_id=settings.BEDROCK_EMBEDDING_MODEL_ID,
            )

            try:
                self._rag = LightRAG(
                    working_dir=str(self._working_dir),
                    workspace=settings.LIGHTRAG_WORKSPACE,
                    llm_model_func=self._llm_adapter,
                    embedding_func=self._embedding_adapter,
                    embedding_dim=settings.VECTOR_SIZE,
                    kv_storage="JsonKVStorage",
                    vector_storage="NanoVectorDBStorage",
                    graph_storage="Neo4JStorage",
                    doc_status_storage="JsonDocStatusStorage",
                    addon_params={
                        "language": "Korean",
                        "entity_types": self._entity_types,
                        "entity_extract_max_gleaning": settings.LIGHTRAG_ENTITY_EXTRACT_MAX_GLEANING,
                        "embedding_batch_num": settings.LIGHTRAG_EMBEDDING_BATCH_SIZE,
                        "llm_model_max_async": settings.LIGHTRAG_LLM_MAX_ASYNC,
                        "embedding_func_max_async": settings.LIGHTRAG_EMBEDDING_MAX_ASYNC,
                    },
                )

                await self._rag.initialize_storages()
            except Exception as exc:
                raise VectorServiceError(
                    message=f"Failed to initialise LightRAG storages: {exc}",
                    error_code=ErrorCode.VECTOR_SERVICE_ERROR,
                    operation="initialize",
                    cause=exc,
                ) from exc

            self._initialized = True
            logger.info("LightRAG service initialised successfully")

    async def finalize(self) -> None:
        """Release LightRAG resources."""
        if not self._initialized or not self._rag:
            return

        try:
            await self._rag.finalize_storages()
            logger.info("LightRAG storages finalised")
        finally:
            self._initialized = False
            self._rag = None

    def _configure_environment(self) -> None:
        """Set environment variables expected by the Neo4j storage implementation."""
        os.environ["NEO4J_URI"] = settings.NEO4J_URI
        os.environ["NEO4J_USERNAME"] = settings.NEO4J_USERNAME
        os.environ["NEO4J_PASSWORD"] = settings.get_secret_value("NEO4J_PASSWORD")
        os.environ["NEO4J_WORKSPACE"] = settings.LIGHTRAG_WORKSPACE
        os.environ["NEO4J_MAX_CONNECTION_POOL_SIZE"] = str(settings.NEO4J_MAX_CONNECTION_POOL_SIZE)
        os.environ["NEO4J_CONNECTION_TIMEOUT"] = str(settings.NEO4J_CONNECTION_TIMEOUT)

        if settings.NEO4J_DATABASE:
            os.environ["NEO4J_DATABASE"] = settings.NEO4J_DATABASE

    async def index_property(self, property_data: dict[str, Any]) -> None:
        """Insert a property document into the LightRAG knowledge graph."""
        await self.initialize()
        if not self._rag:
            raise VectorServiceError(
                message="LightRAG is not initialised",
                error_code=ErrorCode.VECTOR_SERVICE_ERROR,
                operation="index_property",
            )

        document = self._format_property_document(property_data)
        await self._rag.ainsert(document)
        logger.debug("Indexed property into LightRAG", extra={"property_id": property_data.get("id")})

    async def index_policy(self, policy_data: dict[str, Any]) -> None:
        """Insert a policy document into the LightRAG knowledge graph."""
        await self.initialize()
        if not self._rag:
            raise VectorServiceError(
                message="LightRAG is not initialised",
                error_code=ErrorCode.VECTOR_SERVICE_ERROR,
                operation="index_policy",
            )

        document = self._format_policy_document(policy_data)
        await self._rag.ainsert(document)
        logger.debug("Indexed policy into LightRAG", extra={"policy_id": policy_data.get("id")})

    async def query(
        self,
        query_text: str,
        mode: QueryMode = "auto",
        cache_ttl: int | None = None,
    ) -> dict[str, Any]:
        """Execute a LightRAG query with Redis caching."""
        await self.initialize()
        if not self._rag:
            raise VectorServiceError(
                message="LightRAG is not initialised",
                error_code=ErrorCode.VECTOR_SERVICE_ERROR,
                operation="query",
            )

        resolved_mode = self._resolve_mode(query_text, mode)
        cache_key = self._cache_key(query_text, resolved_mode)
        cached = await cache_manager.get_json(cache_key)
        if cached:
            cached["cached"] = True
            return cached

        try:
            from lightrag import QueryParam

            result = await self._rag.aquery(
                query_text,
                param=QueryParam(
                    mode=resolved_mode,
                    top_k=settings.MAX_SEARCH_RESULTS,
                    max_token_for_text_unit=settings.LIGHTRAG_MAX_TOKEN_FOR_TEXT_UNIT,
                    max_token_for_global_context=settings.LIGHTRAG_MAX_TOKEN_FOR_GLOBAL_CONTEXT,
                    max_token_for_local_context=settings.LIGHTRAG_MAX_TOKEN_FOR_LOCAL_CONTEXT,
                ),
            )
        except Exception as exc:
            raise VectorServiceError(
                message=f"LightRAG query failed: {exc}",
                error_code=ErrorCode.VECTOR_SEARCH_ERROR,
                operation="query",
                cause=exc,
            ) from exc

        payload = {
            "answer": result,
            "mode": resolved_mode,
            "cached": False,
        }

        await cache_manager.set_json(
            cache_key,
            payload,
            ttl=cache_ttl or settings.LIGHTRAG_QUERY_CACHE_TTL,
        )
        return payload

    def _resolve_mode(self, query_text: str, provided: QueryMode) -> QueryMode:
        """Simple heuristic for choosing a LightRAG mode."""
        if provided != "auto":
            return provided

        lower_text = query_text.lower()
        if any(keyword in lower_text for keyword in ("정책", "지원", "대출")):
            return "global"
        if any(keyword in lower_text for keyword in ("추천", "매물", "어떤 집", "어디")):
            return "local"
        if len(query_text.split()) > 12:
            return "hybrid"
        return "hybrid"

    def _cache_key(self, query_text: str, mode: QueryMode) -> str:
        digest = hashlib.sha256(f"{mode}:{query_text}".encode()).hexdigest()
        return f"lightrag:{mode}:{digest}"

    def _format_property_document(self, property_data: dict[str, Any]) -> str:
        """Create a Korean text document for LightRAG ingestion."""
        return (
            "부동산 매물 정보:\n"
            f"- 매물 ID: {property_data.get('id', '알 수 없음')}\n"
            f"- 주소: {property_data.get('address', '정보 없음')}\n"
            f"- 지역: {property_data.get('district', '')} {property_data.get('dong', '')}\n"
            f"- 유형: {property_data.get('property_type', '정보 없음')}\n"
            f"- 거래 유형: {property_data.get('transaction_type', '정보 없음')}\n"
            f"- 가격: {property_data.get('price') or property_data.get('deposit') or 0:,}원\n"
            f"- 전용면적: {property_data.get('area_exclusive', 0)}㎡\n"
            f"- 방/욕실: {property_data.get('room_count', 0)}개 / {property_data.get('bathroom_count', 0)}개\n"
            f"- 준공년도: {property_data.get('building_year', '정보 없음')}\n"
            f"- 설명: {property_data.get('description', '설명 없음')}\n"
        )

    def _format_policy_document(self, policy_data: dict[str, Any]) -> str:
        """Create a policy document suitable for LightRAG ingestion."""
        return (
            "정부 지원 정책 정보:\n"
            f"- 정책 ID: {policy_data.get('id', '알 수 없음')}\n"
            f"- 정책명: {policy_data.get('policy_name', '정보 없음')}\n"
            f"- 정책 유형: {policy_data.get('policy_type', '정보 없음')}\n"
            f"- 대상: {policy_data.get('target_demographic', '정보 없음')}\n"
            f"- 소득 조건: {policy_data.get('income_min', '정보 없음')} ~ {policy_data.get('income_max', '정보 없음')}\n"
            f"- 지역 조건: {', '.join(policy_data.get('available_regions', []) or [])}\n"
            f"- 혜택: {policy_data.get('benefits', '정보 없음')}\n"
            f"- 신청 방법: {policy_data.get('application_method', '정보 없음')}\n"
            f"- 설명: {policy_data.get('description', '설명 없음')}\n"
        )

    async def health_check(self) -> dict[str, Any]:
        """Return simple health indicator for monitoring endpoints."""
        status = {
            "service": "LightRAG",
            "initialized": self._initialized,
            "workspace": settings.LIGHTRAG_WORKSPACE,
        }
        if not self._initialized:
            status["status"] = "uninitialized"
            return status

        status["status"] = "healthy"
        return status
