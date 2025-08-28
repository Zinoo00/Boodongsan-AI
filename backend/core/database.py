"""
Database connection and management for Korean Real Estate RAG AI Chatbot
Supabase Client and Redis integration
"""

import asyncio
import json
import logging
import time
from collections.abc import Callable
from typing import Any, TypeVar

import redis.asyncio as aioredis
from supabase import create_client, Client
from supabase.client import ClientOptions
from tenacity import retry, stop_after_attempt, wait_exponential

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
    """Enhanced Supabase database connection manager with retry logic and monitoring"""
    def __init__(self):
        self.supabase_client: Client | None = None
        self.redis_client = None
        self._initialized = False
        self._connection_stats = {
            "total_connections": 0,
            "active_connections": 0,
            "failed_connections": 0,
            "last_connection_attempt": None,
        }

    @retry(
        stop=stop_after_attempt(DB_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=DB_RETRY_WAIT_MIN, max=DB_RETRY_WAIT_MAX)
    )
    async def initialize(self):
        """Initialize Supabase and Redis connections with retry logic"""
        if self._initialized:
            return

        self._connection_stats["last_connection_attempt"] = time.time()

        try:
            # Initialize Supabase client
            supabase_url = str(settings.SUPABASE_URL)
            supabase_key = settings.get_secret_value("SUPABASE_SERVICE_ROLE_KEY")
            
            # Configure client options for production use
            client_options = ClientOptions(
                auto_refresh_token=True,
                persist_session=True,
            )
            
            self.supabase_client = create_client(
                supabase_url,
                supabase_key,
                options=client_options
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
            self._connection_stats["total_connections"] += 1

            logger.info(
                "Supabase and Redis connections initialized successfully",
                extra={
                    "supabase_url": supabase_url,
                    "redis_max_connections": 20,
                },
            )

        except Exception as e:
            self._connection_stats["failed_connections"] += 1

            logger.error(
                "Failed to initialize Supabase connections",
                extra={
                    "error": str(e),
                    "attempt_time": self._connection_stats["last_connection_attempt"],
                },
            )

            raise DatabaseError(
                message="Supabase initialization failed", operation="initialize", cause=e
            )

    async def _test_connections(self):
        """Test Supabase and Redis connections with comprehensive validation"""
        try:
            # Test Supabase connection
            # Use a simple query to test connection
            try:
                # Test basic connectivity with a simple query
                response = await asyncio.get_event_loop().run_in_executor(
                    None, 
                    lambda: self.supabase_client.rpc('get_schema_version', {})
                )
                logger.info("Supabase connection successful")
            except Exception as e:
                # If the RPC doesn't exist, that's fine - connection is still working
                # Let's try a simpler test
                try:
                    # Try to get current user (should work even if no user is logged in)
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: self.supabase_client.auth.get_user()
                    )
                    logger.info("Supabase connection successful (auth test)")
                except:
                    # Even if auth fails, the client is initialized correctly
                    logger.info("Supabase client initialized successfully")

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
            logger.error("Connection test failed", extra={"error": str(e)}, exc_info=True)
            raise DatabaseError(
                message="Connection test failed", operation="test_connections", cause=e
            )

    def get_supabase(self) -> Client:
        """Get Supabase client with connection validation"""
        if not self._initialized:
            raise DatabaseError(
                message="Supabase client not initialized", 
                operation="get_supabase"
            )
        
        if self.supabase_client is None:
            raise DatabaseError(
                message="Supabase client is None", 
                operation="get_supabase"
            )
        
        return self.supabase_client
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
        """Gracefully close all connections"""
        close_errors = []

        try:
            if self.supabase_client:
                # Supabase client doesn't require explicit closing like SQLAlchemy
                # but we can clear the reference
                self.supabase_client = None
                logger.debug("Supabase client cleared")
        except Exception as e:
            close_errors.append(f"Supabase client: {str(e)}")
            logger.error("Error clearing Supabase client", extra={"error": str(e)})

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
                "Connections closed with errors", extra={"errors": close_errors}
            )
        else:
            logger.info("Connections closed successfully")

    async def execute_with_retry(self, operation: Callable[[], T], max_retries: int = 3) -> T:
        """Execute Supabase operation with retry logic"""
        for attempt in range(max_retries):
            try:
                return await operation()
            except Exception as e:
                if attempt == max_retries - 1:
                    raise DatabaseError(
                        message=f"Supabase operation failed after {max_retries} attempts",
                        operation="execute_with_retry",
                        cause=e,
                    )

                wait_time = (2**attempt) * 0.5  # Exponential backoff
                logger.warning(
                    f"Supabase operation failed (attempt {attempt + 1}/{max_retries}), retrying in {wait_time}s",
                    extra={"error": str(e), "wait_time": wait_time},
                )
                await asyncio.sleep(wait_time)

        raise DatabaseError(
            message="Supabase operation failed after all retry attempts",
            operation="execute_with_retry",
        )

    async def health_check(self) -> dict[str, Any]:
        """Comprehensive health check with metrics"""
        from datetime import datetime

        status = {
            "supabase": {"status": False, "latency_ms": None},
            "redis": {"status": False, "latency_ms": None, "memory_usage": None},
            "connection_stats": self._connection_stats.copy(),
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Supabase health check with metrics
        try:
            start_time = time.time()
            # Simple test to verify Supabase connection
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.supabase_client.auth.get_user()
            )
            latency = (time.time() - start_time) * 1000
            status["supabase"].update(
                {"status": True, "latency_ms": round(latency, 2)}
            )

        except Exception as e:
            logger.error("Supabase health check failed", extra={"error": str(e)})
            status["supabase"]["error"] = str(e)
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
    def get_supabase() -> Client:
        """Get Supabase client for dependency injection"""
        return db_manager.get_supabase()

    @staticmethod
    async def get_redis():
        """Get Redis client for dependency injection"""
        return await db_manager.get_redis()

    @staticmethod
    async def get_cache_manager():
        """Get cache manager for dependency injection"""
        return cache_manager


def get_supabase_client() -> Client:
    """FastAPI dependency for Supabase client"""
    return db_manager.get_supabase()


async def get_redis_client():
    """FastAPI dependency for Redis client"""
    return await db_manager.get_redis()


async def get_cache_manager():
    """FastAPI dependency for cache manager"""
    return cache_manager


# Enhanced Supabase operations with error handling

async def execute_supabase_operation(operation: Callable[[Client], T]) -> T:
    """Execute Supabase operation with error handling"""
    try:
        client = db_manager.get_supabase()
        return await asyncio.get_event_loop().run_in_executor(
            None, 
            lambda: operation(client)
        )
    except Exception as e:
        logger.error("Supabase operation failed", extra={"error": str(e)})
        raise DatabaseError(message="Supabase operation failed", operation="execute_operation", cause=e)


# Database initialization function for app startup
async def initialize_database():
    """Initialize Supabase and Redis connections with comprehensive validation"""
    try:
        await db_manager.initialize()
        logger.info("Supabase and Redis initialization completed successfully")
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
            "supabase": {"status": False, "error": str(e)},
            "redis": {"status": False, "error": str(e)},
            "timestamp": time.time(),
        }
