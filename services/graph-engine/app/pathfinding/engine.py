"""Core Pathfinding Engine Coordinator."""

from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone

import networkx as nx

from meridian_shared.models import (
    AssetIdentifier,
    RouteDiscoverRequest,
    RouteDiscoverResponse,
    RouteHop,
    RouteResult,
)
from meridian_shared.stellar import parse_asset_identifier

from app.pathfinding.scoring import RouteScoringEngine
from app.pathfinding.simulation import RouteSimulationEngine
from app.pathfinding.strategies import DijkstraStrategy, YensStrategy


class PathfindingEngine:
    """Coordinates route discovery, simulation, and scoring."""

    def __init__(self, graph: nx.DiGraph) -> None:
        self.graph = graph
        self.yens = YensStrategy()
        self.dijkstra = DijkstraStrategy()

    def _generate_route_hash(self, path: list[str]) -> str:
        """Generate deterministic hash for a specific path sequence."""
        return hashlib.sha256("-".join(path).encode()).hexdigest()

    def _build_pruned_graph(self, input_amount: float) -> nx.DiGraph:
        """Create a graph view removing edges with insufficient liquidity."""
        # For simplicity and performance, we use an edge subgraph view
        # We only keep edges where capacity is >= input_amount
        def filter_edge(u: str, v: str) -> bool:
            edge = self.graph[u][v]
            # Pool
            if "reserve_in" in edge:
                return float(edge["reserve_in"]) >= input_amount * 0.05  # Allow some slippage room
            # Orderbook
            if "bid_depth" in edge:
                return float(edge["bid_depth"]) >= input_amount * 0.05
            return True

        # NetworkX edge subgraph view is O(1) creation
        edges = [(u, v) for u, v, d in self.graph.edges(data=True) if filter_edge(u, v)]
        return self.graph.edge_subgraph(edges)

    def _format_route_hop(self, u: str, v: str) -> RouteHop:
        """Format a graph edge into a RouteHop model."""
        target_node = self.graph.nodes[v]
        
        if target_node.get("node_type") == "pool":
            return RouteHop(
                asset=AssetIdentifier(code="POOL", issuer="AMM"), # Placeholder, actual asset is next hop
                pool_id=target_node.get("pool_id"),
                hop_type="amm"
            )
            
        return RouteHop(
            asset=AssetIdentifier(
                code=target_node.get("code", "XLM"),
                issuer=target_node.get("issuer")
            ),
            hop_type="orderbook"
        )

    def discover_routes(self, request: RouteDiscoverRequest) -> RouteDiscoverResponse:
        """Discover, simulate, and score top optimal routes."""
        start_time = time.perf_counter()
        
        # 1. Resolve nodes
        source_id = "asset:" + hashlib.sha256(f"{request.source_asset.code}:{request.source_asset.issuer or 'native'}".encode()).hexdigest()[:16]
        dest_id = "asset:" + hashlib.sha256(f"{request.destination_asset.code}:{request.destination_asset.issuer or 'native'}".encode()).hexdigest()[:16]
        
        if source_id not in self.graph or dest_id not in self.graph:
            return RouteDiscoverResponse(routes=[], latency_ms=int((time.perf_counter() - start_time) * 1000), cache_hit=False, evaluated_paths_count=0)

        # 2. Prune Graph for Feasibility
        pruned_graph = self._build_pruned_graph(request.amount)
        
        if source_id not in pruned_graph or dest_id not in pruned_graph:
            return RouteDiscoverResponse(routes=[], latency_ms=int((time.perf_counter() - start_time) * 1000), cache_hit=False, evaluated_paths_count=0)
        
        # 3. Discover Paths (Yen's K-Shortest)
        # Using the base weight function which is 1.0 / liquidity + fee
        def weight_func(u: str, v: str, d: dict) -> float:
            return d.get("weight", 1.0)
            
        raw_paths = self.yens.find_paths(
            pruned_graph,
            source_id,
            dest_id,
            weight_func=weight_func,
            max_hops=request.max_hops * 2, # Multiply by 2 because pool hops take 2 edges
            max_paths=request.max_routes * 3 # Fetch more to allow simulation pruning
        )

        routes = []
        
        # 4. Simulate and Score
        for path in raw_paths:
            expected_output, slippage, fee_base, explanation, success = RouteSimulationEngine.simulate_path(
                self.graph, path, request.amount
            )
            
            if not success or slippage > 0.5: # Reject >50% slippage
                continue
                
            # Calculate ideal theoretical output (0 fee 0 slippage)
            path_expected_rate = 1.0
            for i in range(len(path) - 1):
                u, v = path[i], path[i+1]
                if "reserve_in" in self.graph[u][v]:
                    rin = self.graph[u][v].get("reserve_in", 0)
                    rout = self.graph[u][v].get("reserve_out", 0)
                    spot = rout / rin if rin > 0 else 0
                    path_expected_rate *= spot
                    
            ideal_output = request.amount * path_expected_rate
                
            quality_score, confidence_score = RouteScoringEngine.calculate_scores(
                self.graph, path, expected_output, ideal_output, explanation
            )
            
            # Format Route Result
            route_hops = []
            actual_hop_count = 0
            
            i = 0
            while i < len(path) - 1:
                u, v = path[i], path[i+1]
                if self.graph.nodes[v].get("node_type") == "pool":
                    # It's an AMM. The hop target asset is path[i+2]
                    w = path[i+2]
                    target_asset = self.graph.nodes[w]
                    route_hops.append(RouteHop(
                        asset=AssetIdentifier(code=target_asset.get("code", "XLM"), issuer=target_asset.get("issuer")),
                        pool_id=self.graph.nodes[v].get("pool_id"),
                        hop_type="amm"
                    ))
                    i += 2
                    actual_hop_count += 1
                else:
                    target_asset = self.graph.nodes[v]
                    route_hops.append(RouteHop(
                        asset=AssetIdentifier(code=target_asset.get("code", "XLM"), issuer=target_asset.get("issuer")),
                        hop_type="orderbook"
                    ))
                    i += 1
                    actual_hop_count += 1
            
            routes.append(RouteResult(
                route_hash=self._generate_route_hash(path),
                source_asset=request.source_asset,
                destination_asset=request.destination_asset,
                path=route_hops,
                hop_count=actual_hop_count,
                expected_output=expected_output,
                estimated_rate=expected_output / request.amount if request.amount > 0 else 0.0,
                estimated_slippage=slippage,
                estimated_fee=fee_base,
                total_liquidity=explanation.bottleneck_liquidity or 0.0,
                quality_score=quality_score,
                confidence_score=confidence_score,
                explanation=explanation,
                discovered_at=datetime.now(timezone.utc)
            ))
            
        # 5. Sort by Quality Score (descending)
        routes.sort(key=lambda r: r.quality_score or 0.0, reverse=True)
        
        # Take Top K
        routes = routes[:request.max_routes]
        
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        
        return RouteDiscoverResponse(
            routes=routes,
            latency_ms=latency_ms,
            cache_hit=False,
            evaluated_paths_count=len(raw_paths)
        )
