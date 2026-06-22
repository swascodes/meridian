"""Tests for PathfindingEngine route validation edge cases."""

import pytest
import networkx as nx

from app.pathfinding.engine import PathfindingEngine
from meridian_shared.models import RouteDiscoverRequest, AssetIdentifier

@pytest.fixture
def mock_graph():
    graph = nx.DiGraph()
    # Add XLM node
    xlm_id = "asset:59e51c890e1762c4"  # Dummy hash for XLM:native
    graph.add_node(xlm_id, node_type="asset", code="XLM", issuer=None)
    
    # Add isolated asset
    iso_id = "asset:b56d81432f835fa9"  # Dummy hash for ISO:native
    graph.add_node(iso_id, node_type="asset", code="ISO", issuer=None)
    
    # Add disconnected asset (has edges, but not to XLM)
    disc1_id = "asset:c8d2345e5fa7210b"
    disc2_id = "asset:d1234567890abcde"
    graph.add_node(disc1_id, node_type="asset", code="DISC1", issuer=None)
    graph.add_node(disc2_id, node_type="asset", code="DISC2", issuer=None)
    graph.add_edge(disc1_id, disc2_id, weight=1.0)
    
    # Valid route from XLM to USDC
    usdc_id = "asset:a1234567890abcde"
    pool_id = "pool:999"
    graph.add_node(usdc_id, node_type="asset", code="USDC", issuer="GB...")
    graph.add_node(pool_id, node_type="pool", pool_id="999", reserve_a=1000, reserve_b=1000)
    
    graph.add_edge(xlm_id, pool_id, weight=1.0, reserve_in=1000, reserve_out=1000)
    graph.add_edge(pool_id, usdc_id, weight=1.0, reserve_in=1000, reserve_out=1000)
    
    return graph

def _get_node_id(engine: PathfindingEngine, code: str, issuer: str | None) -> str:
    return engine._node_id(code, issuer)

def test_identical_source_destination(mock_graph):
    engine = PathfindingEngine(mock_graph)
    # Ensure correct node ids are populated
    xlm_id = _get_node_id(engine, "XLM", None)
    mock_graph.add_node(xlm_id, node_type="asset", code="XLM", issuer=None)
    
    req = RouteDiscoverRequest(
        source_asset=AssetIdentifier(code="XLM", issuer=None),
        destination_asset=AssetIdentifier(code="XLM", issuer=None),
        amount=100.0,
    )
    
    res = engine.discover_routes(req)
    assert len(res.routes) == 0
    assert res.failure_reason == "Source and destination assets are identical"

def test_nonexistent_asset(mock_graph):
    engine = PathfindingEngine(mock_graph)
    xlm_id = _get_node_id(engine, "XLM", None)
    mock_graph.add_node(xlm_id, node_type="asset", code="XLM", issuer=None)
    
    req = RouteDiscoverRequest(
        source_asset=AssetIdentifier(code="XLM", issuer=None),
        destination_asset=AssetIdentifier(code="FAKE", issuer="FAKE"),
        amount=100.0,
    )
    
    res = engine.discover_routes(req)
    assert len(res.routes) == 0
    assert res.failure_reason == "Source or destination asset not found in graph"

def test_isolated_asset(mock_graph):
    engine = PathfindingEngine(mock_graph)
    xlm_id = _get_node_id(engine, "XLM", None)
    iso_id = _get_node_id(engine, "ISO", None)
    mock_graph.add_node(xlm_id, node_type="asset", code="XLM", issuer=None)
    mock_graph.add_node(iso_id, node_type="asset", code="ISO", issuer=None)
    
    req = RouteDiscoverRequest(
        source_asset=AssetIdentifier(code="XLM", issuer=None),
        destination_asset=AssetIdentifier(code="ISO", issuer=None),
        amount=100.0,
    )
    
    res = engine.discover_routes(req)
    assert len(res.routes) == 0
    assert res.failure_reason == "Source or destination asset isolated after liquidity pruning" or res.failure_reason == "No valid path found"

def test_disconnected_asset(mock_graph):
    engine = PathfindingEngine(mock_graph)
    xlm_id = _get_node_id(engine, "XLM", None)
    disc1_id = _get_node_id(engine, "DISC1", None)
    mock_graph.add_node(xlm_id, node_type="asset", code="XLM", issuer=None)
    mock_graph.add_node(disc1_id, node_type="asset", code="DISC1", issuer=None)
    
    req = RouteDiscoverRequest(
        source_asset=AssetIdentifier(code="XLM", issuer=None),
        destination_asset=AssetIdentifier(code="DISC1", issuer=None),
        amount=100.0,
    )
    
    res = engine.discover_routes(req)
    assert len(res.routes) == 0
    assert "isolated after liquidity pruning" in res.failure_reason or "No valid path found" in res.failure_reason

def test_valid_pool_route(mock_graph):
    engine = PathfindingEngine(mock_graph)
    xlm_id = _get_node_id(engine, "XLM", None)
    usdc_id = _get_node_id(engine, "USDC", "GB...")
    pool_id = "pool:999"
    
    mock_graph.add_node(xlm_id, node_type="asset", code="XLM", issuer=None)
    mock_graph.add_node(usdc_id, node_type="asset", code="USDC", issuer="GB...")
    mock_graph.add_node(pool_id, node_type="pool", pool_id="999", reserve_a=1000, reserve_b=1000)
    mock_graph.add_edge(xlm_id, pool_id, weight=1.0, reserve_in=1000, reserve_out=1000)
    mock_graph.add_edge(pool_id, usdc_id, weight=1.0, reserve_in=1000, reserve_out=1000)
    
    req = RouteDiscoverRequest(
        source_asset=AssetIdentifier(code="XLM", issuer=None),
        destination_asset=AssetIdentifier(code="USDC", issuer="GB..."),
        amount=10.0,
        simulate=True
    )
    
    res = engine.discover_routes(req)
    assert len(res.routes) > 0
    assert res.routes[0].hop_count == 1
    assert res.failure_reason is None
