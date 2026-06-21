"""Redis client wrapper with connection pooling and pub/sub."""

from __future__ import annotations

import redis.asyncio as redis
from redis.asyncio import ConnectionPool, Redis

from meridian_shared.config import get_settings

_pool: ConnectionPool | None = None
_binary_pool: ConnectionPool | None = None


def get_redis_pool() -> ConnectionPool:
    """Get or create the Redis connection pool."""
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = ConnectionPool.from_url(
            str(settings.redis_url),
            max_connections=settings.redis_max_connections,
            decode_responses=True,
        )
    return _pool


def get_redis() -> Redis:  # type: ignore[type-arg]
    """Get a Redis client from the pool (decodes responses as UTF-8)."""
    return Redis(connection_pool=get_redis_pool())


def get_redis_binary_pool() -> ConnectionPool:
    """Get or create a Redis connection pool for binary data."""
    global _binary_pool
    if _binary_pool is None:
        settings = get_settings()
        _binary_pool = ConnectionPool.from_url(
            str(settings.redis_url),
            max_connections=settings.redis_max_connections,
            decode_responses=False,
        )
    return _binary_pool


def get_redis_binary() -> Redis:  # type: ignore[type-arg]
    """Get a Redis client from the binary pool (returns raw bytes)."""
    return Redis(connection_pool=get_redis_binary_pool())


async def close_redis() -> None:
    """Close the Redis connection pool."""
    global _pool, _binary_pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None
    if _binary_pool is not None:
        await _binary_pool.aclose()
        _binary_pool = None


class RedisKeys:
    """Centralized Redis key namespace."""

    # Graph
    GRAPH_DATA = "meridian:graph:data"
    GRAPH_METADATA = "meridian:graph:metadata"
    GRAPH_LOCK = "meridian:graph:lock"

    # Orderbook cache
    ORDERBOOK_PREFIX = "meridian:orderbook:"

    # Route cache
    ROUTE_CACHE_PREFIX = "meridian:route:"
    ROUTE_QUALITY_PREFIX = "meridian:quality:"

    # Pub/Sub channels
    CHANNEL_GRAPH_UPDATE = "meridian:channel:graph_update"
    CHANNEL_TRADE = "meridian:channel:trade"
    CHANNEL_ORDERBOOK = "meridian:channel:orderbook"
    CHANNEL_POOL_UPDATE = "meridian:channel:pool_update"

    # Ingestion
    INGESTION_STATUS = "meridian:ingestion:status"

    @staticmethod
    def orderbook(base_code: str, counter_code: str) -> str:
        return f"meridian:orderbook:{base_code}:{counter_code}"

    @staticmethod
    def route_cache(source: str, dest: str) -> str:
        return f"meridian:route:{source}:{dest}"

    @staticmethod
    def route_quality(route_hash: str) -> str:
        return f"meridian:quality:{route_hash}"
