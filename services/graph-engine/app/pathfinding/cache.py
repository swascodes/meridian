"""Redis caching for route discovery."""

from __future__ import annotations

import hashlib
import json

from meridian_shared.models import RouteDiscoverRequest, RouteDiscoverResponse
from meridian_shared.redis import get_redis


class RouteCache:
    """Handles caching of discovered routes."""

    @staticmethod
    def _generate_cache_key(request: RouteDiscoverRequest) -> str:
        """Generate a deterministic cache key for the request."""
        # Include source, dest, amount (rounded to 4 decimals), max hops, max routes
        raw = (
            f"{request.source_asset.code}:{request.source_asset.issuer or 'native'}_"
            f"{request.destination_asset.code}:{request.destination_asset.issuer or 'native'}_"
            f"{round(request.amount, 4)}_"
            f"{request.max_hops}_{request.max_routes}"
        )
        return "route_cache:" + hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    async def get_cached_routes(request: RouteDiscoverRequest) -> RouteDiscoverResponse | None:
        """Attempt to retrieve routes from cache."""
        try:
            redis = get_redis()
            key = RouteCache._generate_cache_key(request)
            data = await redis.get(key)
            if data:
                response_dict = json.loads(data)
                response_dict["cache_hit"] = True
                return RouteDiscoverResponse(**response_dict)
            return None
        except Exception:
            return None

    @staticmethod
    async def set_cached_routes(request: RouteDiscoverRequest, response: RouteDiscoverResponse, ttl: int = 60) -> None:
        """Cache discovered routes."""
        try:
            redis = get_redis()
            key = RouteCache._generate_cache_key(request)
            
            # Ensure cache_hit is false in stored representation
            response.cache_hit = False
            
            await redis.set(key, response.model_dump_json(), ex=ttl)
        except Exception:
            pass

    @staticmethod
    async def invalidate_all() -> None:
        """Invalidate all cached routes (called on graph rebuild)."""
        try:
            redis = get_redis()
            keys = await redis.keys("route_cache:*")
            if keys:
                await redis.delete(*keys)
        except Exception:
            pass
