"""Routing endpoints — proxy to graph-engine service."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
import httpx

from meridian_shared.config import get_settings
from meridian_shared.models import (
    RouteDiscoverRequest,
    RouteDiscoverResponse,
    RouteValidateRequest,
)

router = APIRouter()

TIMEOUT = 30.0


async def _proxy_post(path: str, payload: dict) -> dict:
    """POST proxy to graph-engine."""
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(
                f"{settings.graph_engine_url}/v1/routes{path}",
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Graph engine unavailable: {e}")


async def _proxy_get(path: str, params: dict | None = None) -> dict:
    """GET proxy to graph-engine."""
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(
                f"{settings.graph_engine_url}/v1/routes{path}",
                params=params,
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Graph engine unavailable: {e}")


@router.post("/discover")
async def discover_routes(payload: RouteDiscoverRequest) -> dict:
    """Discover optimal risk-adjusted routes. Proxied to graph-engine."""
    return await _proxy_post("/discover", payload.model_dump(mode="json"))


@router.post("/validate")
async def validate_route(payload: RouteValidateRequest) -> dict:
    """Validate a route for execution readiness. Proxied to graph-engine."""
    return await _proxy_post("/validate", payload.model_dump(mode="json"))


@router.post("/simulate")
async def simulate_route(payload: RouteValidateRequest) -> dict:
    """Run standalone execution simulation. Proxied to graph-engine."""
    return await _proxy_post("/simulate", payload.model_dump(mode="json"))


@router.get("/explain/{route_hash}")
async def explain_route(route_hash: str) -> dict:
    """Explain why a route was selected. Proxied to graph-engine."""
    return await _proxy_get(f"/explain/{route_hash}")


@router.get("/cache/stats")
async def cache_stats() -> dict:
    """Get route cache statistics. Proxied to graph-engine."""
    return await _proxy_get("/cache/stats")


@router.get("/metrics")
async def route_metrics() -> dict:
    """Get route observability metrics. Proxied to graph-engine."""
    return await _proxy_get("/metrics")


@router.get("/debug")
async def debug_route(
    source_code: str,
    dest_code: str,
    source_issuer: str | None = None,
    dest_issuer: str | None = None,
) -> dict:
    """Debug route resolution. Proxied to graph-engine."""
    params = {"source_code": source_code, "dest_code": dest_code}
    if source_issuer:
        params["source_issuer"] = source_issuer
    if dest_issuer:
        params["dest_issuer"] = dest_issuer
    return await _proxy_get("/debug", params)
