"""
Local storage backend using LightRAG defaults (NanoVectorDB + NetworkX + JSON).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from services.storage.base import StorageBackend

logger = logging.getLogger(__name__)


class LocalBackend(StorageBackend):
    """
    Local storage backend using LightRAG embedded storage.

    Uses:
    - NanoVectorDB for vector search (embedded)
    - NetworkX for graph storage (local)
    - JSON files for document status (local)
    """

    def __init__(self, working_dir: Path) -> None:
        """
        Local backend 초기화.

        Args:
            working_dir: 로컬 저장소 디렉토리
        """
        self.working_dir = working_dir
        self._initialized = False

    async def initialize(self) -> None:
        """로컬 스토리지 초기화."""
        if self._initialized:
            logger.info("Local backend already initialized")
            return

        # Ensure working directory exists
        self.working_dir.mkdir(parents=True, exist_ok=True)
        self._initialized = True
        logger.info(f"Local backend initialized at {self.working_dir}")

    async def finalize(self) -> None:
        """로컬 스토리지 정리."""
        self._initialized = False
        logger.info("Local backend finalized")

    async def insert_document(self, text: str, metadata: dict[str, Any] | None = None) -> bool:
        """
        문서 삽입 (LightRAG에서 처리).

        Local backend는 LightRAG가 직접 처리하므로 여기서는 패스스루.
        """
        return True

    async def insert_entity(
        self,
        entity_id: str,
        entity_type: str,
        description: str | None = None,
        properties: dict[str, Any] | None = None,
        embedding: list[float] | None = None,
    ) -> bool:
        """
        엔티티 삽입 (LightRAG에서 처리).

        Local backend는 LightRAG가 직접 처리하므로 여기서는 패스스루.
        """
        return True

    async def insert_relation(
        self,
        source_entity: str,
        target_entity: str,
        relation_type: str,
        description: str | None = None,
        weight: float = 1.0,
        properties: dict[str, Any] | None = None,
    ) -> bool:
        """
        관계 삽입 (LightRAG에서 처리).

        Local backend는 LightRAG가 직접 처리하므로 여기서는 패스스루.
        """
        return True

    async def search_similar_vectors(
        self, query_embedding: list[float], limit: int = 10
    ) -> list[dict[str, Any]]:
        """
        벡터 유사도 검색 (LightRAG에서 처리).

        Local backend는 LightRAG의 NanoVectorDB를 사용.
        """
        return []

    async def get_entity(self, entity_id: str) -> dict[str, Any] | None:
        """
        엔티티 조회 (LightRAG에서 처리).

        Local backend는 LightRAG가 직접 처리하므로 여기서는 None 반환.
        """
        return None

    async def get_entity_relations(
        self, entity_id: str, relation_type: str | None = None
    ) -> list[dict[str, Any]]:
        """
        엔티티의 관계 조회 (LightRAG에서 처리).

        Local backend는 LightRAG가 직접 처리하므로 여기서는 빈 리스트 반환.
        """
        return []

    def is_empty(self) -> bool:
        """
        Storage가 비어있는지 확인.

        Returns:
            True if empty, False otherwise
        """
        if not self.working_dir.exists():
            return True

        # Check for any data files
        files = list(self.working_dir.glob("**/*"))
        data_files = [f for f in files if f.is_file() and f.suffix in {".json", ".pkl", ".db"}]

        return len(data_files) == 0
