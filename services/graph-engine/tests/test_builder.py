"""Tests for graph builder."""

import pytest

from app.graph.builder import GraphBuilder


def test_asset_node_id_deterministic():
    """Node IDs should be deterministic for same input."""
    id1 = GraphBuilder._asset_node_id("XLM", None)
    id2 = GraphBuilder._asset_node_id("XLM", None)
    assert id1 == id2
    assert id1.startswith("asset:")


def test_asset_node_id_different_for_different_assets():
    """Different assets should have different node IDs."""
    xlm_id = GraphBuilder._asset_node_id("XLM", None)
    usdc_id = GraphBuilder._asset_node_id("USDC", "GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN")
    assert xlm_id != usdc_id


def test_empty_graph_paths():
    """Finding paths in empty graph should return empty list."""
    builder = GraphBuilder()
    paths = builder.find_paths("XLM", None, "USDC", "SOME_ISSUER")
    assert paths == []


def test_empty_graph_stats():
    """Empty graph stats should have zero values."""
    builder = GraphBuilder()
    stats = builder.get_stats()
    assert stats["total_nodes"] == 0
    assert stats["total_edges"] == 0
