"""Route Quality Oracle FastAPI application."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from meridian_shared.db import close_engine
from meridian_shared.logging import setup_logging
from meridian_shared.redis import close_redis

logger = setup_logging("quality-oracle")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("quality_oracle_starting")
    yield
    logger.info("quality_oracle_stopping")
    await close_engine()
    await close_redis()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Meridian Route Quality Oracle",
        version="0.1.0",
        docs_url="/docs",
        lifespan=lifespan,
    )

    from app.routes.health import router as health_router
    from app.routes.quality import router as quality_router

    app.include_router(health_router)
    app.include_router(quality_router, prefix="/v1/quality")

    return app
