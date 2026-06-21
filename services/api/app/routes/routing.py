"""Routing endpoints — proxy to route-optimizer service."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
import httpx

from meridian_shared.config import get_settings
from meridian_shared.models import RouteResult, RouteSimulationRequest, RouteSimulationResult

router = APIRouter()


@router.get("/{source}/{destination}", response_model=list[RouteResult])
async def find_routes(
    source: str,
    destination: str,
    amount: float = 100.0,
    max_hops: int = 4,
) -> list[RouteResult]:
    """Find optimal routes between two assets."""
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{settings.route_optimizer_url}/v1/optimize/routes/{source}/{destination}",
                params={"amount": amount, "max_hops": max_hops},
            )
            resp.raise_for_status()
            return [RouteResult(**r) for r in resp.json()]
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Route optimizer unavailable: {e}")


@router.get("/{source}/{destination}/alternatives", response_model=list[RouteResult])
async def find_alternative_routes(
    source: str,
    destination: str,
    amount: float = 100.0,
    max_results: int = 10,
) -> list[RouteResult]:
    """Get ranked alternative routes."""
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{settings.route_optimizer_url}/v1/optimize/routes/{source}/{destination}",
                params={"amount": amount, "max_hops": 6, "max_results": max_results},
            )
            resp.raise_for_status()
            return [RouteResult(**r) for r in resp.json()]
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Route optimizer unavailable: {e}")


@router.post("/simulate", response_model=RouteSimulationResult)
async def simulate_route(request: RouteSimulationRequest) -> RouteSimulationResult:
    """Simulate route execution."""
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{settings.route_optimizer_url}/v1/optimize/simulate",
                json=request.model_dump(),
            )
            resp.raise_for_status()
            return RouteSimulationResult(**resp.json())
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Route optimizer unavailable: {e}")
