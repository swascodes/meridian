"""Multi-objective route optimization engine."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone

import structlog
import httpx

from meridian_shared.config import get_settings
from meridian_shared.models import AssetIdentifier, RouteHop, RouteResult

from app.optimizer.simulator import RouteSimulator

logger = structlog.get_logger()


@dataclass
class OptimizationObjective:
    """Weights for multi-objective optimization."""
    slippage_weight: float = 0.30
    liquidity_weight: float = 0.25
    hop_penalty_weight: float = 0.15
    spread_weight: float = 0.20
    reliability_weight: float = 0.10


@dataclass
class CandidateRoute:
    """A candidate route under evaluation."""
    path_nodes: list[dict] = field(default_factory=list)
    total_weight: float = 0.0
    estimated_slippage: float = 0.0
    total_liquidity: float = 0.0
    avg_spread: float = 0.0
    hop_count: int = 0
    composite_score: float = 0.0


class OptimizationEngine:
    """Multi-objective route optimizer."""

    def __init__(self, objectives: OptimizationObjective | None = None) -> None:
        self.objectives = objectives or OptimizationObjective()
        self.simulator = RouteSimulator()
        self.settings = get_settings()

    async def find_optimal_routes(
        self,
        source: AssetIdentifier,
        destination: AssetIdentifier,
        amount: float,
        max_hops: int = 4,
        max_results: int = 5,
    ) -> list[RouteResult]:
        """Find and rank optimal routes between two assets."""
        # 1. Get candidate paths from graph engine
        raw_paths = await self._fetch_paths(source, destination, max_hops)

        if not raw_paths:
            logger.info("no_paths_found", source=source.canonical, dest=destination.canonical)
            return []

        # 2. Evaluate each candidate
        candidates = []
        for raw_path in raw_paths:
            candidate = await self._evaluate_candidate(raw_path, amount)
            if candidate:
                candidates.append(candidate)

        # 3. Score and rank
        scored = self._score_candidates(candidates)

        # 4. Convert to RouteResult
        results = []
        for candidate in scored[:max_results]:
            route_hash = self._compute_route_hash(candidate)
            results.append(RouteResult(
                route_hash=route_hash,
                source_asset=source,
                destination_asset=destination,
                path=[
                    RouteHop(
                        asset=AssetIdentifier(
                            code=node.get("code", ""),
                            issuer=node.get("issuer"),
                        ),
                        hop_type=node.get("edge_type", "orderbook"),
                    )
                    for node in candidate.path_nodes
                ],
                hop_count=candidate.hop_count,
                estimated_rate=1.0 - candidate.estimated_slippage,
                estimated_slippage=candidate.estimated_slippage,
                total_liquidity=candidate.total_liquidity,
                quality_score=candidate.composite_score,
                discovered_at=datetime.now(timezone.utc),
            ))

        logger.info(
            "routes_optimized",
            source=source.canonical,
            dest=destination.canonical,
            candidates=len(candidates),
            results=len(results),
        )
        return results

    async def _fetch_paths(self, source: AssetIdentifier, dest: AssetIdentifier, max_hops: int) -> list[list[dict]]:
        """Fetch candidate paths from graph engine."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.settings.graph_engine_url}/v1/graph/paths/{source.canonical}/{dest.canonical}",
                    params={"max_hops": max_hops, "max_paths": 20},
                )
                response.raise_for_status()
                data = response.json()
                return data.get("paths", [])
        except Exception as e:
            logger.error("graph_engine_fetch_error", error=str(e))
            return []

    async def _evaluate_candidate(self, raw_path: list[dict], amount: float) -> CandidateRoute | None:
        """Evaluate a single candidate route."""
        try:
            candidate = CandidateRoute(
                path_nodes=raw_path,
                hop_count=len(raw_path) - 1,
            )

            # Simulate execution
            sim_result = await self.simulator.simulate(raw_path, amount)
            candidate.estimated_slippage = sim_result.get("slippage", 0.05)
            candidate.total_liquidity = sim_result.get("total_liquidity", 0)
            candidate.avg_spread = sim_result.get("avg_spread", 0)
            candidate.total_weight = sim_result.get("total_weight", 1.0)

            return candidate
        except Exception as e:
            logger.warning("candidate_evaluation_error", error=str(e))
            return None

    def _score_candidates(self, candidates: list[CandidateRoute]) -> list[CandidateRoute]:
        """Score and rank candidates using multi-objective function."""
        if not candidates:
            return []

        # Normalize metrics
        max_liquidity = max(c.total_liquidity for c in candidates) or 1.0
        max_slippage = max(c.estimated_slippage for c in candidates) or 1.0
        max_spread = max(c.avg_spread for c in candidates) or 1.0
        max_hops = max(c.hop_count for c in candidates) or 1

        obj = self.objectives

        for c in candidates:
            slippage_score = 1.0 - (c.estimated_slippage / max_slippage)
            liquidity_score = c.total_liquidity / max_liquidity
            hop_score = 1.0 - (c.hop_count / (max_hops + 1))
            spread_score = 1.0 - (c.avg_spread / max_spread) if max_spread > 0 else 1.0

            c.composite_score = (
                obj.slippage_weight * slippage_score
                + obj.liquidity_weight * liquidity_score
                + obj.hop_penalty_weight * hop_score
                + obj.spread_weight * spread_score
            )

        candidates.sort(key=lambda c: c.composite_score, reverse=True)
        return candidates

    @staticmethod
    def _compute_route_hash(candidate: CandidateRoute) -> str:
        """Deterministic route hash from path nodes."""
        path_str = "|".join(
            f"{n.get('code', '')}:{n.get('issuer', 'native')}" for n in candidate.path_nodes
        )
        return hashlib.sha256(path_str.encode()).hexdigest()[:16]
