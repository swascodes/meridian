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
