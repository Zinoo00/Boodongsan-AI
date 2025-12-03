"""
Base storage backend interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class StorageBackend(ABC):
    """
    Storage backend 추상 인터페이스.

    모든 storage backend는 이 인터페이스를 구현해야 함.
    """

    @abstractmethod
    async def initialize(self) -> None:
        """Storage 초기화."""
        ...

    @abstractmethod
    async def finalize(self) -> None:
        """Storage 정리 및 종료."""
        ...

    @abstractmethod
    async def insert_document(self, text: str, metadata: dict[str, Any] | None = None) -> bool:
        """
        문서 삽입.

        Args:
            text: 문서 내용
            metadata: 메타데이터

        Returns:
            성공 여부
        """
        ...

    @abstractmethod
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
        ...

    @abstractmethod
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
        ...

    @abstractmethod
    async def search_similar_vectors(
        self, query_embedding: list[float], limit: int = 10
    ) -> list[dict[str, Any]]:
        """
        벡터 유사도 검색.

        Args:
            query_embedding: 쿼리 임베딩 벡터
            limit: 최대 결과 수

        Returns:
            검색 결과 리스트
        """
        ...

    @abstractmethod
    async def get_entity(self, entity_id: str) -> dict[str, Any] | None:
        """
        엔티티 조회.

        Args:
            entity_id: 엔티티 ID

        Returns:
            엔티티 정보 또는 None
        """
        ...

    @abstractmethod
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
        ...

    @abstractmethod
    def is_empty(self) -> bool:
        """
        Storage가 비어있는지 확인.

        Returns:
            True if empty, False otherwise
        """
        ...
