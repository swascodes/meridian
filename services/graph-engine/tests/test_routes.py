"""Tests for Graph API Routes."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.graph.manager import GraphManager
from app.graph.builder import GraphBuilder


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def mock_manager():
    manager = GraphManager()
    builder = manager.builder
    
    # Add dummy assets
    builder.graph.add_node(
        "asset:xlm", 
        node_type="asset", 
        code="XLM", 
        issuer=None, 
        trustlines=1000, 
        volume_24h=50000.0
    )
    builder.graph.add_node(
        "asset:usdc", 
        node_type="asset", 
        code="USDC", 
        issuer="GA5Z...", 
        trustlines=500, 
        volume_24h=10000.0
    )
    
    # Add dummy pool
    builder.graph.add_node(
        "pool:123", 
        node_type="pool", 
        pool_id="123", 
        reserve_a=1000.0, 
        reserve_b=2000.0, 
        total_shares=500.0, 
        fee_bp=30
    )
    
    # Add edges
    builder.graph.add_edge("asset:xlm", "pool:123", weight=1.0)
    builder.graph.add_edge("pool:123", "asset:usdc", weight=1.0)
    
    return manager


def test_get_stats(client, app, mock_manager):
    app.state.graph_manager = mock_manager
    response = client.get("/v1/graph/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total_assets"] == 2
    assert data["total_pools"] == 1
    assert data["total_nodes"] == 3


def test_get_assets(client, app, mock_manager):
    app.state.graph_manager = mock_manager
    response = client.get("/v1/graph/assets")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2
    assert len(data["assets"]) == 2
    assert data["assets"][0]["code"] == "XLM"  # Should be sorted by trustlines


def test_get_pools(client, app, mock_manager):
    app.state.graph_manager = mock_manager
    response = client.get("/v1/graph/pools")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert len(data["pools"]) == 1
    assert data["pools"][0]["pool_id"] == "123"
