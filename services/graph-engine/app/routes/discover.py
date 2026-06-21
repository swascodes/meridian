"""Route discovery API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from meridian_shared.models import RouteDiscoverRequest, RouteDiscoverResponse
from app.pathfinding.cache import RouteCache
from app.pathfinding.engine import PathfindingEngine

router = APIRouter()


@router.post("/discover", response_model=RouteDiscoverResponse)
async def discover_routes(request: Request, payload: RouteDiscoverRequest) -> RouteDiscoverResponse:
    """Discover optimal risk-adjusted routes for an asset conversion."""
    # 1. Check Cache
    cached = await RouteCache.get_cached_routes(payload)
    if cached:
        return cached

    # 2. Get Graph
    manager = request.app.state.graph_manager
    graph = manager.builder.graph
    
    if graph.number_of_nodes() == 0:
        raise HTTPException(status_code=503, detail="Graph engine is still initializing.")

    # 3. Pathfinding Engine
    engine = PathfindingEngine(graph)
    response = engine.discover_routes(payload)
    
    # 4. Cache and Return
    if response.routes:
        await RouteCache.set_cached_routes(payload, response)
        
    return response

@router.get("/debug")
async def debug_route(
    request: Request,
    source_code: str,
    dest_code: str,
    source_issuer: str | None = None,
    dest_issuer: str | None = None,
) -> dict:
    """Debug why a route is failing."""
    import hashlib
    import networkx as nx
    
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
