"""Tests for route simulator."""

import pytest

from app.optimizer.simulator import RouteSimulator


@pytest.fixture
def simulator():
    return RouteSimulator()


def test_execute_against_orderbook():
    """Test orderbook execution simulation."""
    sim = RouteSimulator()
    orderbook = {
        "asks": [
            {"price": 1.0, "amount": 100},
            {"price": 1.01, "amount": 200},
            {"price": 1.02, "amount": 300},
        ],
        "spread": 0.01,
    }

    result = sim._execute_against_orderbook(orderbook, 50)

    assert result["output_amount"] > 0
    assert result["slippage"] >= 0
    assert result["liquidity"] > 0


def test_estimate_amm_execution():
    """Test AMM constant-product execution estimate."""
    sim = RouteSimulator()
    source = {"code": "XLM"}
    dest = {"code": "USDC", "reserve_a": 10000, "reserve_b": 10000, "fee_bp": 30}

    result = sim._estimate_amm_execution(source, dest, 100)

    assert result["output_amount"] > 0
    assert result["output_amount"] < 100  # Some slippage expected
    assert result["slippage"] > 0


def test_estimate_default():
    """Default estimation should apply 0.5% cost."""
    sim = RouteSimulator()
    result = sim._estimate_default(1000)

    assert result["output_amount"] == 995.0
    assert result["slippage"] == 0.005
