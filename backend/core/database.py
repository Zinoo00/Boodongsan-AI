"""
데이터베이스 연결 관리 - AWS OpenSearch, Neo4j, Redis
Korean Real Estate RAG AI Chatbot
"""

import asyncio
import json
import logging
import time
from collections.abc import Callable
from typing import Any, TypeVar

import redis.asyncio as aioredis
from neo4j import AsyncGraphDatabase, AsyncDriver
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import settings
from .exceptions import CacheError, DatabaseError

logger = logging.getLogger(__name__)

T = TypeVar("T")

# 재시도 설정
DB_RETRY_ATTEMPTS = 3
DB_RETRY_WAIT_MIN = 1
DB_RETRY_WAIT_MAX = 10
CACHE_RETRY_ATTEMPTS = 2
CACHE_RETRY_WAIT = 0.5


class DatabaseManager:
    """Neo4j + Redis 연결 관리자 (OpenSearch는 별도 서비스에서 관리)"""

    def __init__(self):
        self.neo4j_driver: AsyncDriver | None = None
        self.redis_client = None
        self._initialized = False
        self._connection_stats = {
            "total_connections": 0,
            "active_connections": 0,
            "failed_connections": 0,
            "last_connection_attempt": None,
        }

    async def initialize(self):
        """Neo4j와 Redis 연결 초기화"""
        if self._initialized:
            return

        self._connection_stats["last_connection_attempt"] = time.time()

        try:
            logger.info("데이터베이스 초기화 시작...")

            # Neo4j 드라이버 초기화
            logger.info(f"Neo4j 연결 중: {settings.NEO4J_URI}")
            self.neo4j_driver = AsyncGraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(
                    settings.NEO4J_USERNAME,
                    settings.get_secret_value("NEO4J_PASSWORD")
                ),
                max_connection_pool_size=settings.NEO4J_MAX_CONNECTION_POOL_SIZE,
                connection_timeout=settings.NEO4J_CONNECTION_TIMEOUT,
            )

            # Neo4j 연결 테스트
            await self.neo4j_driver.verify_connectivity()
            logger.info("Neo4j 연결 성공")

            # Redis 클라이언트 초기화
            logger.info(f"Redis 연결 중: {settings.REDIS_URL}")
            redis_kwargs = {
                "encoding": "utf-8",
                "decode_responses": True,
                "socket_connect_timeout": 5,
                "socket_timeout": 5,
            }

            if hasattr(settings, 'REDIS_PASSWORD') and settings.REDIS_PASSWORD:
                redis_kwargs["password"] = settings.REDIS_PASSWORD

            self.redis_client = await aioredis.from_url(settings.REDIS_URL, **redis_kwargs)
            await self.redis_client.ping()
            logger.info("Redis 연결 성공")

            self._initialized = True
            self._connection_stats["total_connections"] += 1

            logger.info("데이터베이스 초기화 완료")

        except Exception as e:
            self._connection_stats["failed_connections"] += 1
            logger.error(f"데이터베이스 초기화 실패: {str(e)}")
            raise DatabaseError(
                message="데이터베이스 초기화 실패",
                operation="initialize",
                cause=e
            )

    def get_neo4j(self) -> AsyncDriver:
        """Neo4j 드라이버 가져오기"""
        if not self._initialized or self.neo4j_driver is None:
            raise DatabaseError(
                message="Neo4j 드라이버가 초기화되지 않음",
                operation="get_neo4j"
            )
        return self.neo4j_driver

    async def get_redis(self):
        """Redis 클라이언트 가져오기 (재연결 지원)"""
        if not self._initialized:
            await self.initialize()

        try:
            await self.redis_client.ping()
            return self.redis_client

        except Exception as e:
            logger.warning(f"Redis 재연결 시도: {str(e)}")

            try:
                await self.redis_client.close()
            except:
                pass

            # Redis 재연결
            redis_kwargs = {
                "encoding": "utf-8",
                "decode_responses": True,
                "max_connections": 20,
                "retry_on_timeout": True,
                "health_check_interval": 30,
            }

            if settings.REDIS_PASSWORD:
                redis_kwargs["password"] = settings.REDIS_PASSWORD

            self.redis_client = await aioredis.from_url(settings.REDIS_URL, **redis_kwargs)
            return self.redis_client

    async def close(self):
        """모든 연결 종료"""
        close_errors = []

        try:
            if self.neo4j_driver:
                await self.neo4j_driver.close()
                logger.debug("Neo4j 드라이버 종료")
        except Exception as e:
            close_errors.append(f"Neo4j: {str(e)}")
            logger.error(f"Neo4j 종료 오류: {str(e)}")

        try:
            if self.redis_client:
                await self.redis_client.close()
                logger.debug("Redis 클라이언트 종료")
        except Exception as e:
            close_errors.append(f"Redis: {str(e)}")
            logger.error(f"Redis 종료 오류: {str(e)}")

        self._initialized = False

        if close_errors:
            logger.warning(f"연결 종료 시 오류 발생: {close_errors}")
        else:
            logger.info("모든 연결 정상 종료")

    async def execute_with_retry(self, operation: Callable[[], T], max_retries: int = 3) -> T:
        """재시도 로직을 포함한 작업 실행"""
        for attempt in range(max_retries):
            try:
                return await operation()
            except Exception as e:
                if attempt == max_retries - 1:
                    raise DatabaseError(
                        message=f"작업 실패 (재시도 {max_retries}회)",
                        operation="execute_with_retry",
                        cause=e,
                    )

                wait_time = (2**attempt) * 0.5
                logger.warning(
                    f"작업 실패 (시도 {attempt + 1}/{max_retries}), {wait_time}초 후 재시도",
                    extra={"error": str(e), "wait_time": wait_time},
                )
                await asyncio.sleep(wait_time)

        raise DatabaseError(
            message="모든 재시도 실패",
            operation="execute_with_retry",
        )

    async def health_check(self) -> dict[str, Any]:
        """헬스 체크 (Neo4j + Redis)"""
        from datetime import datetime

        status = {
            "neo4j": {"status": False, "latency_ms": None},
            "redis": {"status": False, "latency_ms": None, "memory_usage": None},
            "connection_stats": self._connection_stats.copy(),
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Neo4j 헬스 체크
        try:
            start_time = time.time()
            async with self.neo4j_driver.session() as session:
                result = await session.run("RETURN 1 AS health")
                await result.single()
            latency = (time.time() - start_time) * 1000
            status["neo4j"].update(
                {"status": True, "latency_ms": round(latency, 2)}
            )
        except Exception as e:
            logger.error(f"Neo4j 헬스 체크 실패: {str(e)}")
            status["neo4j"]["error"] = str(e)

        # Redis 헬스 체크
        try:
            start_time = time.time()
            await self.redis_client.ping()

            redis_info = await self.redis_client.info("memory")
            memory_stats = {
                "used_memory": redis_info.get("used_memory"),
                "used_memory_human": redis_info.get("used_memory_human"),
                "used_memory_peak": redis_info.get("used_memory_peak"),
            }

            latency = (time.time() - start_time) * 1000
            status["redis"].update(
                {"status": True, "latency_ms": round(latency, 2), "memory_usage": memory_stats}
            )
        except Exception as e:
            logger.error(f"Redis 헬스 체크 실패: {str(e)}")
            status["redis"]["error"] = str(e)

        return status


class CacheManager:
    """Redis 캐시 관리자 (재시도 로직 포함)"""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.default_ttl = settings.CACHE_TTL
        self._cache_stats = {"hits": 0, "misses": 0, "errors": 0, "total_operations": 0}

    @retry(
        stop=stop_after_attempt(CACHE_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=CACHE_RETRY_WAIT, max=2),
    )
    async def get(self, key: str) -> str | None:
        """캐시에서 값 가져오기"""
        self._cache_stats["total_operations"] += 1

        try:
            redis_client = await self.db_manager.get_redis()
            value = await redis_client.get(key)

            if value is not None:
                self._cache_stats["hits"] += 1
            else:
                self._cache_stats["misses"] += 1

            return value

        except Exception as e:
            self._cache_stats["errors"] += 1
            self._cache_stats["misses"] += 1
            logger.error(f"캐시 조회 실패 (key: {key}): {str(e)}")
            raise CacheError(
                message="캐시 조회 실패",
                operation="get",
                details={"key": key},
                cause=e
            )

    @retry(
        stop=stop_after_attempt(CACHE_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=CACHE_RETRY_WAIT, max=2),
    )
    async def set(self, key: str, value: str, ttl: int | None = None) -> bool:
        """캐시에 값 저장"""
        self._cache_stats["total_operations"] += 1

        try:
            redis_client = await self.db_manager.get_redis()
            ttl = ttl or self.default_ttl
            await redis_client.setex(key, ttl, value)
            return True

        except Exception as e:
            self._cache_stats["errors"] += 1
            logger.error(f"캐시 저장 실패 (key: {key}): {str(e)}")
            return False

    async def delete(self, key: str) -> bool:
        """캐시에서 값 삭제"""
        try:
            redis_client = await self.db_manager.get_redis()
            result = await redis_client.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"캐시 삭제 실패 (key: {key}): {str(e)}")
            return False

    async def exists(self, key: str) -> bool:
        """캐시에 키 존재 여부 확인"""
        try:
            redis_client = await self.db_manager.get_redis()
            result = await redis_client.exists(key)
            return result > 0
        except Exception as e:
            logger.error(f"캐시 존재 확인 실패 (key: {key}): {str(e)}")
            return False

    async def get_json(self, key: str) -> dict[str, Any] | None:
        """JSON 값 가져오기"""
        try:
            value = await self.get(key)
            if value:
                return json.loads(value)
            return None

        except json.JSONDecodeError as e:
            logger.warning(f"잘못된 JSON 캐시 (key: {key}): {str(e)}")
            await self.delete(key)  # 손상된 캐시 삭제
            return None

        except Exception as e:
            logger.error(f"JSON 캐시 조회 실패 (key: {key}): {str(e)}")
            return None

    async def set_json(self, key: str, value: dict[str, Any], ttl: int | None = None) -> bool:
        """JSON 값 저장"""
        try:
            json_value = json.dumps(value, ensure_ascii=False, default=str)
            return await self.set(key, json_value, ttl)

        except (TypeError, ValueError) as e:
            logger.error(f"JSON 직렬화 실패 (key: {key}): {str(e)}")
            return False

        except Exception as e:
            logger.error(f"JSON 캐시 저장 실패 (key: {key}): {str(e)}")
            return False

    def get_cache_stats(self) -> dict[str, Any]:
        """캐시 성능 통계"""
        total_ops = self._cache_stats["total_operations"]
        if total_ops > 0:
            hit_rate = (self._cache_stats["hits"] / total_ops) * 100
            error_rate = (self._cache_stats["errors"] / total_ops) * 100
        else:
            hit_rate = 0
            error_rate = 0

        return {
            **self._cache_stats,
            "hit_rate_percent": round(hit_rate, 2),
            "error_rate_percent": round(error_rate, 2),
        }

    def reset_cache_stats(self):
        """캐시 통계 초기화"""
        self._cache_stats = {"hits": 0, "misses": 0, "errors": 0, "total_operations": 0}

    async def clear_pattern(self, pattern: str) -> int:
        """패턴과 일치하는 모든 키 삭제"""
        try:
            redis_client = await self.db_manager.get_redis()
            keys = await redis_client.keys(pattern)
            if keys:
                return await redis_client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"패턴 캐시 삭제 실패 (pattern: {pattern}): {str(e)}")
            return 0

    async def increment(self, key: str, amount: int = 1) -> int | None:
        """카운터 증가"""
        try:
            redis_client = await self.db_manager.get_redis()
            return await redis_client.incrby(key, amount)
        except Exception as e:
            logger.error(f"캐시 증가 실패 (key: {key}): {str(e)}")
            return None

    async def expire(self, key: str, ttl: int) -> bool:
        """키의 만료 시간 설정"""
        try:
            redis_client = await self.db_manager.get_redis()
            return await redis_client.expire(key, ttl)
        except Exception as e:
            logger.error(f"만료 시간 설정 실패 (key: {key}): {str(e)}")
            return False


# 전역 데이터베이스 매니저 인스턴스
db_manager = DatabaseManager()
cache_manager = CacheManager(db_manager)


# 의존성 주입용 헬퍼
class DatabaseDependency:
    """의존성 주입 헬퍼"""

    @staticmethod
    def get_neo4j() -> AsyncDriver:
        """Neo4j 드라이버 가져오기"""
        return db_manager.get_neo4j()

    @staticmethod
    async def get_redis():
        """Redis 클라이언트 가져오기"""
        return await db_manager.get_redis()

    @staticmethod
    async def get_cache_manager():
        """캐시 매니저 가져오기"""
        return cache_manager


def get_neo4j_driver() -> AsyncDriver:
    """FastAPI 의존성용 Neo4j 드라이버"""
    return db_manager.get_neo4j()


async def get_redis_client():
    """FastAPI 의존성용 Redis 클라이언트"""
    return await db_manager.get_redis()


async def get_cache_manager():
    """FastAPI 의존성용 캐시 매니저"""
    return cache_manager


# 앱 시작/종료 함수
async def initialize_database():
    """데이터베이스 초기화 (앱 시작 시)"""
    try:
        await db_manager.initialize()
        logger.info("데이터베이스 초기화 완료")
    except Exception as e:
        logger.error(f"데이터베이스 초기화 실패: {str(e)}")
        raise


async def cleanup_database():
    """데이터베이스 정리 (앱 종료 시)"""
    await db_manager.close()


async def database_health_check():
    """데이터베이스 헬스 체크"""
    try:
        health_status = await db_manager.health_check()
        health_status["cache_stats"] = cache_manager.get_cache_stats()
        return health_status

    except Exception as e:
        logger.error(f"헬스 체크 실패: {str(e)}")
        return {
            "neo4j": {"status": False, "error": str(e)},
            "redis": {"status": False, "error": str(e)},
            "timestamp": time.time(),
        }
