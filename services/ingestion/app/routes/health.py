"""Health check route."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from meridian_shared.models import ServiceHealth

router = APIRouter()


@router.get("/health", response_model=ServiceHealth)
async def health_check() -> ServiceHealth:
    """Service health endpoint."""
    return ServiceHealth(
        service="ingestion",
        status="healthy",
        version="0.1.0",
        timestamp=datetime.now(timezone.utc),
        dependencies={},
    )
