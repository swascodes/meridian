"""Asset endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from meridian_shared.db import Asset, get_session_dep
from meridian_shared.models import AssetDetail, AssetType, LiquidityProfile

router = APIRouter()


@router.get("/", response_model=list[AssetDetail])
async def list_assets(
    limit: int = 50,
    offset: int = 0,
    min_volume: float = 0.0,
    session: AsyncSession = Depends(get_session_dep),
) -> list[AssetDetail]:
    """List known assets, ordered by volume."""
    stmt = (
        select(Asset)
        .where(Asset.total_volume_24h >= min_volume)
        .order_by(Asset.total_volume_24h.desc())
        .offset(offset)
        .limit(min(limit, 200))
    )
    result = await session.execute(stmt)
    assets = result.scalars().all()

    return [
        AssetDetail(
            id=a.id,
            code=a.code,
            issuer=a.issuer,
            asset_type=AssetType(a.asset_type),
            domain=a.domain,
            is_verified=a.is_verified,
            total_trustlines=a.total_trustlines,
            total_volume_24h=a.total_volume_24h,
            first_seen_at=a.first_seen_at,
            last_seen_at=a.last_seen_at,
        )
        for a in assets
    ]


@router.get("/{code}/liquidity", response_model=LiquidityProfile)
async def asset_liquidity(
    code: str,
    issuer: str | None = None,
    session: AsyncSession = Depends(get_session_dep),
) -> LiquidityProfile:
    """Get liquidity profile for an asset."""
    from meridian_shared.models import AssetIdentifier

    if code.upper() == "XLM":
        stmt = select(Asset).where(Asset.code == "XLM", Asset.issuer.is_(None))
    else:
        if not issuer:
            raise HTTPException(status_code=400, detail="Issuer required for non-native assets")
        stmt = select(Asset).where(Asset.code == code, Asset.issuer == issuer)

    result = await session.execute(stmt)
    asset = result.scalar_one_or_none()

    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    # TODO: Compute from orderbooks + pools
    return LiquidityProfile(
        asset=AssetIdentifier(code=asset.code, issuer=asset.issuer),
        total_orderbook_depth=0.0,
        total_pool_reserves=0.0,
        num_trading_pairs=0,
        num_pools=0,
        avg_spread=0.0,
        volume_24h=asset.total_volume_24h,
    )
