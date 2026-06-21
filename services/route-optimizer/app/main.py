"""Route Optimization Engine FastAPI application."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from meridian_shared.db import close_engine
from meridian_shared.logging import setup_logging
from meridian_shared.redis import close_redis

logger = setup_logging("route-optimizer")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("route_optimizer_starting")
    yield
    logger.info("route_optimizer_stopping")
    await close_engine()
    await close_redis()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Meridian Route Optimization Engine",
        version="0.1.0",
        docs_url="/docs",
        lifespan=lifespan,
    )

    from app.routes.health import router as health_router
    from app.routes.optimize import router as optimize_router

    app.include_router(health_router)
    app.include_router(optimize_router, prefix="/v1/optimize")

    return app
