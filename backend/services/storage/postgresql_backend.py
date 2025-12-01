"""
PostgreSQL storage backend with pgvector.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select

from database.models import Document, Entity, GraphRelation
from database.session import get_session_maker, init_db
from services.storage.base import StorageBackend

logger = logging.getLogger(__name__)


class PostgreSQLBackend(StorageBackend):
    """
    PostgreSQL + pgvector storage backend.

    Features:
    - Vector similarity search using pgvector
    - Graph relations stored in PostgreSQL
    - Efficient querying with indexes
    """

    def __init__(self) -> None:
        """PostgreSQL backend 초기화."""
        self._initialized = False
        self._session_maker = None
        self._is_empty_cache: bool | None = None

    async def initialize(self) -> None:
        """PostgreSQL 연결 및 테이블 초기화."""
        if self._initialized:
            logger.info("PostgreSQL backend already initialized")
            return

        try:
            # 데이터베이스 초기화 (pgvector 확장 + 테이블 생성)
            await init_db()
            self._session_maker = get_session_maker()
            self._initialized = True

            # 초기화 시점에 is_empty 상태 캐싱
            await self._update_empty_cache()

            logger.info("PostgreSQL backend initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL backend: {e}")
            raise

    async def finalize(self) -> None:
        """PostgreSQL 연결 종료."""
        if self._initialized:
            from database.session import close_db

            await close_db()
            self._initialized = False
            logger.info("PostgreSQL backend finalized")

    async def insert_document(self, text: str, metadata: dict[str, Any] | None = None) -> bool:
        """
        문서 삽입.

        Args:
            text: 문서 내용
            metadata: 메타데이터

        Returns:
            성공 여부
        """
        if not self._initialized:
            await self.initialize()

        try:
            async with self._session_maker() as session:
                document = Document(
                    content=text,
                    doc_metadata=metadata or {},
                )
                session.add(document)
                await session.commit()
                logger.info(f"Inserted document: {document.id}")
                return True

        except Exception as e:
            logger.error(f"Failed to insert document: {e}")
            return False

    async def insert_entity(
        self,
        entity_id: str,
        entity_type: str,
        description: str | None = None,
        properties: dict[str, Any] | None = None,
        embedding: list[float] | None = None,
    ) -> bool:
        """
        엔티티 삽입.

        Args:
            entity_id: 엔티티 고유 ID
            entity_type: 엔티티 타입
            description: 엔티티 설명
            properties: 추가 속성
            embedding: 임베딩 벡터

        Returns:
            성공 여부
        """
        if not self._initialized:
            await self.initialize()

        try:
            async with self._session_maker() as session:
                # Check if entity exists
                result = await session.execute(
                    select(Entity).where(Entity.entity_id == entity_id)
                )
                existing_entity = result.scalar_one_or_none()

                if existing_entity:
                    # Update existing entity
                    existing_entity.description = description
                    existing_entity.properties = properties or {}
                    if embedding:
                        existing_entity.embedding = embedding
                else:
                    # Create new entity
                    entity = Entity(
                        entity_id=entity_id,
                        entity_type=entity_type,
                        description=description,
                        properties=properties or {},
                        embedding=embedding,
                    )
                    session.add(entity)

                await session.commit()
                logger.debug(f"Inserted/updated entity: {entity_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to insert entity {entity_id}: {e}")
            return False

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
        관계 삽입.

        Args:
            source_entity: 시작 엔티티 ID
            target_entity: 목표 엔티티 ID
            relation_type: 관계 타입
            description: 관계 설명
            weight: 관계 가중치
            properties: 추가 속성

        Returns:
            성공 여부
        """
        if not self._initialized:
            await self.initialize()

        try:
            async with self._session_maker() as session:
                relation = GraphRelation(
                    source_entity=source_entity,
                    target_entity=target_entity,
                    relation_type=relation_type,
                    description=description,
                    weight=weight,
                    properties=properties or {},
                )
                session.add(relation)
                await session.commit()
                logger.debug(
                    f"Inserted relation: {source_entity} -[{relation_type}]-> {target_entity}"
                )
                return True

        except Exception as e:
            logger.error(f"Failed to insert relation: {e}")
            return False

    async def search_similar_vectors(
        self, query_embedding: list[float], limit: int = 10
    ) -> list[dict[str, Any]]:
        """
        벡터 유사도 검색 using pgvector.

        Args:
            query_embedding: 쿼리 임베딩 벡터
            limit: 최대 결과 수

        Returns:
            검색 결과 리스트
        """
        if not self._initialized:
            await self.initialize()

        try:
            async with self._session_maker() as session:
                # pgvector cosine similarity search
                # <=> operator: cosine distance (1 - cosine similarity)
                stmt = (
                    select(
                        Entity,
                        Entity.embedding.cosine_distance(query_embedding).label("distance"),
                    )
                    .where(Entity.embedding.isnot(None))
                    .order_by("distance")
                    .limit(limit)
                )

                result = await session.execute(stmt)
                rows = result.all()

                results = []
                for entity, distance in rows:
                    results.append(
                        {
                            "entity_id": entity.entity_id,
                            "entity_type": entity.entity_type,
                            "description": entity.description,
                            "properties": entity.properties,
                            "score": 1.0 - distance,  # Convert distance to similarity
                            "distance": distance,
                        }
                    )

                logger.info(f"Vector search found {len(results)} results")
                return results

        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []

    async def get_entity(self, entity_id: str) -> dict[str, Any] | None:
        """
        엔티티 조회.

        Args:
            entity_id: 엔티티 ID

        Returns:
            엔티티 정보 또는 None
        """
        if not self._initialized:
            await self.initialize()

        try:
            async with self._session_maker() as session:
                result = await session.execute(
                    select(Entity).where(Entity.entity_id == entity_id)
                )
                entity = result.scalar_one_or_none()

                if not entity:
                    return None

                return {
                    "entity_id": entity.entity_id,
                    "entity_type": entity.entity_type,
                    "description": entity.description,
                    "properties": entity.properties,
                }

        except Exception as e:
            logger.error(f"Failed to get entity {entity_id}: {e}")
            return None

    async def get_entity_relations(
        self, entity_id: str, relation_type: str | None = None
    ) -> list[dict[str, Any]]:
        """
        엔티티의 관계 조회.

        Args:
            entity_id: 엔티티 ID
            relation_type: 관계 타입 (optional filter)

        Returns:
            관계 리스트
        """
        if not self._initialized:
            await self.initialize()

        try:
            async with self._session_maker() as session:
                # Query relations where entity is source or target
                stmt = select(GraphRelation).where(
                    (GraphRelation.source_entity == entity_id)
                    | (GraphRelation.target_entity == entity_id)
                )

                if relation_type:
                    stmt = stmt.where(GraphRelation.relation_type == relation_type)

                result = await session.execute(stmt)
                relations = result.scalars().all()

                return [
                    {
                        "source_entity": rel.source_entity,
                        "target_entity": rel.target_entity,
                        "relation_type": rel.relation_type,
                        "description": rel.description,
                        "weight": rel.weight,
                        "properties": rel.properties,
                    }
                    for rel in relations
                ]

        except Exception as e:
            logger.error(f"Failed to get relations for entity {entity_id}: {e}")
            return []

    async def _update_empty_cache(self) -> None:
        """
        테이블 데이터 존재 여부 캐시 업데이트.

        초기화 시점 및 데이터 삽입 후 호출.
        """
        if not self._session_maker:
            self._is_empty_cache = True
            return

        try:
            async with self._session_maker() as session:
                # documents, entities, relations 중 하나라도 데이터가 있으면 not empty
                doc_count = await session.execute(select(func.count()).select_from(Document))
                if doc_count.scalar() > 0:
                    self._is_empty_cache = False
                    return

                entity_count = await session.execute(select(func.count()).select_from(Entity))
                if entity_count.scalar() > 0:
                    self._is_empty_cache = False
                    return

                relation_count = await session.execute(
                    select(func.count()).select_from(GraphRelation)
                )
                if relation_count.scalar() > 0:
                    self._is_empty_cache = False
                    return

                self._is_empty_cache = True

        except Exception as e:
            logger.warning(f"Failed to check if storage is empty: {e}")
            self._is_empty_cache = False  # Conservative: assume not empty on error

    def is_empty(self) -> bool:
        """
        Storage가 비어있는지 확인.

        Returns:
            True if empty, False otherwise
        """
        # 캐시된 값 반환 (동기 메서드이므로 초기화 시점에 캐싱된 값 사용)
        if self._is_empty_cache is None:
            # 초기화 전에는 True 반환 (데이터 없음으로 가정)
            return True
        return self._is_empty_cache

    async def check_is_empty(self) -> bool:
        """
        Storage가 비어있는지 비동기로 확인.

        캐시를 업데이트하고 결과 반환.

        Returns:
            True if empty, False otherwise
        """
        await self._update_empty_cache()
        return self._is_empty_cache if self._is_empty_cache is not None else True
