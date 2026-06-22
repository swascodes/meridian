"""Route discovery API endpoints with execution intelligence."""

from __future__ import annotations

import hashlib

from fastapi import APIRouter, HTTPException, Request
import networkx as nx

from meridian_shared.models import (
    CacheStats,
    RouteDiscoverRequest,
    RouteDiscoverResponse,
    RouteExplainResponse,
    RouteValidateRequest,
)
from app.execution.planner import ExecutionPlanner
from app.execution.risk import RiskEngine
from app.execution.simulator import ExecutionSimulator
from app.execution.validator import RouteValidator
from app.pathfinding.cache import RouteCache
from app.pathfinding.engine import PathfindingEngine

router = APIRouter()

# In-memory store for recently discovered routes (for explain endpoint)
_route_store: dict[str, dict] = {}

# Observability counters
_metrics: dict[str, int | float] = {
    "routes_discovered_total": 0,
    "routes_validated_total": 0,
    "route_validation_failures": 0,
    "simulation_runs_total": 0,
    "average_execution_score": 0.0,
    "cache_hits": 0,
    "cache_misses": 0,
}


@router.post("/discover", response_model=RouteDiscoverResponse)
async def discover_routes(request: Request, payload: RouteDiscoverRequest) -> RouteDiscoverResponse:
    """Discover optimal risk-adjusted routes for an asset conversion."""
    # 1. Check Cache
    cached = await RouteCache.get_cached_routes(payload)
    if cached:
        _metrics["cache_hits"] += 1
        return cached

    _metrics["cache_misses"] += 1

    # 2. Get Graph
    manager = request.app.state.graph_manager
    graph = manager.builder.graph

    if graph.number_of_nodes() == 0:
        raise HTTPException(status_code=503, detail="Graph engine is still initializing.")

    # 3. Pathfinding Engine
    engine = PathfindingEngine(graph)
    response = engine.discover_routes(payload)

    # 4. Track metrics
    _metrics["routes_discovered_total"] += len(response.routes)
    if response.routes:
        scores = [r.execution_score for r in response.routes if r.execution_score is not None]
        if scores:
            _metrics["average_execution_score"] = sum(scores) / len(scores)

    # 5. Store routes for explain endpoint
    for route in response.routes:
        _route_store[route.route_hash] = route.model_dump(mode="json")
        # Keep store bounded
        if len(_route_store) > 1000:
            oldest = next(iter(_route_store))
            del _route_store[oldest]

    # 6. Cache and Return
    if response.routes:
        await RouteCache.set_cached_routes(payload, response)

    return response


@router.post("/validate")
async def validate_route(request: Request, payload: RouteValidateRequest) -> dict:
    """Validate a route for execution readiness."""
    _metrics["routes_validated_total"] += 1

    manager = request.app.state.graph_manager
    graph = manager.builder.graph

    if graph.number_of_nodes() == 0:
        raise HTTPException(status_code=503, detail="Graph engine is still initializing.")

    engine = PathfindingEngine(graph)

    # Discover the best path first
    from meridian_shared.models import RouteDiscoverRequest as DR, AssetIdentifier
    dr = DR(
        source_asset=payload.source_asset,
        destination_asset=payload.destination_asset,
        amount=payload.amount,
        max_hops=payload.max_hops,
        max_routes=1,
    )
    response = engine.discover_routes(dr)

    if not response.routes:
        _metrics["route_validation_failures"] += 1
        return {"valid": False, "reason": "No path found between assets"}

    # Re-discover raw path for validation
    source_id = engine._node_id(payload.source_asset.code, payload.source_asset.issuer)
    dest_id = engine._node_id(payload.destination_asset.code, payload.destination_asset.issuer)

    try:
        path = nx.shortest_path(graph, source_id, dest_id, weight="weight")
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        _metrics["route_validation_failures"] += 1
        return {"valid": False, "reason": "No path exists in graph"}

    validation = RouteValidator.validate_route(graph, path, payload.amount)
    if not validation.valid:
        _metrics["route_validation_failures"] += 1

    return validation.model_dump(mode="json")


@router.post("/simulate")
async def simulate_route(request: Request, payload: RouteValidateRequest) -> dict:
    """Run standalone execution simulation."""
    _metrics["simulation_runs_total"] += 1

    manager = request.app.state.graph_manager
    graph = manager.builder.graph

    if graph.number_of_nodes() == 0:
        raise HTTPException(status_code=503, detail="Graph engine is still initializing.")

    engine = PathfindingEngine(graph)
    source_id = engine._node_id(payload.source_asset.code, payload.source_asset.issuer)
    dest_id = engine._node_id(payload.destination_asset.code, payload.destination_asset.issuer)

    try:
        path = nx.shortest_path(graph, source_id, dest_id, weight="weight")
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        raise HTTPException(status_code=404, detail="No path exists between assets")

    simulation = ExecutionSimulator.simulate_execution(graph, path, payload.amount)
    risk = RiskEngine.assess_risk(graph, path, simulation)
    plan = ExecutionPlanner.generate_plan(
        graph, path, payload.amount, simulation,
        hashlib.sha256("-".join(path).encode()).hexdigest()
    )

    return {
        "simulation": simulation.model_dump(mode="json"),
        "risk": risk.model_dump(mode="json"),
        "plan": plan.model_dump(mode="json"),
    }


@router.get("/explain/{route_hash}")
async def explain_route(route_hash: str) -> dict:
    """Explain why a route was selected."""
    if route_hash not in _route_store:
        raise HTTPException(status_code=404, detail="Route not found in recent cache. Discover routes first.")

    return _route_store[route_hash]


@router.get("/cache/stats", response_model=CacheStats)
async def cache_stats() -> CacheStats:
    """Get route cache statistics."""
    from meridian_shared.redis import get_redis

    redis = get_redis()
    keys = await redis.keys("route_cache:*")
    entries = len(keys) if keys else 0

    total_requests = _metrics.get("cache_hits", 0) + _metrics.get("cache_misses", 0)
    hit_rate = _metrics.get("cache_hits", 0) / total_requests if total_requests > 0 else 0.0

    return CacheStats(
        entries=entries,
        hit_rate=round(hit_rate, 4),
        evictions=0,  # Redis handles eviction, we don't track it
        ttl_seconds=60,
    )


@router.get("/debug")
async def debug_route(
    request: Request,
    source_code: str,
    dest_code: str,
    source_issuer: str | None = None,
    dest_issuer: str | None = None,
) -> dict:
    """Debug why a route is failing."""
    manager = request.app.state.graph_manager
    graph = manager.builder.graph

    def _node_id(code: str, issuer: str | None) -> str:
        raw = f"{code}:{issuer or 'native'}"
        return "asset:" + hashlib.sha256(raw.encode()).hexdigest()[:16]

    source_id = _node_id(source_code, source_issuer)
    dest_id = _node_id(dest_code, dest_issuer)

    source_exists = source_id in graph
    dest_exists = dest_id in graph

    source_degree = graph.degree(source_id) if source_exists else 0
    dest_degree = graph.degree(dest_id) if dest_exists else 0

    reachable = len(nx.descendants(graph, source_id)) if source_exists else 0
    components = nx.number_weakly_connected_components(graph) if graph.number_of_nodes() > 0 else 0

    path_exists = False
    if source_exists and dest_exists:
        path_exists = nx.has_path(graph, source_id, dest_id)

    mismatch = []
    if not source_exists:
        mismatch.append(f"Source missing: {source_id}")
    if not dest_exists:
        mismatch.append(f"Destination missing: {dest_id}")

    return {
        "source_id_generated": source_id,
        "dest_id_generated": dest_id,
        "source_exists": source_exists,
        "destination_exists": dest_exists,
        "source_degree": source_degree,
        "destination_degree": dest_degree,
        "connected_components": components,
        "reachable_nodes": reachable,
        "path_exists": path_exists,
        "mismatch": mismatch,
    }


@router.get("/metrics")
async def route_metrics() -> dict:
    """Observability metrics for route operations."""
    return dict(_metrics)
