"""Graph manager — lifecycle, caching, incremental updates."""

from __future__ import annotations

import asyncio
import pickle
from datetime import datetime, timezone

import structlog

from meridian_shared.redis import RedisKeys, get_redis, get_redis_binary

from app.graph.builder import GraphBuilder

logger = structlog.get_logger()


class GraphManager:
    """Manages the asset graph lifecycle with Redis persistence and real-time updates."""

    def __init__(self) -> None:
        self.builder = GraphBuilder()
        self._update_task: asyncio.Task | None = None  # type: ignore[type-arg]
        self._rebuild_interval = 300  # Rebuild every 5 minutes

    async def initialize(self) -> None:
        """Initialize graph: load from cache or build fresh."""
        try:
            loaded = await self._load_from_cache()
            if not loaded:
                await self.rebuild()
        except Exception as e:
            logger.error("graph_initialization_error", error=str(e))
            # Provide empty graph fallback to ensure service health
            import networkx as nx
            self.builder.graph = nx.DiGraph()

        # Start background update listener
        self._update_task = asyncio.create_task(self._listen_for_updates())

        # Start periodic rebuild
        asyncio.create_task(self._periodic_rebuild())

        logger.info(
            "graph_manager_initialized",
            nodes=self.builder.graph.number_of_nodes(),
            edges=self.builder.graph.number_of_edges(),
        )

    async def shutdown(self) -> None:
        """Clean shutdown."""
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass

    async def rebuild(self) -> None:
        """Full graph rebuild from database."""
        logger.info("graph_rebuild_starting")
        try:
            await self.builder.build_full_graph()
            await self._save_to_cache()
            logger.info("graph_rebuild_complete")
        except Exception as e:
            logger.error("graph_rebuild_failed", error=str(e))

    async def _save_to_cache(self) -> None:
        """Serialize and save graph to Redis."""
        try:
            redis_bin = get_redis_binary()
            graph_bytes = pickle.dumps(self.builder.graph)
            await redis_bin.set(RedisKeys.GRAPH_DATA, graph_bytes, ex=3600)
            
            redis = get_redis()
            await redis.set(
                RedisKeys.GRAPH_METADATA,
                f'{{"nodes":{self.builder.graph.number_of_nodes()},"edges":{self.builder.graph.number_of_edges()},"updated_at":"{datetime.now(timezone.utc).isoformat()}"}}',
            )
            
            # Invalidate all route caches
            from app.pathfinding.cache import RouteCache
            await RouteCache.invalidate_all()
            
            logger.debug("graph_cached", size_bytes=len(graph_bytes))
        except Exception as e:
            logger.error("graph_cache_save_failed", error=str(e))

    async def _load_from_cache(self) -> bool:
        """Load graph from Redis cache."""
        try:
            redis_bin = get_redis_binary()
            graph_bytes = await redis_bin.get(RedisKeys.GRAPH_DATA)
            if graph_bytes:
                try:
                    self.builder.graph = pickle.loads(graph_bytes)  # noqa: S301
                    logger.info(
                        "graph_loaded_from_cache",
                        nodes=self.builder.graph.number_of_nodes(),
                        edges=self.builder.graph.number_of_edges(),
                    )
                    return True
                except Exception as e:
                    logger.warning("graph_cache_corruption_detected", error=str(e))
            return False
        except Exception as e:
            logger.warning("redis_unavailable_for_graph_load", error=str(e))
            return False

    async def _listen_for_updates(self) -> None:
        """Listen for Redis pub/sub events to trigger graph updates."""
        redis = get_redis()
        pubsub = redis.pubsub()
        await pubsub.subscribe(
            RedisKeys.CHANNEL_ORDERBOOK,
            RedisKeys.CHANNEL_POOL_UPDATE,
            RedisKeys.CHANNEL_TRADE,
        )

        update_count = 0
        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue

                update_count += 1

                # Batch updates: rebuild after N events
                if update_count >= 5:
                    await self.rebuild()
                    update_count = 0

        except asyncio.CancelledError:
            await pubsub.unsubscribe()
            raise

    async def _periodic_rebuild(self) -> None:
        """Periodically rebuild the full graph."""
        while True:
            try:
                await asyncio.sleep(self._rebuild_interval)
                await self.rebuild()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("periodic_rebuild_error", error=str(e))
                await asyncio.sleep(30)

    def find_paths(self, source_code: str, source_issuer: str | None, dest_code: str, dest_issuer: str | None, max_hops: int = 4, max_paths: int = 10) -> list[list[str]]:
        """Delegate path finding to builder."""
        return self.builder.find_paths(source_code, source_issuer, dest_code, dest_issuer, max_hops, max_paths)

    def get_stats(self) -> dict:
        """Get graph statistics."""
        return self.builder.get_stats()

    def get_node_info(self, node_id: str) -> dict | None:
        """Get node attributes."""
        if node_id in self.builder.graph:
            return dict(self.builder.graph.nodes[node_id])
        return None

    def get_neighbors(self, node_id: str) -> list[dict]:
        """Get node neighbors with edge data."""
        if node_id not in self.builder.graph:
            return []
        neighbors = []
        for neighbor in self.builder.graph.neighbors(node_id):
            edge_data = self.builder.graph[node_id][neighbor]
            node_data = self.builder.graph.nodes[neighbor]
            neighbors.append({
                "node_id": neighbor,
                "code": node_data.get("code"),
                "issuer": node_data.get("issuer"),
                "edge": edge_data,
            })
        return neighbors
