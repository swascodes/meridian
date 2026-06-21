"""Trade stream — consumes Stellar Horizon trade stream."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import structlog
from sqlalchemy import select

from meridian_shared.config import get_settings
from meridian_shared.db import Asset, Trade, get_session
from meridian_shared.redis import RedisKeys, get_redis
from meridian_shared.stellar import get_horizon_client

from app.services.cursor import CursorManager

logger = structlog.get_logger()


class TradeStream:
    """Streams trades from Stellar Horizon and persists to PostgreSQL."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.cursor_manager = CursorManager("trades")
        self._running = True

    async def run(self) -> None:
        """Main stream loop with reconnection."""
        while self._running:
            try:
                await self._stream_trades()
            except asyncio.CancelledError:
                logger.info("trade_stream_cancelled")
                break
            except Exception as e:
                logger.error("trade_stream_error", error=str(e))
                await asyncio.sleep(5)  # Reconnect delay

    async def _stream_trades(self) -> None:
        """Connect to Horizon and stream trades."""
        server = get_horizon_client()
        cursor = await self.cursor_manager.get_cursor()

        builder = server.trades().limit(200).order(desc=False)
        if cursor:
            builder = builder.cursor(cursor)

        logger.info("trade_stream_connected", cursor=cursor)

        # Use call() for polling since streaming SSE needs special handling
        while self._running:
            try:
                response = builder.call()
                records = response["_embedded"]["records"]

                if records:
                    await self._process_batch(records)
                    last_cursor = records[-1]["paging_token"]
                    await self.cursor_manager.save_cursor(last_cursor)
                    builder = server.trades().cursor(last_cursor).limit(200).order(desc=False)
                else:
                    await asyncio.sleep(5)  # No new trades, wait

            except Exception as e:
                logger.warning("trade_fetch_error", error=str(e))
                await asyncio.sleep(5)

    async def _process_batch(self, records: list[dict]) -> None:
        """Process a batch of trade records."""
        redis = get_redis()

        async with get_session() as session:
            for record in records:
                try:
                    trade = await self._record_to_trade(session, record)
                    if trade:
                        session.add(trade)

                        # Publish to Redis for real-time consumers
                        await redis.publish(
                            RedisKeys.CHANNEL_TRADE,
                            f"{trade.stellar_trade_id}",
                        )
                except Exception as e:
                    logger.warning("trade_process_error", trade_id=record.get("id"), error=str(e))

        logger.debug("trades_batch_processed", count=len(records))

    async def _record_to_trade(self, session, record: dict) -> Trade | None:  # type: ignore[no-untyped-def]
        """Convert Horizon trade record to Trade model."""
        # Resolve assets
        base_asset = await self._resolve_asset(
            session,
            record.get("base_asset_code", "XLM"),
            record.get("base_asset_issuer"),
            record.get("base_asset_type", "native"),
        )
        counter_asset = await self._resolve_asset(
            session,
            record.get("counter_asset_code", "XLM"),
            record.get("counter_asset_issuer"),
            record.get("counter_asset_type", "native"),
        )

        if not base_asset or not counter_asset:
            return None

        # Parse price
        price_n = float(record.get("price", {}).get("n", 0))
        price_d = float(record.get("price", {}).get("d", 1))
        price = price_n / price_d if price_d else 0

        timestamp = datetime.fromisoformat(record["ledger_close_time"].replace("Z", "+00:00"))

        return Trade(
            stellar_trade_id=record["id"],
            base_asset_id=base_asset.id,
            counter_asset_id=counter_asset.id,
            base_amount=float(record.get("base_amount", 0)),
            counter_amount=float(record.get("counter_amount", 0)),
            price=price,
            base_is_seller=record.get("base_is_seller", False),
            timestamp=timestamp,
            ledger_close_time=timestamp,
            trade_type="liquidity_pool" if record.get("liquidity_pool_id") else "orderbook",
            liquidity_pool_id=record.get("liquidity_pool_id"),
        )

    async def _resolve_asset(
        self, session, code: str, issuer: str | None, asset_type: str  # type: ignore[no-untyped-def]
    ) -> Asset | None:
        """Find or create an asset record."""
        if asset_type == "native":
            code = "XLM"
            issuer = None

        stmt = select(Asset).where(Asset.code == code, Asset.issuer == issuer)
        result = await session.execute(stmt)
        asset = result.scalar_one_or_none()

        if not asset:
            asset = Asset(
                code=code,
                issuer=issuer,
                asset_type=asset_type,
                last_seen_at=datetime.now(timezone.utc),
            )
            session.add(asset)
            await session.flush()

        return asset
