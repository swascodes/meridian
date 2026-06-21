"""Tests for shared models."""

import pytest
from datetime import datetime, timezone

from meridian_shared.models import (
    AssetIdentifier,
    RouteSimulationRequest,
    QualityBreakdown,
    ServiceHealth,
)


def test_asset_identifier_native():
    asset = AssetIdentifier(code="XLM", issuer=None)
    assert asset.canonical == "native"


def test_asset_identifier_credit():
    asset = AssetIdentifier(code="USDC", issuer="GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN")
    assert asset.canonical == "USDC:GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN"


def test_simulation_request_validation():
    req = RouteSimulationRequest(
        source_asset=AssetIdentifier(code="XLM", issuer=None),
        destination_asset=AssetIdentifier(code="USDC", issuer="GA5Z"),
        amount=100.0,
    )
    assert req.max_hops == 4
    assert req.slippage_tolerance == 0.01


def test_quality_breakdown_bounds():
    breakdown = QualityBreakdown(
        liquidity_score=0.9,
        reliability_score=0.85,
        speed_score=0.7,
        cost_score=0.8,
        slippage_score=0.95,
    )
    assert all(0 <= getattr(breakdown, f) <= 1 for f in breakdown.model_fields)


def test_service_health():
    health = ServiceHealth(
        service="test",
        status="healthy",
        timestamp=datetime.now(timezone.utc),
    )
    assert health.version == "0.1.0"
