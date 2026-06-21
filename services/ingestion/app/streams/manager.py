"""Stream manager — orchestrates all ingestion streams."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import structlog

from app.streams.assets import AssetDiscoveryStream
from app.streams.orderbooks import OrderbookPoller
from app.streams.pools import PoolSyncStream
from app.streams.trades import TradeStream

logger = structlog.get_logger()


class StreamManager:
    """Orchestrates all data ingestion streams."""

    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task] = {}  # type: ignore[type-arg]
        self._streams: dict[str, object] = {}
        self.is_running = False
        self._started_at: datetime | None = None

    async def start(self) -> None:
        """Start all ingestion streams."""
        logger.info("stream_manager_starting")

        streams = {
            "trade_stream": TradeStream(),
            "orderbook_poller": OrderbookPoller(),
            "asset_discovery": AssetDiscoveryStream(),
            "pool_sync": PoolSyncStream(),
        }

        for name, stream in streams.items():
            task = asyncio.create_task(stream.run(), name=f"stream_{name}")
            self._tasks[name] = task
            self._streams[name] = stream
            logger.info("stream_started", stream=name)

        self.is_running = True
        self._started_at = datetime.now(timezone.utc)

    async def stop(self) -> None:
        """Stop all ingestion streams."""
        logger.info("stream_manager_stopping")

        for name, task in self._tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                logger.info("stream_stopped", stream=name)

        self._tasks.clear()
        self._streams.clear()
        self.is_running = False

    def get_status(self) -> dict[str, dict]:
        """Get status of all streams."""
        status = {}
        for name, task in self._tasks.items():
            status[name] = {
                "running": not task.done(),
                "cancelled": task.cancelled(),
                "error": str(task.exception()) if task.done() and not task.cancelled() and task.exception() else None,
            }
        return status
