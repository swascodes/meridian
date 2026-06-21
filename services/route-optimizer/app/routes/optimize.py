"""Optimization API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from meridian_shared.models import (
    AssetIdentifier,
    RouteResult,
    RouteSimulationRequest,
    RouteSimulationResult,
)
from meridian_shared.stellar import parse_asset_identifier

from app.optimizer.engine import OptimizationEngine

router = APIRouter()
engine = OptimizationEngine()


@router.get("/routes/{source}/{destination}", response_model=list[RouteResult])
async def find_optimal_routes(
    source: str,
    destination: str,
    amount: float = 100.0,
    max_hops: int = 4,
    max_results: int = 5,
) -> list[RouteResult]:
    """Find optimal routes between two assets."""
    try:
        source_code, source_issuer = parse_asset_identifier(source)
        dest_code, dest_issuer = parse_asset_identifier(destination)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    results = await engine.find_optimal_routes(
        source=AssetIdentifier(code=source_code, issuer=source_issuer),
        destination=AssetIdentifier(code=dest_code, issuer=dest_issuer),
        amount=amount,
        max_hops=max_hops,
        max_results=max_results,
    )
    return results


@router.post("/simulate", response_model=RouteSimulationResult)
async def simulate_route(request: RouteSimulationRequest) -> RouteSimulationResult:
    """Simulate route execution with specific amount."""
    results = await engine.find_optimal_routes(
        source=request.source_asset,
        destination=request.destination_asset,
        amount=request.amount,
        max_hops=request.max_hops,
        max_results=1,
    )

    if not results:
        raise HTTPException(status_code=404, detail="No routes found")

    best = results[0]
    return RouteSimulationResult(
        route=best,
        input_amount=request.amount,
        expected_output=request.amount * best.estimated_rate,
        estimated_slippage=best.estimated_slippage,
        price_impact=best.estimated_slippage * 100,
        execution_probability=0.95 if best.estimated_slippage < 0.01 else 0.85,
        warnings=_generate_warnings(best, request),
    )


def _generate_warnings(route: RouteResult, request: RouteSimulationRequest) -> list[str]:
    """Generate warnings for a simulation result."""
    warnings = []
    if route.estimated_slippage > request.slippage_tolerance:
        warnings.append(f"Estimated slippage ({route.estimated_slippage:.2%}) exceeds tolerance ({request.slippage_tolerance:.2%})")
    if route.hop_count > 3:
        warnings.append(f"Route has {route.hop_count} hops — higher execution risk")
    if route.total_liquidity < request.amount * 10:
        warnings.append("Low liquidity relative to trade size")
    return warnings
