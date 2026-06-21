"""Soroban registry endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from meridian_shared.db import RegisteredRoute, Route, get_session_dep
from meridian_shared.models import RegistryEntry, RegistryPublishRequest

router = APIRouter()


@router.post("/publish", response_model=RegistryEntry)
async def publish_route(
    request: RegistryPublishRequest,
    session: AsyncSession = Depends(get_session_dep),
) -> RegistryEntry:
    """Publish a route to the Soroban routing registry."""
    # Verify route exists
    stmt = select(Route).where(Route.route_hash == request.route_hash)
    result = await session.execute(stmt)
    route = result.scalar_one_or_none()

    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    # TODO: Actual Soroban contract invocation
    # For Phase 1, we record the intent and return a placeholder
    registered = RegisteredRoute(
        route_id=route.id,
        contract_id="PLACEHOLDER_CONTRACT_ID",
        soroban_tx_hash="PLACEHOLDER_TX_HASH",
        on_chain_score=request.quality_score,
    )
    session.add(registered)
    await session.flush()

    return RegistryEntry(
        route_hash=request.route_hash,
        contract_id=registered.contract_id,
        soroban_tx_hash=registered.soroban_tx_hash,
        quality_score=registered.on_chain_score,
        registered_at=registered.registered_at,
        last_updated_at=registered.last_updated_at,
        is_active=registered.is_active,
    )


@router.get("/{route_hash}", response_model=RegistryEntry | None)
async def get_registered_route(
    route_hash: str,
    session: AsyncSession = Depends(get_session_dep),
) -> RegistryEntry | None:
    """Get on-chain registry entry for a route."""
    stmt = (
        select(RegisteredRoute)
        .join(Route)
        .where(Route.route_hash == route_hash, RegisteredRoute.is_active == True)  # noqa: E712
        .order_by(RegisteredRoute.registered_at.desc())
    )
    result = await session.execute(stmt)
    entry = result.scalar_one_or_none()

    if not entry:
        return None

    return RegistryEntry(
        route_hash=route_hash,
        contract_id=entry.contract_id,
        soroban_tx_hash=entry.soroban_tx_hash,
        quality_score=entry.on_chain_score,
        registered_at=entry.registered_at,
        last_updated_at=entry.last_updated_at,
        is_active=entry.is_active,
    )
