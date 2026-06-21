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
        
        # State tracking
        self.total_pools_seen = 0
        self.total_pools_persisted = 0
        self.last_sync_time = None
        self._cursor = "0"

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
        """Fetch and sync all liquidity pools via pagination."""
        server = get_horizon_client()

        try:
            pages_processed = 0
            pools_discovered = 0
            pools_skipped = 0
            total_created = 0
            total_updated = 0
            
            # Start pagination
            logger.info("pool_sync_starting", cursor=self._cursor)
            call_builder = server.liquidity_pools().limit(200).cursor(self._cursor)

            while True:
                try:
                    response = call_builder.call()
                except Exception as api_err:
                    if "429" in str(api_err):
                        logger.warning("pool_sync_rate_limited", sleeping=5)
                        await asyncio.sleep(5)
                        continue
                    raise
                    
                records = response.get("_embedded", {}).get("records", [])
                if not records:
                    break

                pages_processed += 1
                pools_discovered += len(records)
                
                updated = 0
                created = 0

                async with get_session() as session:
                    for record in records:
                        pool_id = record["id"]
                        self._cursor = record.get("paging_token", self._cursor)
                        
                        reserves = record.get("reserves", [])
                        if len(reserves) != 2:
                            pools_skipped += 1
                            continue

                        # Resolve assets
                        asset_a = await self._resolve_pool_asset(session, reserves[0].get("asset", "native"))
                        asset_b = await self._resolve_pool_asset(session, reserves[1].get("asset", "native"))

                        if not asset_a or not asset_b:
                            pools_skipped += 1
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

                    await session.commit()
                    
                total_created += created
                total_updated += updated
                self.total_pools_seen += len(records)
                self.total_pools_persisted += (created + updated)
                
                # Fetch next page
                call_builder = server.liquidity_pools().cursor(self._cursor).limit(200)

            self.last_sync_time = datetime.now(timezone.utc)

            # Notify graph engine of pool updates
            if total_created > 0 or total_updated > 0:
                redis = get_redis()
                await redis.publish(RedisKeys.CHANNEL_POOL_UPDATE, f"synced:{pools_discovered}")

            logger.info("pool_sync_complete", 
                pages=pages_processed,
                discovered=pools_discovered,
                created=total_created, 
                updated=total_updated,
                skipped=pools_skipped,
                cursor=self._cursor
            )

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
