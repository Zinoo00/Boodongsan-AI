"""
LightRAG service - 지식 그래프 기반 RAG with default NanoVectorDB storage.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from lightrag import LightRAG, QueryParam

from core.config import settings

if TYPE_CHECKING:
    from services.ai_service import AIService

logger = logging.getLogger(__name__)


def _build_llm_model_func(ai_service: AIService | None) -> Callable[..., Awaitable[str]]:
    async def llm_model_func(
        prompt: str,
        system_prompt: str | None = None,
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
) -> Callable[[list[str]], Awaitable[list[list[float]]]]:
    async def embedding_func(texts: list[str], **kwargs: Any) -> list[list[float]]:
        if not ai_service:
            raise ValueError("AIService not configured")

        try:
            return await ai_service.generate_embeddings(texts, **kwargs)
        except Exception as exc:
            logger.error(f"Embedding function failed: {exc}")
            raise

    embedding_dim = None
    if ai_service:
        embedding_dim = getattr(ai_service, "embedding_dim", None) or getattr(
            ai_service, "embedding_dimension", None
        )
    if embedding_dim is None:
        embedding_dim = settings.LIGHTRAG_EMBEDDING_DIM
    embedding_func.embedding_dim = embedding_dim

    return embedding_func


class LightRAGService:
    """
    LightRAG 지식 그래프 RAG 서비스.

    Default 설정:
    - Vector DB: NanoVectorDB (embedded, no external service required)
    - Graph Storage: NetworkX (local graph storage)
    - Document Status: JSON files (local storage)
    """

    def __init__(self, ai_service: AIService | None = None) -> None:
        """
        LightRAG 서비스 초기화.

        Args:
            ai_service: AI service providing Anthropic Claude responses and embeddings
        """
        self.ai_service = ai_service
        self._rag: LightRAG | None = None
        self._initialized = False

        # Working directory 설정
        self.working_dir = Path(settings.LIGHTRAG_WORKING_DIR) / settings.LIGHTRAG_WORKSPACE
        self.working_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"LightRAG working directory: {self.working_dir}")

    async def initialize(self) -> None:
        """
        LightRAG 초기화 with default settings.

        Default 설정:
        - NanoVectorDB for vector storage
        - NetworkX for knowledge graph
        - Chunk size: 1200 tokens
        - Embedding batch size: 32
        """
        if self._initialized:
            logger.info("LightRAG already initialized")
            return

        try:
            llm_model_func = _build_llm_model_func(self.ai_service)
            embedding_func = _build_embedding_func(self.ai_service)

            # LightRAG 인스턴스 생성 with default settings
            self._rag = LightRAG(
                working_dir=str(self.working_dir),
                # LLM 함수 - Anthropic Claude 사용
                llm_model_func=llm_model_func,
                # Embedding 함수 - 로컬 결정적 임베딩 사용
                embedding_func=embedding_func,
                # Default vector DB: NanoVectorDB (embedded)
                # Default graph storage: NetworkX
                # Default doc status: JSON
                # 기타 모든 설정은 LightRAG default 사용
            )

            # Storage 초기화 (필수)
            await self._rag.initialize_storages()

            # Pipeline status 초기화 (필수)
            try:
                from lightrag.kg.shared_storage import initialize_pipeline_status

                await initialize_pipeline_status()
                logger.info("Pipeline status initialized")
            except (ImportError, AttributeError) as e:
                logger.warning(f"Could not initialize pipeline status: {e}")
                # Continue anyway - some versions may not require this

            self._initialized = True
            logger.info(
                "LightRAG initialized successfully with default settings (NanoVectorDB, NetworkX)"
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
        # Check if any files exist in the working directory
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
                # Storage 정리
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

        LightRAG의 naive 모드를 사용하여 순수 벡터 검색 수행 (NanoVectorDB).

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
