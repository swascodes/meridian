"""Ingestion service FastAPI application."""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI

from meridian_shared.db import close_engine
from meridian_shared.logging import setup_logging
from meridian_shared.redis import close_redis

logger = setup_logging("ingestion")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage service lifecycle."""
    logger.info("ingestion_starting")

    from app.streams.manager import StreamManager
    manager = StreamManager()
    app.state.stream_manager = manager
    await manager.start()

    yield

    logger.info("ingestion_stopping")
    await manager.stop()
    await close_engine()
    await close_redis()


def create_app() -> FastAPI:
    """Application factory."""
    app = FastAPI(
        title="Meridian Ingestion Service",
        version="0.1.0",
        docs_url="/docs",
        lifespan=lifespan,
    )

    from app.routes.health import router as health_router
    from app.routes.ingestion import router as ingestion_router

    app.include_router(health_router)
    app.include_router(ingestion_router, prefix="/v1/ingestion")

    return app
