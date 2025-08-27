"""
Database connection and management for Korean Real Estate RAG AI Chatbot
Supabase PostgreSQL and Redis integration
"""

import asyncio
import json
import logging
import time
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from typing import Any, TypeVar

import redis.asyncio as aioredis
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import DisconnectionError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .config import settings
from .exceptions import CacheError, DatabaseError

logger = logging.getLogger(__name__)

# Type variable for generic functions
T = TypeVar("T")

# Connection retry configuration
DB_RETRY_ATTEMPTS = 3
DB_RETRY_WAIT_MIN = 1
DB_RETRY_WAIT_MAX = 10

# Cache retry configuration
CACHE_RETRY_ATTEMPTS = 2
CACHE_RETRY_WAIT = 0.5


class DatabaseManager:
    """Enhanced database connection manager with retry logic and monitoring"""

    def __init__(self):
        self.async_engine = None
        self.sync_engine = None
        self.async_session_factory = None
        self.sync_session_factory = None
        self.redis_client = None
        self._initialized = False
        self._connection_pool_stats = {
            "total_connections": 0,
            "active_connections": 0,
            "failed_connections": 0,
            "last_connection_attempt": None,
        }

    @retry(
        stop=stop_after_attempt(DB_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=DB_RETRY_WAIT_MIN, max=DB_RETRY_WAIT_MAX),
        retry=retry_if_exception_type((OperationalError, DisconnectionError)),
    )
    async def initialize(self):
        """Initialize database connections with retry logic"""
        if self._initialized:
            return

        self._connection_pool_stats["last_connection_attempt"] = time.time()

        try:
            # Create async PostgreSQL engine with enhanced configuration
            self.async_engine = create_async_engine(
                settings.DATABASE_URL,
                pool_size=settings.DB_POOL_SIZE,
                max_overflow=settings.DB_MAX_OVERFLOW,
                pool_timeout=30,
                pool_recycle=3600,  # Recycle connections every hour
                pool_pre_ping=True,
                echo=settings.DEBUG,
                future=True,
                connect_args={
                    "statement_timeout": 30000,  # 30 seconds
                    "command_timeout": 60,
                    "server_settings": {
                        "application_name": settings.APP_NAME,
                        "jit": "off",  # Disable JIT for better connection performance
                    },
                },
            )

            # Add connection pool event listeners
            self._setup_pool_events(self.async_engine)

            # Create sync PostgreSQL engine (for migrations)
            sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
            self.sync_engine = create_engine(
                sync_url,
                poolclass=QueuePool,
                pool_size=max(2, settings.DB_POOL_SIZE // 2),  # Smaller pool for sync
                max_overflow=settings.DB_MAX_OVERFLOW // 2,
                pool_timeout=30,
                pool_recycle=3600,
                pool_pre_ping=True,
                echo=settings.DEBUG,
                connect_args={
                    "application_name": f"{settings.APP_NAME}_sync",
                },
            )

            # Create session factories
            self.async_session_factory = async_sessionmaker(
                self.async_engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=True,
                autocommit=False,
            )

            self.sync_session_factory = sessionmaker(
                self.sync_engine,
                class_=Session,
                expire_on_commit=False,
                autoflush=True,
                autocommit=False,
            )

            # Initialize Redis client with enhanced configuration
            redis_kwargs = {
                "encoding": "utf-8",
                "decode_responses": True,
                "max_connections": 20,
                "retry_on_timeout": True,
                "retry_on_error": [ConnectionError, TimeoutError],
                "health_check_interval": 30,
                "socket_connect_timeout": 5,
                "socket_timeout": 5,
                "socket_keepalive": True,
                "socket_keepalive_options": {},
            }

            if settings.REDIS_PASSWORD:
                redis_kwargs["password"] = settings.REDIS_PASSWORD

            self.redis_client = await aioredis.from_url(settings.REDIS_URL, **redis_kwargs)

            # Test connections with detailed validation
            await self._test_connections()

            self._initialized = True
            self._connection_pool_stats["total_connections"] += 1

            logger.info(
                "Database connections initialized successfully",
                extra={
                    "pool_size": settings.DB_POOL_SIZE,
                    "max_overflow": settings.DB_MAX_OVERFLOW,
                    "redis_max_connections": 20,
                },
            )

        except Exception as e:
            self._connection_pool_stats["failed_connections"] += 1

            logger.error(
                "Failed to initialize database connections",
                extra={
                    "error": str(e),
                    "attempt_time": self._connection_pool_stats["last_connection_attempt"],
                },
            )

            raise DatabaseError(
                message="Database initialization failed", operation="initialize", cause=e
            )

    async def _test_connections(self):
        """Test database connections with comprehensive validation"""
        try:
            # Test PostgreSQL connection with detailed checks
            async with self.async_engine.begin() as conn:
                # Basic connectivity test
                result = await conn.execute(text("SELECT 1 as test"))
                assert result.scalar() == 1

                # Check database version and settings
                version_result = await conn.execute(text("SELECT version()"))
                db_version = version_result.scalar()

                # Test transaction capability
                await conn.execute(text("SELECT NOW()"))

                logger.info(f"PostgreSQL connection successful: {db_version}")

            # Test Redis connection with multiple operations
            await self.redis_client.ping()

            # Test Redis basic operations
            test_key = "health_check_test"
            await self.redis_client.set(test_key, "test_value", ex=10)
            test_value = await self.redis_client.get(test_key)
            assert test_value == "test_value"
            await self.redis_client.delete(test_key)

            redis_info = await self.redis_client.info()
            logger.info(
                "Redis connection successful",
                extra={
                    "redis_version": redis_info.get("redis_version"),
                    "connected_clients": redis_info.get("connected_clients"),
                },
            )

        except Exception as e:
            logger.error("Database connection test failed", extra={"error": str(e)}, exc_info=True)
            raise DatabaseError(
                message="Database connection test failed", operation="test_connections", cause=e
            )

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get async database session with enhanced error handling"""
        if not self._initialized:
            await self.initialize()

        session = None
        try:
            session = self.async_session_factory()
            self._connection_pool_stats["active_connections"] += 1

            yield session

        except (OperationalError, DisconnectionError) as e:
            if session:
                await session.rollback()

            logger.warning(
                "Database connection error, attempting to reinitialize", extra={"error": str(e)}
            )

            # Attempt to reinitialize on connection errors
            self._initialized = False
            await self.initialize()

            raise DatabaseError(
                message="Database connection lost", operation="get_session", cause=e
            )

        except Exception as e:
            if session:
                await session.rollback()

            raise DatabaseError(message="Database session error", operation="get_session", cause=e)

        finally:
            if session:
                await session.close()
                self._connection_pool_stats["active_connections"] -= 1

    def get_sync_session(self) -> Session:
        """Get sync database session"""
        return self.sync_session_factory()

    async def get_redis(self):
        """Get Redis client with connection validation"""
        if not self._initialized:
            await self.initialize()

        try:
            # Quick ping to validate connection
            await self.redis_client.ping()
            return self.redis_client

        except Exception as e:
            logger.warning(
                "Redis connection validation failed, attempting reconnection",
                extra={"error": str(e)},
            )

            # Attempt to recreate Redis connection
            try:
                await self.redis_client.close()
            except:
                pass

            # Reinitialize Redis connection
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
        """Gracefully close all database connections"""
        close_errors = []

        try:
            if self.async_engine:
                await self.async_engine.dispose()
                logger.debug("Async PostgreSQL engine disposed")
        except Exception as e:
            close_errors.append(f"Async engine: {str(e)}")
            logger.error("Error disposing async engine", extra={"error": str(e)})

        try:
            if self.sync_engine:
                self.sync_engine.dispose()
                logger.debug("Sync PostgreSQL engine disposed")
        except Exception as e:
            close_errors.append(f"Sync engine: {str(e)}")
            logger.error("Error disposing sync engine", extra={"error": str(e)})

        try:
            if self.redis_client:
                await self.redis_client.close()
                logger.debug("Redis client closed")
        except Exception as e:
            close_errors.append(f"Redis client: {str(e)}")
            logger.error("Error closing Redis client", extra={"error": str(e)})

        self._initialized = False

        if close_errors:
            logger.warning(
                "Database connections closed with errors", extra={"errors": close_errors}
            )
        else:
            logger.info("Database connections closed successfully")

    def _setup_pool_events(self, engine):
        """Setup connection pool event listeners for monitoring"""

        @event.listens_for(engine.sync_engine, "connect")
        def receive_connect(dbapi_connection, connection_record):
            logger.debug("New database connection established")
            self._connection_pool_stats["total_connections"] += 1

        @event.listens_for(engine.sync_engine, "checkout")
        def receive_checkout(dbapi_connection, connection_record, connection_proxy):
            self._connection_pool_stats["active_connections"] += 1

        @event.listens_for(engine.sync_engine, "checkin")
        def receive_checkin(dbapi_connection, connection_record):
            self._connection_pool_stats["active_connections"] -= 1

    async def execute_with_retry(self, operation: Callable[[], T], max_retries: int = 3) -> T:
        """Execute database operation with retry logic"""
        for attempt in range(max_retries):
            try:
                return await operation()
            except (OperationalError, DisconnectionError) as e:
                if attempt == max_retries - 1:
                    raise DatabaseError(
                        message=f"Database operation failed after {max_retries} attempts",
                        operation="execute_with_retry",
                        cause=e,
                    )

                wait_time = (2**attempt) * 0.5  # Exponential backoff
                logger.warning(
                    f"Database operation failed (attempt {attempt + 1}/{max_retries}), retrying in {wait_time}s",
                    extra={"error": str(e), "wait_time": wait_time},
                )
                await asyncio.sleep(wait_time)

        raise DatabaseError(
            message="Database operation failed after all retry attempts",
            operation="execute_with_retry",
        )

    async def health_check(self) -> dict[str, Any]:
        """Comprehensive database health check with metrics"""
        from datetime import datetime

        status = {
            "postgresql": {"status": False, "latency_ms": None, "pool_stats": None},
            "redis": {"status": False, "latency_ms": None, "memory_usage": None},
            "connection_stats": self._connection_pool_stats.copy(),
            "timestamp": datetime.utcnow().isoformat(),
        }

        # PostgreSQL health check with metrics
        try:
            start_time = time.time()
            async with self.async_engine.begin() as conn:
                await conn.execute(text("SELECT 1"))

                # Get pool statistics
                pool = self.async_engine.pool
                pool_stats = {
                    "size": pool.size(),
                    "checked_in": pool.checkedin(),
                    "checked_out": pool.checkedout(),
                    "overflow": pool.overflow(),
                    "invalid": pool.invalid(),
                }

            latency = (time.time() - start_time) * 1000
            status["postgresql"].update(
                {"status": True, "latency_ms": round(latency, 2), "pool_stats": pool_stats}
            )

        except Exception as e:
            logger.error("PostgreSQL health check failed", extra={"error": str(e)})
            status["postgresql"]["error"] = str(e)

        # Redis health check with metrics
        try:
            start_time = time.time()
            await self.redis_client.ping()

            # Get Redis info
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
            logger.error("Redis health check failed", extra={"error": str(e)})
            status["redis"]["error"] = str(e)

        return status


class CacheManager:
    """Enhanced Redis cache management with retry logic and monitoring"""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.default_ttl = settings.CACHE_TTL
        self._cache_stats = {"hits": 0, "misses": 0, "errors": 0, "total_operations": 0}

    @retry(
        stop=stop_after_attempt(CACHE_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=CACHE_RETRY_WAIT, max=2),
    )
    async def get(self, key: str) -> str | None:
        """Get value from cache with retry logic"""
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

            logger.error("Cache get operation failed", extra={"key": key, "error": str(e)})

            raise CacheError(
                message="Cache get operation failed", operation="get", details={"key": key}, cause=e
            )

    @retry(
        stop=stop_after_attempt(CACHE_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=CACHE_RETRY_WAIT, max=2),
    )
    async def set(self, key: str, value: str, ttl: int | None = None) -> bool:
        """Set value in cache with retry logic"""
        self._cache_stats["total_operations"] += 1

        try:
            redis_client = await self.db_manager.get_redis()
            ttl = ttl or self.default_ttl
            await redis_client.setex(key, ttl, value)
            return True

        except Exception as e:
            self._cache_stats["errors"] += 1

            logger.error(
                "Cache set operation failed", extra={"key": key, "ttl": ttl, "error": str(e)}
            )

            # For set operations, we might want to fail gracefully
            # depending on the use case
            return False

    async def delete(self, key: str) -> bool:
        """Delete value from cache"""
        try:
            redis_client = await self.db_manager.get_redis()
            result = await redis_client.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"Cache delete failed for key {key}: {str(e)}")
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        try:
            redis_client = await self.db_manager.get_redis()
            result = await redis_client.exists(key)
            return result > 0
        except Exception as e:
            logger.error(f"Cache exists check failed for key {key}: {str(e)}")
            return False

    async def get_json(self, key: str) -> dict[str, Any] | None:
        """Get JSON value from cache with proper error handling"""
        try:
            value = await self.get(key)
            if value:
                return json.loads(value)
            return None

        except json.JSONDecodeError as e:
            logger.warning(
                "Invalid JSON in cache", extra={"key": key, "value": value, "error": str(e)}
            )
            # Delete corrupted cache entry
            await self.delete(key)
            return None

        except Exception as e:
            logger.error("Cache get_json operation failed", extra={"key": key, "error": str(e)})
            return None

    async def set_json(self, key: str, value: dict[str, Any], ttl: int | None = None) -> bool:
        """Set JSON value in cache with validation"""
        try:
            # Validate that the value can be serialized
            json_value = json.dumps(value, ensure_ascii=False, default=str)
            return await self.set(key, json_value, ttl)

        except (TypeError, ValueError) as e:
            logger.error(
                "JSON serialization failed",
                extra={"key": key, "value_type": type(value), "error": str(e)},
            )
            return False

        except Exception as e:
            logger.error("Cache set_json operation failed", extra={"key": key, "error": str(e)})
            return False

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache performance statistics"""
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
        """Reset cache statistics"""
        self._cache_stats = {"hits": 0, "misses": 0, "errors": 0, "total_operations": 0}

    async def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern"""
        try:
            redis_client = await self.db_manager.get_redis()
            keys = await redis_client.keys(pattern)
            if keys:
                return await redis_client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Cache clear_pattern failed for pattern {pattern}: {str(e)}")
            return 0

    async def increment(self, key: str, amount: int = 1) -> int | None:
        """Increment counter"""
        try:
            redis_client = await self.db_manager.get_redis()
            return await redis_client.incrby(key, amount)
        except Exception as e:
            logger.error(f"Cache increment failed for key {key}: {str(e)}")
            return None

    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration for key"""
        try:
            redis_client = await self.db_manager.get_redis()
            return await redis_client.expire(key, ttl)
        except Exception as e:
            logger.error(f"Cache expire failed for key {key}: {str(e)}")
            return False


# Global database manager instance
db_manager = DatabaseManager()
cache_manager = CacheManager(db_manager)


# Database utilities for dependency injection
class DatabaseDependency:
    """Dependency injection helper for database operations"""

    @staticmethod
    async def get_session() -> AsyncGenerator[AsyncSession, None]:
        """Get database session for dependency injection"""
        async with db_manager.get_session() as session:
            yield session

    @staticmethod
    async def get_redis():
        """Get Redis client for dependency injection"""
        return await db_manager.get_redis()

    @staticmethod
    async def get_cache_manager():
        """Get cache manager for dependency injection"""
        return cache_manager


async def get_database_session():
    """FastAPI dependency for database session"""
    async with db_manager.get_session() as session:
        yield session


async def get_redis_client():
    """FastAPI dependency for Redis client"""
    return await db_manager.get_redis()


async def get_cache_manager():
    """FastAPI dependency for cache manager"""
    return cache_manager


# Enhanced database operations with transaction support


@asynccontextmanager
async def transaction() -> AsyncGenerator[AsyncSession, None]:
    """Database transaction context manager with automatic rollback"""
    async with db_manager.get_session() as session:
        try:
            await session.begin()
            yield session
            await session.commit()

        except Exception as e:
            await session.rollback()
            logger.error("Transaction rolled back due to error", extra={"error": str(e)})
            raise DatabaseError(message="Transaction failed", operation="transaction", cause=e)


async def execute_in_transaction(operation: Callable[[AsyncSession], T]) -> T:
    """Execute operation within a transaction"""
    async with transaction() as session:
        return await operation(session)


# Database initialization function for app startup
async def initialize_database():
    """Initialize database connections with comprehensive validation"""
    try:
        await db_manager.initialize()
        logger.info("Database initialization completed successfully")
    except Exception as e:
        logger.error("Database initialization failed", extra={"error": str(e)})
        raise


# Database cleanup function for app shutdown
async def cleanup_database():
    """Cleanup database connections"""
    await db_manager.close()


# Health check function
async def database_health_check():
    """Comprehensive database health check with metrics"""
    try:
        health_status = await db_manager.health_check()

        # Add cache statistics to health check
        health_status["cache_stats"] = cache_manager.get_cache_stats()

        return health_status

    except Exception as e:
        logger.error("Health check failed", extra={"error": str(e)})
        return {
            "postgresql": {"status": False, "error": str(e)},
            "redis": {"status": False, "error": str(e)},
            "timestamp": time.time(),
        }
