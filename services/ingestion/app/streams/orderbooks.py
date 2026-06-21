"""Orderbook poller — periodic orderbook snapshots from Horizon."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import structlog
from sqlalchemy import select

from meridian_shared.config import get_settings
from meridian_shared.db import Asset, OrderbookSnapshot, get_session
from meridian_shared.redis import RedisKeys, get_redis
from meridian_shared.stellar import get_horizon_client

logger = structlog.get_logger()


class OrderbookPoller:
    """Periodically polls orderbooks for tracked asset pairs."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._running = True
        
        # State tracking
        self.pairs_scanned = 0
        self.orderbooks_persisted = 0
        self.last_sync_time = None

    async def run(self) -> None:
        """Main polling loop."""
        while self._running:
            try:
                await self._poll_orderbooks()
                await asyncio.sleep(self.settings.ingestion_orderbook_poll_interval)
            except asyncio.CancelledError:
                logger.info("orderbook_poller_cancelled")
                break
            except Exception as e:
                logger.error("orderbook_poll_error", error=str(e))
                await asyncio.sleep(10)

    async def _poll_orderbooks(self) -> None:
        """Poll orderbooks for all known high-volume pairs or top testnet assets."""
        async with get_session() as session:
            # Get top assets
            if self.settings.stellar_network.lower() == "testnet":
                # Testnet assets have 0 volume, use trustlines instead
                stmt = (
                    select(Asset)
                    .order_by(Asset.total_trustlines.desc())
                    .limit(50)
                )
            else:
                stmt = (
                    select(Asset)
                    .where(Asset.total_volume_24h > 0)
                    .order_by(Asset.total_volume_24h.desc())
                    .limit(50)
                )
                
            result = await session.execute(stmt)
            assets = result.scalars().all()

        if not assets:
            logger.debug("no_assets_for_orderbook_polling")
            return

        # XLM is always included as base
        xlm = next((a for a in assets if a.code == "XLM" and a.issuer is None), None)
        if not xlm:
            return

        tasks = []
        for asset in assets:
            if asset.id != xlm.id:
                self.pairs_scanned += 1
                tasks.append(self._fetch_and_store_orderbook(xlm, asset))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            success_count = sum(1 for r in results if not isinstance(r, Exception))
            self.orderbooks_persisted += success_count
            self.last_sync_time = datetime.now(timezone.utc)
            logger.info("orderbooks_polled", total=len(tasks), success=success_count)

    async def _fetch_and_store_orderbook(self, base: Asset, counter: Asset) -> None:
        """Fetch a single orderbook from Horizon and store snapshot."""
        server = get_horizon_client()
        from stellar_sdk.asset import Asset as StellarAsset

        try:
            # Build asset representations for the SDK
            if base.issuer is None:
                selling_asset = StellarAsset.native()
            else:
                selling_asset = StellarAsset(base.code, base.issuer)

            if counter.issuer is None:
                buying_asset = StellarAsset.native()
            else:
                buying_asset = StellarAsset(counter.code, counter.issuer)

            response = server.orderbook(
                selling=selling_asset,
                buying=buying_asset,
            ).limit(self.settings.ingestion_max_orderbook_depth).call()

            bids = [{"price": float(b["price"]), "amount": float(b["amount"])} for b in response.get("bids", [])]
            asks = [{"price": float(a["price"]), "amount": float(a["amount"])} for a in response.get("asks", [])]

            bid_depth = sum(b["amount"] for b in bids)
            ask_depth = sum(a["amount"] for a in asks)

            best_bid = bids[0]["price"] if bids else 0.0
            best_ask = asks[0]["price"] if asks else 0.0
            spread = (best_ask - best_bid) / best_ask if best_ask > 0 else 0.0
            mid_price = (best_bid + best_ask) / 2 if (best_bid + best_ask) > 0 else 0.0

            now = datetime.now(timezone.utc)

            snapshot = OrderbookSnapshot(
                base_asset_id=base.id,
                counter_asset_id=counter.id,
                timestamp=now,
                bids=bids,  # type: ignore[arg-type]
                asks=asks,  # type: ignore[arg-type]
                bid_depth=bid_depth,
                ask_depth=ask_depth,
                spread=spread,
                mid_price=mid_price,
            )

            async with get_session() as session:
                session.add(snapshot)

            # Cache in Redis
            redis = get_redis()
            cache_key = RedisKeys.orderbook(base.code, counter.code)
            await redis.set(cache_key, str({"bids": bids, "asks": asks, "spread": spread, "mid_price": mid_price}), ex=120)
            await redis.publish(RedisKeys.CHANNEL_ORDERBOOK, f"{base.code}:{counter.code}")

        except Exception as e:
            import traceback
            logger.warning("orderbook_fetch_error", base=base.code, counter=counter.code, error=str(e), tb=traceback.format_exc())
