"""
PostgreSQL database models for RAG storage.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, Float, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class Document(Base):
    """
    문서 저장 테이블.

    LightRAG에서 추가한 원본 문서와 청크 정보 저장.
    """

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    doc_metadata: Mapped[dict] = mapped_column(JSON, nullable=True, default=dict)
    chunk_ids: Mapped[list] = mapped_column(JSON, nullable=True, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, created_at={self.created_at})>"


class Entity(Base):
    """
    엔티티 저장 테이블.

    Knowledge Graph의 노드(엔티티) 정보 저장.
    """

    __tablename__ = "entities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_id: Mapped[str] = mapped_column(String(500), unique=True, nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    properties: Mapped[dict] = mapped_column(JSON, nullable=True, default=dict)
    source_chunks: Mapped[list] = mapped_column(JSON, nullable=True, default=list)
    embedding: Mapped[list[float]] = mapped_column(
        Vector(1024), nullable=True
    )  # AWS Titan Embed v2 (1024 dimensions)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<Entity(id={self.entity_id}, type={self.entity_type})>"


class GraphRelation(Base):
    """
    그래프 관계 저장 테이블.

    Knowledge Graph의 엣지(관계) 정보 저장.
    """

    __tablename__ = "graph_relations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_entity: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    target_entity: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    relation_type: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    weight: Mapped[float] = mapped_column(Float, nullable=True, default=1.0)
    properties: Mapped[dict] = mapped_column(JSON, nullable=True, default=dict)
    source_chunks: Mapped[list] = mapped_column(JSON, nullable=True, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return (
            f"<GraphRelation({self.source_entity} -[{self.relation_type}]-> {self.target_entity})>"
        )
