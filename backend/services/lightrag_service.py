"""
LightRAG service - 지식 그래프 기반 RAG with native PostgreSQL storage.

Storage backends:
- PostgreSQL (default): Native LightRAG PostgreSQL storage classes
  - PGKVStorage: Key-value storage
  - PGVectorStorage: Vector storage with pgvector
  - PGGraphStorage: Graph storage
  - PGDocStatusStorage: Document status storage
- Local: Default LightRAG embedded storage
  - JsonKVStorage, NanoVectorDBStorage, NetworkXStorage, JsonDocStatusStorage
"""

from __future__ import annotations

import logging
import os
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
from lightrag import LightRAG, QueryParam
from lightrag.kg.shared_storage import initialize_pipeline_status
from lightrag.utils import EmbeddingFunc

from core.config import settings

if TYPE_CHECKING:
    from services.ai_service import AIService

logger = logging.getLogger(__name__)


def _build_llm_model_func(ai_service: AIService | None) -> Callable[..., Awaitable[str]]:
    """LightRAG용 LLM 함수 생성."""

    async def llm_model_func(
        prompt: str,
        system_prompt: str | None = None,
        history_messages: list | None = None,
        keyword_extraction: bool = False,
        **kwargs: Any,
    ) -> str:
        if not ai_service:
            raise ValueError("AIService not configured")

        try:
            response = await ai_service.generate_text(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=kwargs.get("max_tokens", 2000),
            )
        except Exception as exc:
            logger.error(f"LLM function failed: {exc}")
            raise

        return response.get("text", "")

    return llm_model_func


def _build_embedding_func(
    ai_service: AIService | None,
) -> EmbeddingFunc:
    """
    LightRAG용 임베딩 함수 생성.

    실제 Bedrock Titan 임베딩 또는 해시 기반 임베딩 반환.
    """

    async def embedding_func(texts: list[str]) -> np.ndarray:
        if not ai_service:
            raise ValueError("AIService not configured")

        try:
            embeddings = await ai_service.generate_embeddings(texts)
            return np.array(embeddings)
        except Exception as exc:
            logger.error(f"Embedding function failed: {exc}")
            raise

    embedding_dim = settings.LIGHTRAG_EMBEDDING_DIM

    return EmbeddingFunc(
        embedding_dim=embedding_dim,
        func=embedding_func,
    )


def _setup_postgres_env() -> None:
    """
    LightRAG PostgreSQL 환경 변수 설정.

    LightRAG는 환경 변수를 통해 PostgreSQL 연결 정보를 읽음.
    """
    if settings.POSTGRES_HOST:
        os.environ["POSTGRES_HOST"] = settings.POSTGRES_HOST
    if settings.POSTGRES_PORT:
        os.environ["POSTGRES_PORT"] = str(settings.POSTGRES_PORT)
    if settings.POSTGRES_USER:
        os.environ["POSTGRES_USER"] = settings.POSTGRES_USER
    if settings.POSTGRES_PASSWORD:
        os.environ["POSTGRES_PASSWORD"] = settings.POSTGRES_PASSWORD
    if settings.POSTGRES_DB:
        os.environ["POSTGRES_DB"] = settings.POSTGRES_DB

    # DATABASE_URL에서 PostgreSQL 정보 추출 (fallback)
    if settings.DATABASE_URL and not settings.POSTGRES_HOST:
        _parse_database_url_to_env(settings.DATABASE_URL)


def _parse_database_url_to_env(database_url: str) -> None:
    """
    DATABASE_URL을 파싱하여 환경 변수로 설정.

    Format: postgresql+asyncpg://user:pass@host:port/dbname
    """
    try:
        from urllib.parse import urlparse

        # asyncpg 스키마 제거
        url = database_url.replace("postgresql+asyncpg://", "postgresql://")
        parsed = urlparse(url)

        if parsed.hostname:
            os.environ["POSTGRES_HOST"] = parsed.hostname
        if parsed.port:
            os.environ["POSTGRES_PORT"] = str(parsed.port)
        if parsed.username:
            os.environ["POSTGRES_USER"] = parsed.username
        if parsed.password:
            os.environ["POSTGRES_PASSWORD"] = parsed.password
        if parsed.path and parsed.path.startswith("/"):
            os.environ["POSTGRES_DB"] = parsed.path[1:]  # Remove leading slash

        logger.info(f"Parsed DATABASE_URL for LightRAG: host={parsed.hostname}")
    except Exception as e:
        logger.warning(f"Failed to parse DATABASE_URL: {e}")


class LightRAGService:
    """
    LightRAG 지식 그래프 RAG 서비스.

    Storage backends:
    - PostgreSQL (default): Native LightRAG PostgreSQL storage
        - PGKVStorage, PGVectorStorage, PGGraphStorage, PGDocStatusStorage
        - 분산 환경에서 동시 접근 안전
    - Local: Embedded storage for development
        - JsonKVStorage, NanoVectorDBStorage, NetworkXStorage, JsonDocStatusStorage
    """

    def __init__(
        self, ai_service: AIService | None = None, storage_backend: str | None = None
    ) -> None:
        """
        LightRAG 서비스 초기화.

        Args:
            ai_service: AI service providing LLM responses and embeddings
            storage_backend: Storage backend type ("postgresql" or "local")
                           If None, uses settings.STORAGE_BACKEND
        """
        self.ai_service = ai_service
        self._rag: LightRAG | None = None
        self._initialized = False

        # Storage backend 설정
        self.storage_backend_type = storage_backend or settings.STORAGE_BACKEND
        logger.info(f"Using storage backend: {self.storage_backend_type}")

        # Working directory 설정
        self.working_dir = Path(settings.LIGHTRAG_WORKING_DIR) / settings.LIGHTRAG_WORKSPACE
        self.working_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"LightRAG working directory: {self.working_dir}")

    async def initialize(self) -> None:
        """
        LightRAG 초기화 with native PostgreSQL storage.

        PostgreSQL backend:
        - PGKVStorage: Key-value storage in PostgreSQL
        - PGVectorStorage: Vector storage using pgvector extension
        - PGGraphStorage: Knowledge graph storage in PostgreSQL
        - PGDocStatusStorage: Document status tracking

        Local backend:
        - JsonKVStorage, NanoVectorDBStorage, NetworkXStorage, JsonDocStatusStorage
        """
        if self._initialized:
            logger.info("LightRAG already initialized")
            return

        try:
            llm_model_func = _build_llm_model_func(self.ai_service)
            embedding_func = _build_embedding_func(self.ai_service)

            if self.storage_backend_type == "postgresql":
                # PostgreSQL 환경 변수 설정
                _setup_postgres_env()

                # LightRAG with native PostgreSQL storage
                self._rag = LightRAG(
                    working_dir=str(self.working_dir),
                    llm_model_func=llm_model_func,
                    embedding_func=embedding_func,
                    # Native PostgreSQL storage classes
                    kv_storage="PGKVStorage",
                    vector_storage="PGVectorStorage",
                    graph_storage="PGGraphStorage",
                    doc_status_storage="PGDocStatusStorage",
                    # Workspace for logical data isolation
                    workspace=settings.LIGHTRAG_WORKSPACE,
                )
                logger.info("Initialized LightRAG with PostgreSQL storage")

            else:
                # Local backend: Default embedded storage
                self._rag = LightRAG(
                    working_dir=str(self.working_dir),
                    llm_model_func=llm_model_func,
                    embedding_func=embedding_func,
                    # Default local storage classes
                    kv_storage="JsonKVStorage",
                    vector_storage="NanoVectorDBStorage",
                    graph_storage="NetworkXStorage",
                    doc_status_storage="JsonDocStatusStorage",
                )
                logger.info("Initialized LightRAG with local storage")

            # Storage 초기화 (필수)
            await self._rag.initialize_storages()
            logger.info("LightRAG storages initialized")

            # Pipeline status 초기화 (필수)
            try:
                await initialize_pipeline_status()
                logger.info("Pipeline status initialized")
            except Exception as e:
                logger.warning(f"Could not initialize pipeline status: {e}")
                # Continue anyway - some versions may not require this

            self._initialized = True
            logger.info(
                f"LightRAG initialized successfully with {self.storage_backend_type} backend"
            )

        except Exception as e:
            logger.error(f"Failed to initialize LightRAG: {e}")
            raise

    def is_empty(self) -> bool:
        """
        LightRAG 스토리지가 비어있는지 확인.

        Returns:
            True if storage is empty, False otherwise
        """
        if self.storage_backend_type == "postgresql":
            # PostgreSQL: 데이터베이스 테이블 확인 필요
            # LightRAG가 초기화되면 기본적으로 비어있지 않다고 가정
            # 실제로는 쿼리를 통해 확인해야 함
            if not self._initialized:
                return True
            # Conservative: assume not empty if initialized
            return False

        # Local backend: 파일 존재 여부 확인
        if not self.working_dir.exists():
            return True

        # Check for any data files
        files = list(self.working_dir.glob("**/*"))
        data_files = [f for f in files if f.is_file() and f.suffix in {".json", ".pkl", ".db"}]

        return len(data_files) == 0

    async def finalize(self) -> None:
        """LightRAG 정리 및 종료."""
        if self._rag and self._initialized:
            try:
                await self._rag.finalize_storages()
                self._initialized = False
                logger.info("LightRAG finalized")
            except Exception as e:
                logger.error(f"Error finalizing LightRAG: {e}")

    async def insert(self, text: str, metadata: dict[str, Any] | None = None) -> bool:
        """
        문서를 LightRAG 지식 그래프에 추가.

        Args:
            text: 추가할 텍스트 (자동으로 chunking 및 entity extraction)
            metadata: 문서 메타데이터 (optional)

        Returns:
            성공 여부
        """
        if not self._initialized:
            await self.initialize()

        try:
            if not text or not text.strip():
                logger.warning("Empty text provided for insertion")
                return False

            # LightRAG에 문서 추가 (자동 chunking, entity extraction, graph building)
            await self._rag.ainsert(text)
            logger.info(f"Inserted document into LightRAG (length: {len(text)} chars)")
            return True

        except Exception as e:
            logger.error(f"Failed to insert document: {e}")
            return False

    async def insert_batch(self, texts: list[str]) -> int:
        """
        여러 문서를 배치로 추가.

        Args:
            texts: 추가할 텍스트 리스트

        Returns:
            성공적으로 추가된 문서 수
        """
        if not self._initialized:
            await self.initialize()

        success_count = 0
        for text in texts:
            if await self.insert(text):
                success_count += 1

        logger.info(f"Batch insert completed: {success_count}/{len(texts)} documents")
        return success_count

    async def query(
        self,
        query: str,
        mode: str = "hybrid",
        only_need_context: bool = False,
        top_k: int = 20,
    ) -> dict[str, Any] | None:
        """
        LightRAG 쿼리 실행.

        Args:
            query: 검색 쿼리
            mode: 검색 모드
                - "local": 로컬 엔티티 중심 검색
                - "global": 글로벌 커뮤니티 중심 검색
                - "hybrid": 로컬 + 글로벌 혼합 (default)
                - "naive": 단순 벡터 검색
            only_need_context: True이면 context만 반환 (LLM 응답 생성 안함)
            top_k: 검색할 최대 결과 수

        Returns:
            쿼리 결과 {"answer": str, "mode": str, "cached": bool}
        """
        if not self._initialized:
            await self.initialize()

        try:
            # QueryParam 설정
            param = QueryParam(
                mode=mode,
                only_need_context=only_need_context,
                top_k=top_k,
            )

            # LightRAG 쿼리 실행
            result = await self._rag.aquery(query, param=param)

            return {
                "answer": result,
                "mode": mode,
                "cached": False,  # LightRAG는 내부적으로 캐싱 처리
            }

        except Exception as e:
            logger.error(f"LightRAG query failed: {e}")
            return None

    async def search_vectors(
        self,
        query: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        벡터 유사도 검색.

        LightRAG의 naive 모드를 사용하여 순수 벡터 검색 수행.

        Args:
            query: 검색 쿼리
            limit: 최대 결과 수

        Returns:
            검색 결과 리스트
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Naive 모드로 context만 가져오기 (순수 벡터 검색)
            result = await self.query(
                query=query,
                mode="naive",
                only_need_context=True,
                top_k=limit,
            )

            if not result or not result.get("answer"):
                return []

            # Context를 검색 결과 형태로 변환
            # LightRAG는 context를 문자열로 반환하므로 파싱 필요
            context_text = result["answer"]

            # 간단한 파싱: context를 chunk로 분리
            results = []
            chunks = context_text.split("\n\n") if context_text else []

            for i, chunk in enumerate(chunks[:limit]):
                if chunk.strip():
                    results.append(
                        {
                            "id": f"lightrag_{i}",
                            "score": 1.0 - (i * 0.05),  # 순위에 따른 점수
                            "document": chunk.strip(),
                            "metadata": {"source": "lightrag", "mode": "naive"},
                            "type": "knowledge_chunk",
                        }
                    )

            logger.info(f"Vector search found {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []
