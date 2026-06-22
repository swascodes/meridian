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
        total_assets=stats["total_assets"],
        total_pools=stats["total_pools"],
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


@router.get("/assets")
async def get_assets(request: Request, limit: int = 100, skip: int = 0, q: str | None = None) -> dict:
    """Get discovered assets in the graph."""
    import networkx as nx
    manager = request.app.state.graph_manager
    graph = manager.builder.graph
    
    if graph.number_of_nodes() == 0:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Graph engine is still initializing")
    
    # Pre-calculate components if graph is populated
    components = list(nx.weakly_connected_components(graph)) if graph.number_of_nodes() > 0 else []
    node_to_comp_size = {}
    for comp in components:
        size = len(comp)
        for node in comp:
            node_to_comp_size[node] = size

    assets = []
    for node, data in graph.nodes(data=True):
        if data.get("node_type") == "asset":
            degree = graph.degree(node)
            comp_size = node_to_comp_size.get(node, 1)
            
            # Filter criteria: degree > 0 and component_size > 1
            if degree > 0 and comp_size > 1:
                code = data.get("code", "")
                
                # Search query filter
                if q and q.lower() not in code.lower():
                    continue

                assets.append({
                    "node_id": node,
                    "code": code,
                    "issuer": data.get("issuer"),
                    "domain": data.get("domain"),
                    "trustlines": data.get("trustlines", 0),
                    "volume_24h": data.get("volume_24h", 0.0),
                    "degree": degree,
                    "component_size": comp_size,
                })
            
    # Sort by degree and trustlines descending
    assets.sort(key=lambda x: (x["degree"], x["trustlines"]), reverse=True)
    
    return {
        "count": len(assets),
        "assets": assets[skip : skip + limit],
    }


@router.get("/pools")
async def get_pools(request: Request, limit: int = 100, skip: int = 0) -> dict:
    """Get discovered liquidity pools in the graph."""
    manager = request.app.state.graph_manager
    graph = manager.builder.graph
    
    pools = []
    for node, data in graph.nodes(data=True):
        if data.get("node_type") == "pool":
            pools.append({
                "node_id": node,
                "pool_id": data.get("pool_id"),
                "reserve_a": data.get("reserve_a", 0.0),
                "reserve_b": data.get("reserve_b", 0.0),
                "total_shares": data.get("total_shares", 0.0),
                "fee_bp": data.get("fee_bp", 30),
            })
            
    # Sort by liquidity proxy (total_shares) descending
    pools.sort(key=lambda x: x["total_shares"], reverse=True)
    
    return {
        "count": len(pools),
        "pools": pools[skip : skip + limit],
    }


@router.get("/components")
async def get_components(request: Request) -> dict:
    """Get graph connected components diagnostics."""
    manager = request.app.state.graph_manager
    graph = manager.builder.graph
    
    import networkx as nx
    
    components = list(nx.weakly_connected_components(graph))
    component_sizes = [len(c) for c in components]
    component_sizes.sort(reverse=True)
    
    return {
        "total_components": len(components),
        "largest_component_size": component_sizes[0] if component_sizes else 0,
        "isolated_nodes": len([c for c in components if len(c) == 1]),
        "sizes": component_sizes[:10],  # Top 10 sizes
    }


@router.get("/connectivity")
async def get_connectivity(request: Request) -> dict:
    """Get graph connectivity diagnostics."""
    manager = request.app.state.graph_manager
    graph = manager.builder.graph
    
    import networkx as nx
    
    num_nodes = graph.number_of_nodes()
    
    return {
        "nodes": num_nodes,
        "edges": graph.number_of_edges(),
        "density": nx.density(graph),
        "avg_degree": sum(d for _, d in graph.degree()) / num_nodes if num_nodes > 0 else 0,
    }


@router.get("/health")
async def get_health(request: Request) -> dict:
    """Get graph engine health and caching diagnostics."""
    manager = request.app.state.graph_manager
    graph = manager.builder.graph
    
    return {
        "status": "healthy" if graph.number_of_nodes() > 0 else "initializing",
        "nodes": graph.number_of_nodes(),
        "cache_rebuild_interval": manager._rebuild_interval,
        "last_rebuild_attempt": datetime.now(timezone.utc), # simplified
    }

@router.get("/audit")
async def get_audit(request: Request) -> dict:
    """Audit graph connectivity and construction state."""
    from sqlalchemy import select, func, distinct, tuple_
    from meridian_shared.db import get_session, OrderbookSnapshot

    manager = request.app.state.graph_manager
    graph = manager.builder.graph
    
    asset_count = sum(1 for _, d in graph.nodes(data=True) if d.get("node_type") == "asset")
    pool_count = sum(1 for _, d in graph.nodes(data=True) if d.get("node_type") == "pool")
    
    pool_edges = sum(1 for _, _, d in graph.edges(data=True) if d.get("edge_type") == "pool_hop")
    orderbook_edges = sum(1 for _, _, d in graph.edges(data=True) if d.get("edge_type") == "orderbook")
    
    isolated_assets = sum(1 for n, d in graph.nodes(data=True) if d.get("node_type") == "asset" and graph.degree(n) == 0)

    # Query unique orderbook pairs from database
    async with get_session() as session:
        unique_orderbook_pairs = await session.scalar(
            select(func.count(distinct(tuple_(
                OrderbookSnapshot.base_asset_id,
                OrderbookSnapshot.counter_asset_id,
            ))))
        ) or 0

    return {
        "assets": asset_count,
        "pools": pool_count,
        "orderbooks": unique_orderbook_pairs,
        "pool_edges_expected": pool_count * 4,
        "pool_edges_created": pool_edges,
        "orderbook_edges_expected": unique_orderbook_pairs * 2,
        "orderbook_edges_created": orderbook_edges,
        "isolated_assets": isolated_assets,
    }
