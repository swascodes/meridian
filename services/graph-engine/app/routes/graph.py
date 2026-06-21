"""Graph API routes."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from meridian_shared.models import GraphStats
from meridian_shared.stellar import parse_asset_identifier

router = APIRouter()


@router.get("/stats", response_model=GraphStats)
async def graph_stats(request: Request) -> GraphStats:
    """Get graph topology statistics."""
    manager = request.app.state.graph_manager
    stats = manager.get_stats()
    return GraphStats(
        total_nodes=stats["total_nodes"],
        total_edges=stats["total_edges"],
        total_assets=stats["total_nodes"],
        total_pools=0,
        avg_degree=stats["avg_degree"],
        density=stats["density"],
        connected_components=stats["connected_components"],
        last_updated_at=datetime.now(timezone.utc),
    )


@router.get("/paths/{source}/{destination}")
async def find_paths(
    request: Request,
    source: str,
    destination: str,
    max_hops: int = 4,
    max_paths: int = 10,
) -> dict:
    """Find paths between two assets.

    Assets specified as CODE:ISSUER or 'native'.
    """
    manager = request.app.state.graph_manager

    try:
        source_code, source_issuer = parse_asset_identifier(source)
        dest_code, dest_issuer = parse_asset_identifier(destination)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    paths = manager.find_paths(
        source_code, source_issuer,
        dest_code, dest_issuer,
        max_hops=max_hops,
        max_paths=max_paths,
    )

    # Enrich paths with node info
    enriched_paths = []
    for path in paths:
        enriched = []
        for node_id in path:
            node_info = manager.get_node_info(node_id)
            enriched.append(node_info or {"node_id": node_id})
        enriched_paths.append(enriched)

    return {
        "source": source,
        "destination": destination,
        "paths": enriched_paths,
        "count": len(enriched_paths),
    }


@router.get("/neighbors/{asset}")
async def get_neighbors(request: Request, asset: str) -> dict:
    """Get neighboring assets in the graph."""
    manager = request.app.state.graph_manager

    try:
        code, issuer = parse_asset_identifier(asset)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    from app.graph.builder import GraphBuilder
    node_id = GraphBuilder._asset_node_id(code, issuer)
    neighbors = manager.get_neighbors(node_id)

    return {
        "asset": asset,
        "neighbors": neighbors,
        "count": len(neighbors),
    }


@router.post("/rebuild")
async def rebuild_graph(request: Request) -> dict:
    """Trigger a full graph rebuild."""
    manager = request.app.state.graph_manager
    await manager.rebuild()
    stats = manager.get_stats()
    return {"status": "rebuilt", "stats": stats}
