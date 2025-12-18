"""
Redis cache helper.

Redis 캐시 관리 및 in-memory fallback 제공.
"""

from __future__ import annotations

import fnmatch
import json
import logging
from datetime import datetime
from typing import Any

import redis.asyncio as aioredis
from redis.exceptions import ConnectionError as RedisConnectionError

from core.config import settings

logger = logging.getLogger(__name__)


class AsyncMemoryCache:
    """In-memory substitute for Redis used when a real instance is unavailable."""

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    async def ping(self) -> bool:
        return True

    async def get(self, key: str) -> str | None:
        value = self._store.get(key)
        return None if value is None else str(value)

    async def setex(self, key: str, _ttl: int, value: str) -> None:
        self._store[key] = value

    async def delete(self, key: str) -> int:
        return 1 if self._store.pop(key, None) is not None else 0

    async def keys(self, pattern: str) -> list[str]:
        return [key for key in self._store if fnmatch.fnmatch(key, pattern)]

    async def incrby(self, key: str, amount: int = 1) -> int:
        new_value = int(self._store.get(key, 0)) + amount
        self._store[key] = new_value
        return new_value

    async def expire(self, _key: str, _ttl: int) -> bool:
        return True

    async def close(self) -> None:  # pragma: no cover - nothing to close
        pass


class RedisManager:
    """Manage a single Redis connection."""

    def __init__(self) -> None:
        self._redis = None

    async def initialize(self) -> None:
        if self._redis:
            return

        try:
            self._redis = await aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                password=settings.REDIS_PASSWORD,
            )
            await self._redis.ping()
            logger.info("Connected to Redis at %s", settings.REDIS_URL)
        except (RedisConnectionError, OSError) as exc:
            logger.warning("Redis connection failed (%s). Falling back to in-memory cache.", exc)
            self._redis = AsyncMemoryCache()

    async def get_redis(self):
        if not self._redis:
            await self.initialize()
        return self._redis

    async def close(self) -> None:
        if self._redis:
            await self._redis.close()
            self._redis = None


class CacheManager:
    """JSON helpers on top of Redis."""

    def __init__(self, manager: RedisManager):
        self.manager = manager
        self.default_ttl = settings.CACHE_TTL

    async def get(self, key: str) -> str | None:
        client = await self.manager.get_redis()
        return await client.get(key)

    async def set(self, key: str, value: str, ttl: int | None = None) -> bool:
        client = await self.manager.get_redis()
        await client.setex(key, ttl or self.default_ttl, value)
        return True

    async def delete(self, key: str) -> int:
        client = await self.manager.get_redis()
        return await client.delete(key)

    async def get_json(self, key: str) -> dict[str, Any] | None:
        raw = await self.get(key)
        return json.loads(raw) if raw else None

    async def set_json(self, key: str, value: dict[str, Any], ttl: int | None = None) -> bool:
        return await self.set(key, json.dumps(value, ensure_ascii=False), ttl)


redis_manager = RedisManager()
cache_manager = CacheManager(redis_manager)


async def get_redis_client():
    return await redis_manager.get_redis()


async def get_cache_manager():
    return cache_manager


async def initialize_cache():
    """Initialize Redis/cache connection."""
    await redis_manager.initialize()


async def cleanup_cache():
    """Close Redis/cache connection."""
    await redis_manager.close()


async def cache_health_check() -> dict[str, Any]:
    """Check Redis/cache health."""
    client = await redis_manager.get_redis()
    alive = bool(await client.ping())
    return {
        "redis": {"status": alive, "url": settings.REDIS_URL},
        "timestamp": datetime.utcnow().isoformat(),
    }


# Backward compatibility aliases (deprecated - will be removed in future)
db_manager = redis_manager
DatabaseManager = RedisManager
AsyncMemoryRedis = AsyncMemoryCache
initialize_database = initialize_cache
cleanup_database = cleanup_cache
database_health_check = cache_health_check
