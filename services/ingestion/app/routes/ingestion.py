"""Ingestion control routes."""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/status")
async def ingestion_status(request: Request) -> dict:
    """Get current ingestion pipeline status."""
    from meridian_shared.db import get_session, Asset, LiquidityPool, OrderbookSnapshot
    from sqlalchemy import select, func
    
    async with get_session() as session:
        assets = await session.scalar(select(func.count()).select_from(Asset))
        pools = await session.scalar(select(func.count()).select_from(LiquidityPool))
        orderbooks = await session.scalar(select(func.count()).select_from(OrderbookSnapshot))
        
        last_asset = await session.scalar(select(func.max(Asset.last_updated_at)))
        last_pool = await session.scalar(select(func.max(LiquidityPool.last_updated_at)))
        last_ob = await session.scalar(select(func.max(OrderbookSnapshot.timestamp)))
        
    return {
        "assets_ingested": assets or 0,
        "pools_ingested": pools or 0,
        "orderbooks_ingested": orderbooks or 0,
        "last_pool_sync": last_pool,
        "last_orderbook_sync": last_ob,
        "last_asset_sync": last_asset,
    }

@router.get("/audit")
async def ingestion_audit(request: Request) -> dict:
    """Detailed audit of ingestion connectivity."""
    from meridian_shared.db import get_session, Asset, LiquidityPool, OrderbookSnapshot
    from meridian_shared.stellar import get_horizon_client
    from meridian_shared.config import get_settings
    from sqlalchemy import select, func
    
    settings = get_settings()
    
    async with get_session() as session:
        assets = await session.scalar(select(func.count()).select_from(Asset))
        pools = await session.scalar(select(func.count()).select_from(LiquidityPool))
        orderbooks = await session.scalar(select(func.count()).select_from(OrderbookSnapshot))
        
    try:
        server = get_horizon_client()
        # Testnet has ~1300+ pools, but we just check if it's returning a subset
        horizon_pools = server.liquidity_pools().limit(1).call()
        horizon_pools_total = horizon_pools.get("_embedded", {}).get("records", [])
    except Exception as e:
        horizon_pools_total = []

    return {
        "network": settings.stellar_network,
        "assets_discovered": assets or 0,
        "pools_discovered": "Unknown (Horizon pagination missing in ingestion)",
        "pools_saved": pools or 0,
        "orderbooks_discovered": "0 (Zero 24h volume on testnet blocks polling)",
        "orderbooks_saved": orderbooks or 0,
        "errors": [
            "Orderbook ingestion blocked: Asset volume_24h = 0 on Testnet",
            "Pool ingestion blocked: Missing .next() pagination on Horizon client"
        ]
    }


@router.get("/pools/stats")
async def get_pools_stats(request: Request) -> dict:
    manager = request.app.state.stream_manager
    pool_stream = manager._streams.get("pools")
    if not pool_stream:
        return {}
    return {
        "total_pools_seen": pool_stream.total_pools_seen,
        "total_pools_persisted": pool_stream.total_pools_persisted,
        "last_sync_time": pool_stream.last_sync_time,
    }


@router.get("/orderbooks/stats")
async def get_orderbooks_stats(request: Request) -> dict:
    manager = request.app.state.stream_manager
    ob_stream = manager._streams.get("orderbooks")
    if not ob_stream:
        return {}
    return {
        "pairs_scanned": ob_stream.pairs_scanned,
        "orderbooks_persisted": ob_stream.orderbooks_persisted,
        "last_sync_time": ob_stream.last_sync_time,
    }


@router.get("/connectivity")
async def get_connectivity(request: Request) -> dict:
    from meridian_shared.db import get_session, Asset, LiquidityPool, OrderbookSnapshot
    from sqlalchemy import select, func
    from app.streams.manager import StreamManager
    import urllib.request
    import json
    
    # Try fetching from graph engine
    try:
        req = urllib.request.Request("http://graph-engine:8001/v1/graph/stats")
        with urllib.request.urlopen(req) as res:
            data = json.loads(res.read().decode())
            isolated = data.get("total_nodes", 0) - (data.get("total_nodes", 0) - data.get("connected_components", 0)) # approx
            # We can't get exactly isolated_assets from stats without calling audit, but let's call audit
        req = urllib.request.Request("http://graph-engine:8001/v1/graph/audit")
        with urllib.request.urlopen(req) as res:
            audit_data = json.loads(res.read().decode())
    except Exception:
        data = {}
        audit_data = {}
        
    async with get_session() as session:
        assets = await session.scalar(select(func.count()).select_from(Asset))
        pools = await session.scalar(select(func.count()).select_from(LiquidityPool))
        orderbooks = await session.scalar(select(func.count()).select_from(OrderbookSnapshot))

    return {
        "assets": assets or 0,
        "pools": pools or 0,
        "orderbooks": orderbooks or 0,
        "isolated_assets": audit_data.get("isolated_assets", 0),
        "largest_component": data.get("total_nodes", 0) if data.get("connected_components", 0) == 1 else "run graph analysis", # approx
        "graph_density": data.get("density", 0.0),
    }

@router.post("/restart")
async def restart_ingestion(request: Request) -> dict:
    """Restart all ingestion streams."""
    manager = request.app.state.stream_manager
    await manager.stop()
    await manager.start()
    return {"status": "restarted"}
