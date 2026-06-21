"""Predictive Engine — Phase 1 stub service.

This service will house ML-based route prediction in Phase 2.
Currently provides a stub API that returns baseline predictions.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import APIRouter, FastAPI

from meridian_shared.db import close_engine
from meridian_shared.logging import setup_logging
from meridian_shared.models import ServiceHealth
from meridian_shared.redis import close_redis

logger = setup_logging("predictive-engine")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("predictive_engine_starting")
    yield
    logger.info("predictive_engine_stopping")
    await close_engine()
    await close_redis()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Meridian Predictive Routing Engine",
        version="0.1.0",
        docs_url="/docs",
        lifespan=lifespan,
    )

    router = APIRouter()

    @router.get("/health", response_model=ServiceHealth)
    async def health_check() -> ServiceHealth:
        return ServiceHealth(
            service="predictive-engine",
            status="healthy",
            version="0.1.0",
            timestamp=datetime.now(timezone.utc),
            dependencies={"ml_model": "not_loaded"},
        )

    @router.get("/v1/predict/{route_hash}")
    async def predict_route_quality(route_hash: str) -> dict:
        """Stub: predict future route quality.

        Phase 2 will implement actual ML-based prediction.
        """
        return {
            "route_hash": route_hash,
            "predicted_quality": 0.75,  # Baseline
            "predicted_slippage": 0.005,
            "confidence": 0.1,  # Low confidence — stub
            "model_version": "stub-v0",
            "predicted_at": datetime.now(timezone.utc).isoformat(),
            "note": "Stub prediction — ML model not yet trained",
        }

    @router.post("/v1/predict/batch")
    async def batch_predict(route_hashes: list[str]) -> list[dict]:
        """Stub: batch predict route quality."""
        return [
            {
                "route_hash": rh,
                "predicted_quality": 0.75,
                "confidence": 0.1,
                "model_version": "stub-v0",
            }
            for rh in route_hashes[:50]
        ]

    app.include_router(router)
    return app
