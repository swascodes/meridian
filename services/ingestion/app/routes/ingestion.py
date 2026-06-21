"""Ingestion control routes."""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/status")
async def ingestion_status(request: Request) -> dict:
    """Get current ingestion pipeline status."""
    manager = request.app.state.stream_manager
    return {
        "streams": manager.get_status(),
        "is_running": manager.is_running,
    }


@router.post("/restart")
async def restart_ingestion(request: Request) -> dict:
    """Restart all ingestion streams."""
    manager = request.app.state.stream_manager
    await manager.stop()
    await manager.start()
    return {"status": "restarted"}
