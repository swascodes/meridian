"""Graph Discovery Engine FastAPI application."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from meridian_shared.db import close_engine
from meridian_shared.logging import setup_logging
from meridian_shared.redis import close_redis

logger = setup_logging("graph-engine")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage service lifecycle."""
    logger.info("graph_engine_starting")

    from app.graph.manager import GraphManager
    manager = GraphManager()
    app.state.graph_manager = manager
    await manager.initialize()

    yield

    logger.info("graph_engine_stopping")
    await manager.shutdown()
    await close_engine()
    await close_redis()


def create_app() -> FastAPI:
    """Application factory."""
    app = FastAPI(
        title="Meridian Graph Discovery Engine",
        version="0.1.0",
        docs_url="/docs",
        lifespan=lifespan,
    )

    from app.routes.health import router as health_router
    from app.routes.graph import router as graph_router

    app.include_router(health_router)
    app.include_router(graph_router, prefix="/v1/graph")

    return app
