"""Quality proxy endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
import httpx

from meridian_shared.config import get_settings
from meridian_shared.models import RouteQuality

router = APIRouter()


@router.get("/{route_hash}", response_model=RouteQuality)
async def get_quality(route_hash: str) -> RouteQuality:
    """Get quality score for a route."""
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{settings.quality_oracle_url}/v1/quality/{route_hash}")
            resp.raise_for_status()
            return RouteQuality(**resp.json())
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Quality oracle unavailable: {e}")
