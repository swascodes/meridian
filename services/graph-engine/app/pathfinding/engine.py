"""Core Pathfinding Engine Coordinator with execution intelligence."""

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

from app.execution.planner import ExecutionPlanner
from app.execution.risk import RiskEngine
from app.execution.simulator import ExecutionSimulator
from app.execution.validator import RouteValidator
from app.pathfinding.scoring import RouteScoringEngine
from app.pathfinding.simulation import RouteSimulationEngine
from app.pathfinding.strategies import DijkstraStrategy, YensStrategy


class PathfindingEngine:
    """Coordinates route discovery, simulation, scoring, and execution intelligence."""

    def __init__(self, graph: nx.DiGraph) -> None:
        self.graph = graph
        self.yens = YensStrategy()
        self.dijkstra = DijkstraStrategy()

    def _generate_route_hash(self, path: list[str]) -> str:
        """Generate deterministic hash for a specific path sequence."""
        return hashlib.sha256("-".join(path).encode()).hexdigest()

    def _build_pruned_graph(self, input_amount: float) -> nx.DiGraph:
        """Create a graph view removing edges with insufficient liquidity."""
        def filter_edge(u: str, v: str) -> bool:
            edge = self.graph[u][v]
            if "reserve_in" in edge:
                return float(edge["reserve_in"]) >= input_amount * 0.05
            if "bid_depth" in edge:
                return float(edge["bid_depth"]) >= input_amount * 0.05
            return True

        edges = [(u, v) for u, v, d in self.graph.edges(data=True) if filter_edge(u, v)]
        return self.graph.edge_subgraph(edges)

    def discover_routes(self, request: RouteDiscoverRequest) -> RouteDiscoverResponse:
        """Discover, simulate, score, and optionally validate/risk-assess routes."""
        start_time = time.perf_counter()

        # 1. Resolve nodes
        source_id = self._node_id(request.source_asset.code, request.source_asset.issuer)
        dest_id = self._node_id(request.destination_asset.code, request.destination_asset.issuer)

        if source_id not in self.graph or dest_id not in self.graph:
            return RouteDiscoverResponse(
                routes=[], latency_ms=self._elapsed(start_time),
                cache_hit=False, evaluated_paths_count=0
            )

        # 2. Prune Graph
        pruned_graph = self._build_pruned_graph(request.amount)
        if source_id not in pruned_graph or dest_id not in pruned_graph:
            return RouteDiscoverResponse(
                routes=[], latency_ms=self._elapsed(start_time),
                cache_hit=False, evaluated_paths_count=0
            )

        # 3. Discover Paths (Yen's K-Shortest)
        def weight_func(u: str, v: str, d: dict) -> float:
            return d.get("weight", 1.0)

        raw_paths = self.yens.find_paths(
            pruned_graph, source_id, dest_id,
            weight_func=weight_func,
            max_hops=request.max_hops * 2,
            max_paths=request.max_routes * 3,
        )

        routes = []

        # 4. Simulate, Score, and Enrich
        for path in raw_paths:
            # Basic simulation (existing engine)
            expected_output, slippage, fee_base, explanation, success = (
                RouteSimulationEngine.simulate_path(self.graph, path, request.amount)
            )

            if not success or slippage > 0.5:
                continue

            # Ideal output calculation
            ideal_output = self._ideal_output(path, request.amount)

            # Quality + confidence scores
            quality_score, confidence_score = RouteScoringEngine.calculate_scores(
                self.graph, path, expected_output, ideal_output, explanation
            )

            route_hash = self._generate_route_hash(path)

            # Format hops
            route_hops, actual_hop_count = self._format_hops(path)

            # --- Execution Intelligence (Phase 4) ---
            exec_validation = None
            exec_simulation = None
            exec_risk = None
            exec_plan = None
            execution_score = quality_score  # Default fallback

            # Detailed simulation (always run for execution_score)
            exec_simulation = ExecutionSimulator.simulate_execution(
                self.graph, path, request.amount
            )

            # Risk assessment
            exec_risk = RiskEngine.assess_risk(self.graph, path, exec_simulation)

            # Execution score = output * penalties
            execution_score = self._compute_execution_score(
                expected_output, request.amount, slippage, fee_base, exec_risk.risk_score
            )

            # Validation (optional)
            if request.validate_execution:
                exec_validation = RouteValidator.validate_route(
                    self.graph, path, request.amount
                )

            # Execution plan
            exec_plan = ExecutionPlanner.generate_plan(
                self.graph, path, request.amount, exec_simulation, route_hash
            )

            # If not requested, strip details from response
            if not request.simulate:
                exec_simulation = None
            if not request.risk_analysis:
                exec_risk_response = None
            else:
                exec_risk_response = exec_risk
            if not request.validate_execution:
                exec_validation = None

            routes.append(RouteResult(
                route_hash=route_hash,
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
                execution_score=execution_score,
                risk=exec_risk_response if request.risk_analysis else None,
                validation=exec_validation,
                simulation=exec_simulation,
                plan=exec_plan,
                explanation=explanation,
                discovered_at=datetime.now(timezone.utc),
            ))

        # 5. Sort by execution_score DESC
        routes.sort(key=lambda r: r.execution_score or 0.0, reverse=True)
        routes = routes[:request.max_routes]

        return RouteDiscoverResponse(
            routes=routes,
            latency_ms=self._elapsed(start_time),
            cache_hit=False,
            evaluated_paths_count=len(raw_paths),
        )

    def _compute_execution_score(
        self,
        expected_output: float,
        input_amount: float,
        slippage: float,
        fee: float,
        risk_score: float,
    ) -> float:
        """Compute composite execution score."""
        if input_amount <= 0:
            return 0.0

        # Normalized output (how much of input is preserved)
        output_ratio = expected_output / input_amount

        # Penalties (all 0-1 range, lower is better)
        slippage_penalty = max(0.0, 1.0 - slippage * 2.0)
        fee_penalty = max(0.0, 1.0 - (fee / input_amount) * 10.0) if input_amount > 0 else 0.0
        risk_penalty = max(0.0, 1.0 - risk_score)

        score = output_ratio * slippage_penalty * fee_penalty * risk_penalty
        return round(max(0.0, min(1.0, score)), 6)

    def _ideal_output(self, path: list[str], amount: float) -> float:
        """Calculate ideal theoretical output (zero fee, zero slippage)."""
        rate = 1.0
        for j in range(len(path) - 1):
            u, v = path[j], path[j + 1]
            edge = self.graph[u][v]
            if "reserve_in" in edge:
                rin = float(edge.get("reserve_in", 0))
                rout = float(edge.get("reserve_out", 0))
                spot = rout / rin if rin > 0 else 0
                rate *= spot
        return amount * rate

    def _format_hops(self, path: list[str]) -> tuple[list[RouteHop], int]:
        """Format path into RouteHop list."""
        route_hops = []
        actual_hop_count = 0
        i = 0
        while i < len(path) - 1:
            u, v = path[i], path[i + 1]
            if self.graph.nodes[v].get("node_type") == "pool":
                w = path[i + 2]
                target = self.graph.nodes[w]
                route_hops.append(RouteHop(
                    asset=AssetIdentifier(code=target.get("code", "XLM"), issuer=target.get("issuer")),
                    pool_id=self.graph.nodes[v].get("pool_id"),
                    hop_type="amm",
                ))
                i += 2
            else:
                target = self.graph.nodes[v]
                route_hops.append(RouteHop(
                    asset=AssetIdentifier(code=target.get("code", "XLM"), issuer=target.get("issuer")),
                    hop_type="orderbook",
                ))
                i += 1
            actual_hop_count += 1
        return route_hops, actual_hop_count

    @staticmethod
    def _node_id(code: str, issuer: str | None) -> str:
        raw = f"{code}:{issuer or 'native'}"
        return "asset:" + hashlib.sha256(raw.encode()).hexdigest()[:16]

    @staticmethod
    def _elapsed(start: float) -> int:
        return int((time.perf_counter() - start) * 1000)
