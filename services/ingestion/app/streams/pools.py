"""Pool sync stream — synchronizes Stellar AMM pool state."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import structlog
from sqlalchemy import select

from meridian_shared.config import get_settings
from meridian_shared.db import Asset, LiquidityPool, get_session
from meridian_shared.redis import RedisKeys, get_redis
from meridian_shared.stellar import get_horizon_client

logger = structlog.get_logger()


class PoolSyncStream:
    """Periodically syncs liquidity pool state from Horizon."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._running = True

    async def run(self) -> None:
        """Main sync loop."""
        while self._running:
            try:
                await self._sync_pools()
                await asyncio.sleep(self.settings.ingestion_pool_sync_interval)
            except asyncio.CancelledError:
                logger.info("pool_sync_cancelled")
                break
            except Exception as e:
                logger.error("pool_sync_error", error=str(e))
                await asyncio.sleep(15)

    async def _sync_pools(self) -> None:
        """Fetch and sync all liquidity pools."""
        server = get_horizon_client()

        try:
            response = server.liquidity_pools().limit(200).call()
            records = response.get("_embedded", {}).get("records", [])

            updated = 0
            created = 0

            async with get_session() as session:
                for record in records:
                    pool_id = record["id"]
                    reserves = record.get("reserves", [])
                    if len(reserves) != 2:
                        continue

                    # Resolve assets
                    asset_a = await self._resolve_pool_asset(session, reserves[0].get("asset", "native"))
                    asset_b = await self._resolve_pool_asset(session, reserves[1].get("asset", "native"))

                    if not asset_a or not asset_b:
                        continue

                    # Upsert pool
                    stmt = select(LiquidityPool).where(LiquidityPool.pool_id == pool_id)
                    result = await session.execute(stmt)
                    pool = result.scalar_one_or_none()

                    reserve_a = float(reserves[0].get("amount", 0))
                    reserve_b = float(reserves[1].get("amount", 0))
                    total_shares = float(record.get("total_shares", 0))
                    fee_bp = int(record.get("fee_bp", 30))

                    if pool:
                        pool.reserve_a = reserve_a
                        pool.reserve_b = reserve_b
                        pool.total_shares = total_shares
                        pool.total_trustlines = int(record.get("total_trustlines", 0))
                        pool.last_updated_at = datetime.now(timezone.utc)
                        updated += 1
                    else:
                        pool = LiquidityPool(
                            pool_id=pool_id,
                            asset_a_id=asset_a.id,
                            asset_b_id=asset_b.id,
                            reserve_a=reserve_a,
                            reserve_b=reserve_b,
                            total_shares=total_shares,
                            fee_bp=fee_bp,
                            total_trustlines=int(record.get("total_trustlines", 0)),
                        )
                        session.add(pool)
                        created += 1

            # Notify graph engine of pool updates
            redis = get_redis()
            await redis.publish(RedisKeys.CHANNEL_POOL_UPDATE, f"synced:{len(records)}")

            logger.info("pool_sync_complete", total=len(records), created=created, updated=updated)

        except Exception as e:
            logger.error("pool_fetch_error", error=str(e))

    async def _resolve_pool_asset(self, session, asset_str: str) -> Asset | None:  # type: ignore[no-untyped-def]
        """Resolve a pool asset string to an Asset record."""
        if asset_str == "native":
            stmt = select(Asset).where(Asset.code == "XLM", Asset.issuer.is_(None))
        else:
            parts = asset_str.split(":")
            if len(parts) != 2:
                return None
            stmt = select(Asset).where(Asset.code == parts[0], Asset.issuer == parts[1])

        result = await session.execute(stmt)
        return result.scalar_one_or_none()
