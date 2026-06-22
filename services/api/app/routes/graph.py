"""Graph proxy endpoints — all graph-engine calls proxied through gateway."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
import httpx

from meridian_shared.config import get_settings

router = APIRouter()

TIMEOUT = 15.0


async def _proxy_get(path: str, params: dict | None = None) -> dict:
    """GET proxy to graph-engine."""
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(
                f"{settings.graph_engine_url}/v1/graph{path}",
                params=params,
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Graph engine unavailable: {e}")


@router.get("/stats")
async def graph_stats() -> dict:
    """Get graph topology statistics."""
    return await _proxy_get("/stats")


@router.get("/audit")
async def graph_audit() -> dict:
    """Audit graph connectivity and construction state."""
    return await _proxy_get("/audit")


@router.get("/metrics")
async def graph_metrics() -> dict:
    """Get graph observability metrics."""
    return await _proxy_get("/metrics")

@router.get("/assets")
async def graph_assets(limit: int = 100, skip: int = 0, q: str | None = None) -> dict:
    """Get discovered assets in the graph. Proxied to graph-engine."""
    params = {"limit": limit, "skip": skip}
    if q:
        params["q"] = q
    return await _proxy_get("/assets", params)
