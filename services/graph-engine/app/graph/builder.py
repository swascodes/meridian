"""Graph builder — constructs NetworkX graph from Stellar data."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import networkx as nx
import structlog
from sqlalchemy import select, func

from meridian_shared.db import Asset, LiquidityPool, OrderbookSnapshot, get_session

logger = structlog.get_logger()


class GraphBuilder:
    """Builds a weighted directed graph of Stellar asset relationships."""

    def __init__(self) -> None:
        self.graph = nx.DiGraph()

    async def build_full_graph(self) -> nx.DiGraph:
        """Build complete graph from current database state."""
        logger.info("graph_build_starting")
        new_graph = nx.DiGraph()

        await self._add_asset_nodes(new_graph)
        await self._add_orderbook_edges(new_graph)
        await self._add_pool_edges(new_graph)

        self.graph = new_graph

        logger.info(
            "graph_build_complete",
            nodes=self.graph.number_of_nodes(),
            edges=self.graph.number_of_edges(),
        )
        return self.graph

    async def _add_asset_nodes(self, graph: nx.DiGraph) -> None:
        """Add all known assets as graph nodes."""
        async with get_session() as session:
            stmt = select(Asset)
            result = await session.execute(stmt)
            assets = result.scalars().all()

            node_count = 0
            for asset in assets:
                node_id = self._asset_node_id(asset.code, asset.issuer)
                graph.add_node(
                    node_id,
                    node_type="asset",
                    asset_id=str(asset.id),
                    code=asset.code,
                    issuer=asset.issuer,
                    domain=asset.domain,
                    trustlines=asset.total_trustlines,
                    volume_24h=asset.total_volume_24h,
                    is_verified=asset.is_verified,
                )
                node_count += 1

        logger.debug("graph_nodes_added", count=node_count)

    async def _add_orderbook_edges(self, graph: nx.DiGraph) -> None:
        """Add edges from active orderbook snapshots."""
        async with get_session() as session:
            # Get latest snapshot per pair using a subquery
            subq = (
                select(
                    OrderbookSnapshot.base_asset_id,
                    OrderbookSnapshot.counter_asset_id,
                    func.max(OrderbookSnapshot.timestamp).label("max_ts"),
                )
                .group_by(OrderbookSnapshot.base_asset_id, OrderbookSnapshot.counter_asset_id)
                .subquery()
            )

            stmt = (
                select(OrderbookSnapshot)
                .join(
                    subq,
                    (OrderbookSnapshot.base_asset_id == subq.c.base_asset_id)
                    & (OrderbookSnapshot.counter_asset_id == subq.c.counter_asset_id)
                    & (OrderbookSnapshot.timestamp == subq.c.max_ts),
                )
            )
            result = await session.execute(stmt)
            snapshots = result.scalars().all()

            edge_count = 0
            for snap in snapshots:
                base_node = self._asset_node_id(snap.base_asset.code, snap.base_asset.issuer)
                counter_node = self._asset_node_id(snap.counter_asset.code, snap.counter_asset.issuer)

                if base_node not in graph or counter_node not in graph:
                    continue

                # Bidirectional edges
                weight = self._calculate_orderbook_weight(snap)

                graph.add_edge(
                    base_node,
                    counter_node,
                    weight=weight,
                    edge_type="orderbook",
                    spread=float(snap.spread),
                    bid_depth=float(snap.bid_depth),
                    ask_depth=float(snap.ask_depth),
                    mid_price=snap.mid_price,
                    timestamp=snap.timestamp.isoformat(),
                )

                graph.add_edge(
                    counter_node,
                    base_node,
                    weight=weight,
                    edge_type="orderbook",
                    spread=float(snap.spread),
                    bid_depth=float(snap.ask_depth),
                    ask_depth=float(snap.bid_depth),
                    mid_price=1.0 / snap.mid_price if snap.mid_price > 0 else 0,
                    timestamp=snap.timestamp.isoformat(),
                )
                edge_count += 2

        logger.debug("orderbook_edges_added", count=edge_count)

    async def _add_pool_edges(self, graph: nx.DiGraph) -> None:
        """Add edges from AMM liquidity pools."""
        async with get_session() as session:
            stmt = select(LiquidityPool)
            result = await session.execute(stmt)
            pools = result.scalars().all()

            edge_count = 0
            for pool in pools:
                node_a = self._asset_node_id(pool.asset_a.code, pool.asset_a.issuer)
                node_b = self._asset_node_id(pool.asset_b.code, pool.asset_b.issuer)

                if node_a not in graph or node_b not in graph:
                    continue

                pool_node_id = f"pool:{pool.pool_id}"
                graph.add_node(
                    pool_node_id,
                    node_type="pool",
                    pool_id=pool.pool_id,
                    reserve_a=float(pool.reserve_a),
                    reserve_b=float(pool.reserve_b),
                    total_shares=float(pool.total_shares),
                    fee_bp=pool.fee_bp,
                    timestamp=pool.last_updated_at.isoformat(),
                )

                weight = self._calculate_pool_weight(pool) / 2.0

                edge_attrs = {
                    "weight": weight,
                    "edge_type": "pool_hop",
                    "pool_id": pool.pool_id,
                    "fee_bp": pool.fee_bp,
                    "timestamp": pool.last_updated_at.isoformat(),
                }

                # Asset A -> Pool -> Asset B
                graph.add_edge(node_a, pool_node_id, **edge_attrs, reserve_in=float(pool.reserve_a), reserve_out=float(pool.reserve_b))
                graph.add_edge(pool_node_id, node_b, **edge_attrs, reserve_in=float(pool.reserve_a), reserve_out=float(pool.reserve_b))

                # Asset B -> Pool -> Asset A
                graph.add_edge(node_b, pool_node_id, **edge_attrs, reserve_in=float(pool.reserve_b), reserve_out=float(pool.reserve_a))
                graph.add_edge(pool_node_id, node_a, **edge_attrs, reserve_in=float(pool.reserve_b), reserve_out=float(pool.reserve_a))

                edge_count += 4

        logger.debug("pool_edges_added", count=edge_count)

    def _calculate_orderbook_weight(self, snapshot: OrderbookSnapshot) -> float:
        """Calculate edge weight from orderbook state.

        Lower weight = better route.
        Factors: spread (lower is better), depth (higher is better).
        """
        spread_penalty = float(snapshot.spread) * 100  # Scale spread to meaningful range
        depth_bonus = 1.0 / (1.0 + float(snapshot.bid_depth) + float(snapshot.ask_depth))
        return max(0.001, spread_penalty + depth_bonus)

    def _calculate_pool_weight(self, pool: LiquidityPool) -> float:
        """Calculate edge weight from AMM pool state.

        Lower weight = better route.
        Higher reserves = lower weight.
        """
        total_liquidity = float(pool.reserve_a) + float(pool.reserve_b)
        fee_factor = pool.fee_bp / 10000.0
        return max(0.001, fee_factor + 1.0 / (1.0 + total_liquidity))

    @staticmethod
    def _asset_node_id(code: str, issuer: str | None) -> str:
        """Generate deterministic node ID for an asset."""
        raw = f"{code}:{issuer or 'native'}"
        return "asset:" + hashlib.sha256(raw.encode()).hexdigest()[:16]

    def find_paths(
        self,
        source_code: str,
        source_issuer: str | None,
        dest_code: str,
        dest_issuer: str | None,
        max_hops: int = 4,
        max_paths: int = 10,
    ) -> list[list[str]]:
        """Find all simple paths between two assets."""
        source = self._asset_node_id(source_code, source_issuer)
        dest = self._asset_node_id(dest_code, dest_issuer)

        if source not in self.graph or dest not in self.graph:
            return []

        try:
            paths = list(nx.shortest_simple_paths(self.graph, source, dest, weight="weight"))
            return [p for p in paths[:max_paths] if len(p) - 1 <= max_hops]
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []

    def get_stats(self) -> dict:
        """Get graph topology statistics."""
        asset_count = sum(1 for _, d in self.graph.nodes(data=True) if d.get("node_type") == "asset")
        pool_count = sum(1 for _, d in self.graph.nodes(data=True) if d.get("node_type") == "pool")
        
        return {
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "total_assets": asset_count,
            "total_pools": pool_count,
            "avg_degree": sum(d for _, d in self.graph.degree()) / max(self.graph.number_of_nodes(), 1),
            "density": nx.density(self.graph),
            "connected_components": nx.number_weakly_connected_components(self.graph),
            "last_updated_at": datetime.now(timezone.utc).isoformat(),
        }
