"""Meridian Developer Routing API — main application."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from meridian_shared.db import close_engine
from meridian_shared.logging import setup_logging
from meridian_shared.redis import close_redis

logger = setup_logging("api")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("api_starting")
    yield
    logger.info("api_stopping")
    await close_engine()
    await close_redis()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Meridian Routing API",
        description="AI-powered routing intelligence for the Stellar network",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Restrict in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate limiting middleware
    from app.middleware.rate_limit import RateLimitMiddleware
    app.add_middleware(RateLimitMiddleware, requests_per_minute=60)

    # Routes
    from app.routes.health import router as health_router
    from app.routes.routing import router as routing_router
    from app.routes.assets import router as assets_router
    from app.routes.graph import router as graph_router
    from app.routes.quality import router as quality_router
    from app.routes.registry import router as registry_router

    app.include_router(health_router)
    app.include_router(routing_router, prefix="/v1/routes", tags=["Routes"])
    app.include_router(assets_router, prefix="/v1/assets", tags=["Assets"])
    app.include_router(graph_router, prefix="/v1/graph", tags=["Graph"])
    app.include_router(quality_router, prefix="/v1/quality", tags=["Quality"])
    app.include_router(registry_router, prefix="/v1/registry", tags=["Registry"])

    return app
