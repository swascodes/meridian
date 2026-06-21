"""Quality API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from meridian_shared.models import RouteQuality

from app.oracle.scorer import RouteScorer

router = APIRouter()
scorer = RouteScorer()


@router.get("/{route_hash}", response_model=RouteQuality)
async def get_route_quality(route_hash: str) -> RouteQuality:
    """Get quality score for a specific route."""
    result = await scorer.score_route(route_hash)
    if not result:
        raise HTTPException(status_code=404, detail="Route not found")
    return result


@router.post("/batch")
async def batch_score(route_hashes: list[str]) -> list[RouteQuality | None]:
    """Score multiple routes."""
    results = []
    for route_hash in route_hashes[:50]:  # Cap at 50
        result = await scorer.score_route(route_hash)
        results.append(result)
    return results
