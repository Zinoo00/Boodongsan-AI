"""
Database session management for PostgreSQL.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)

# Global engine instance
_engine: AsyncEngine | None = None
_session_maker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """
    PostgreSQL 엔진 가져오기.

    Returns:
        AsyncEngine instance
    """
    global _engine
    if _engine is None:
        if not settings.DATABASE_URL:
            raise ValueError("DATABASE_URL not configured")

        _engine = create_async_engine(
            settings.DATABASE_URL,
            echo=settings.DATABASE_ECHO,
            pool_size=settings.DATABASE_POOL_SIZE,
            max_overflow=settings.DATABASE_MAX_OVERFLOW,
            pool_timeout=settings.DATABASE_POOL_TIMEOUT,
            pool_pre_ping=True,  # Verify connections before using
        )
        logger.info("PostgreSQL engine created")
    return _engine


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    """
    세션 메이커 가져오기.

    Returns:
        async_sessionmaker instance
    """
    global _session_maker
    if _session_maker is None:
        engine = get_engine()
        _session_maker = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
        logger.info("Session maker created")
    return _session_maker


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    데이터베이스 세션 의존성 주입.

    Yields:
        AsyncSession instance
    """
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """
    데이터베이스 초기화.

    - pgvector 확장 설치
    - 테이블 생성
    """
    from database.base import Base
    from database.models import Document, Entity, GraphRelation  # noqa: F401

    engine = get_engine()

    async with engine.begin() as conn:
        # pgvector 확장 설치
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        logger.info("pgvector extension created")

        # 테이블 생성
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created")


async def close_db() -> None:
    """데이터베이스 연결 종료."""
    global _engine, _session_maker

    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_maker = None
        logger.info("Database connections closed")
