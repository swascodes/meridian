"""Graph proxy endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
import httpx

from meridian_shared.config import get_settings
from meridian_shared.models import GraphStats

router = APIRouter()


@router.get("/stats", response_model=GraphStats)
async def graph_stats() -> GraphStats:
    """Get graph topology statistics."""
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{settings.graph_engine_url}/v1/graph/stats")
            resp.raise_for_status()
            return GraphStats(**resp.json())
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Graph engine unavailable: {e}")
