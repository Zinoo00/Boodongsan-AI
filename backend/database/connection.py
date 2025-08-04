"""
데이터베이스 연결 설정
PostgreSQL 및 Redis 연결 관리
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

import asyncpg
import aioredis
from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from .models import Base

logger = logging.getLogger(__name__)

class DatabaseConfig:
    """데이터베이스 설정"""
    
    def __init__(self):
        # PostgreSQL 설정
        self.postgres_host = os.getenv("POSTGRES_HOST", "localhost")
        self.postgres_port = os.getenv("POSTGRES_PORT", "5432")
        self.postgres_db = os.getenv("POSTGRES_DB", "boodongsan")
        self.postgres_user = os.getenv("POSTGRES_USER", "postgres")
        self.postgres_password = os.getenv("POSTGRES_PASSWORD", "password")
        
        # Redis 설정
        self.redis_host = os.getenv("REDIS_HOST", "localhost")
        self.redis_port = int(os.getenv("REDIS_PORT", "6379"))
        self.redis_db = int(os.getenv("REDIS_DB", "0"))
        self.redis_password = os.getenv("REDIS_PASSWORD")
        
        # 연결 풀 설정
        self.pool_size = int(os.getenv("DB_POOL_SIZE", "10"))
        self.max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "20"))
        self.pool_timeout = int(os.getenv("DB_POOL_TIMEOUT", "30"))
        
        # SSL 설정
        self.ssl_mode = os.getenv("DB_SSL_MODE", "prefer")
    
    @property
    def postgres_url(self) -> str:
        """PostgreSQL 연결 URL"""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
    
    @property
    def async_postgres_url(self) -> str:
        """비동기 PostgreSQL 연결 URL"""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
    
    @property
    def redis_url(self) -> str:
        """Redis 연결 URL"""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

# 전역 설정 인스턴스
db_config = DatabaseConfig()

# SQLAlchemy 엔진들
async_engine = None
sync_engine = None
async_session_factory = None
sync_session_factory = None

# Redis 연결
redis_client = None

async def initialize_database():
    """데이터베이스 초기화"""
    global async_engine, sync_engine, async_session_factory, sync_session_factory, redis_client
    
    try:
        # 비동기 엔진 생성
        async_engine = create_async_engine(
            db_config.async_postgres_url,
            pool_size=db_config.pool_size,
            max_overflow=db_config.max_overflow,
            pool_timeout=db_config.pool_timeout,
            echo=os.getenv("DB_ECHO", "false").lower() == "true",
            future=True
        )
        
        # 동기 엔진 생성 (마이그레이션 등에 사용)
        sync_engine = create_engine(
            db_config.postgres_url,
            pool_size=db_config.pool_size,
            max_overflow=db_config.max_overflow,
            pool_timeout=db_config.pool_timeout,
            echo=os.getenv("DB_ECHO", "false").lower() == "true"
        )
        
        # 세션 팩토리 생성
        async_session_factory = async_sessionmaker(
            async_engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        sync_session_factory = sessionmaker(
            sync_engine,
            class_=Session,
            expire_on_commit=False
        )
        
        # Redis 클라이언트 초기화
        redis_client = await aioredis.from_url(
            db_config.redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20
        )
        
        # 연결 테스트
        await test_connections()
        
        logger.info("데이터베이스 초기화 완료")
        
    except Exception as e:
        logger.error(f"데이터베이스 초기화 실패: {str(e)}")
        raise

async def test_connections():
    """데이터베이스 연결 테스트"""
    try:
        # PostgreSQL 연결 테스트
        async with async_engine.begin() as conn:
            result = await conn.execute("SELECT 1")
            assert result.scalar() == 1
        
        # Redis 연결 테스트
        await redis_client.ping()
        
        logger.info("데이터베이스 연결 테스트 성공")
        
    except Exception as e:
        logger.error(f"데이터베이스 연결 테스트 실패: {str(e)}")
        raise

@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """비동기 데이터베이스 세션 컨텍스트 매니저"""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

def get_sync_db_session() -> Session:
    """동기 데이터베이스 세션"""
    return sync_session_factory()

async def get_redis_client():
    """Redis 클라이언트 반환"""
    return redis_client

async def create_tables():
    """테이블 생성"""
    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("테이블 생성 완료")
        
    except Exception as e:
        logger.error(f"테이블 생성 실패: {str(e)}")
        raise

async def drop_tables():
    """테이블 삭제 (개발용)"""
    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        logger.info("테이블 삭제 완료")
        
    except Exception as e:
        logger.error(f"테이블 삭제 실패: {str(e)}")
        raise

async def reset_database():
    """데이터베이스 리셋 (개발용)"""
    try:
        await drop_tables()
        await create_tables()
        logger.info("데이터베이스 리셋 완료")
        
    except Exception as e:
        logger.error(f"데이터베이스 리셋 실패: {str(e)}")
        raise

class CacheManager:
    """Redis 캐시 관리자"""
    
    def __init__(self):
        self.default_ttl = 3600  # 1시간
    
    async def get(self, key: str) -> Optional[str]:
        """캐시 값 조회"""
        try:
            return await redis_client.get(key)
        except Exception as e:
            logger.error(f"캐시 조회 실패 {key}: {str(e)}")
            return None
    
    async def set(self, key: str, value: str, ttl: int = None) -> bool:
        """캐시 값 저장"""
        try:
            ttl = ttl or self.default_ttl
            await redis_client.setex(key, ttl, value)
            return True
        except Exception as e:
            logger.error(f"캐시 저장 실패 {key}: {str(e)}")
            return False
    
    async def delete(self, key: str) -> bool:
        """캐시 값 삭제"""
        try:
            result = await redis_client.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"캐시 삭제 실패 {key}: {str(e)}")
            return False
    
    async def exists(self, key: str) -> bool:
        """캐시 키 존재 확인"""
        try:
            result = await redis_client.exists(key)
            return result > 0
        except Exception as e:
            logger.error(f"캐시 존재 확인 실패 {key}: {str(e)}")
            return False
    
    async def clear_pattern(self, pattern: str) -> int:
        """패턴에 맞는 키들 삭제"""
        try:
            keys = await redis_client.keys(pattern)
            if keys:
                return await redis_client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"패턴 캐시 삭제 실패 {pattern}: {str(e)}")
            return 0
    
    async def get_json(self, key: str) -> Optional[dict]:
        """JSON 형태 캐시 값 조회"""
        try:
            import json
            value = await self.get(key)
            return json.loads(value) if value else None
        except Exception as e:
            logger.error(f"JSON 캐시 조회 실패 {key}: {str(e)}")
            return None
    
    async def set_json(self, key: str, value: dict, ttl: int = None) -> bool:
        """JSON 형태 캐시 값 저장"""
        try:
            import json
            json_value = json.dumps(value, ensure_ascii=False)
            return await self.set(key, json_value, ttl)
        except Exception as e:
            logger.error(f"JSON 캐시 저장 실패 {key}: {str(e)}")
            return False

# 전역 캐시 관리자 인스턴스
cache_manager = CacheManager()

async def health_check() -> dict:
    """데이터베이스 및 캐시 상태 확인"""
    status = {
        "postgres": False,
        "redis": False,
        "timestamp": None
    }
    
    try:
        # PostgreSQL 상태 확인
        async with async_engine.begin() as conn:
            await conn.execute("SELECT 1")
        status["postgres"] = True
        
    except Exception as e:
        logger.error(f"PostgreSQL 상태 확인 실패: {str(e)}")
    
    try:
        # Redis 상태 확인
        await redis_client.ping()
        status["redis"] = True
        
    except Exception as e:
        logger.error(f"Redis 상태 확인 실패: {str(e)}")
    
    from datetime import datetime
    status["timestamp"] = datetime.utcnow().isoformat()
    
    return status

async def cleanup_connections():
    """연결 정리"""
    try:
        if async_engine:
            await async_engine.dispose()
        
        if sync_engine:
            sync_engine.dispose()
        
        if redis_client:
            await redis_client.close()
        
        logger.info("데이터베이스 연결 정리 완료")
        
    except Exception as e:
        logger.error(f"연결 정리 실패: {str(e)}")

# 데이터베이스 세션 의존성 (FastAPI용)
async def get_database_session():
    """FastAPI 의존성으로 사용할 데이터베이스 세션"""
    async with get_db_session() as session:
        yield session