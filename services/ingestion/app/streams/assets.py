"""Asset discovery stream — discovers new assets on Stellar."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import structlog
from sqlalchemy import select

from meridian_shared.config import get_settings
from meridian_shared.db import Asset, get_session
from meridian_shared.stellar import get_horizon_client

logger = structlog.get_logger()


class AssetDiscoveryStream:
    """Periodically discovers new assets from Stellar Horizon."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._running = True

    async def run(self) -> None:
        """Main discovery loop."""
        while self._running:
            try:
                await self._discover_assets()
                await asyncio.sleep(self.settings.ingestion_asset_discovery_interval)
            except asyncio.CancelledError:
                logger.info("asset_discovery_cancelled")
                break
            except Exception as e:
                logger.error("asset_discovery_error", error=str(e))
                await asyncio.sleep(30)

    async def _discover_assets(self) -> None:
        """Fetch top assets from Horizon."""
        server = get_horizon_client()

        try:
            # Ensure XLM native is always present
            await self._ensure_native_asset()

            # Fetch assets ordered by number of accounts
            response = server.assets().limit(200).order(desc=True).call()
            records = response.get("_embedded", {}).get("records", [])

            new_count = 0
            async with get_session() as session:
                for record in records:
                    code = record.get("asset_code", "")
                    issuer = record.get("asset_issuer", "")
                    asset_type = record.get("asset_type", "")

                    # Check if exists
                    stmt = select(Asset).where(Asset.code == code, Asset.issuer == issuer)
                    result = await session.execute(stmt)
                    existing = result.scalar_one_or_none()

                    if existing:
                        # Update stats
                        existing.total_trustlines = int(record.get("num_accounts", 0))
                        existing.last_seen_at = datetime.now(timezone.utc)
                    else:
                        asset = Asset(
                            code=code,
                            issuer=issuer,
                            asset_type=asset_type,
                            total_trustlines=int(record.get("num_accounts", 0)),
                            first_seen_at=datetime.now(timezone.utc),
                            last_seen_at=datetime.now(timezone.utc),
                        )
                        session.add(asset)
                        new_count += 1

            logger.info("asset_discovery_complete", total=len(records), new=new_count)

        except Exception as e:
            logger.error("asset_fetch_error", error=str(e))

    async def _ensure_native_asset(self) -> None:
        """Ensure XLM native asset exists."""
        async with get_session() as session:
            stmt = select(Asset).where(Asset.code == "XLM", Asset.issuer.is_(None))
            result = await session.execute(stmt)
            if not result.scalar_one_or_none():
                session.add(Asset(
                    code="XLM",
                    issuer=None,
                    asset_type="native",
                    is_verified=True,
                    domain="stellar.org",
                ))
