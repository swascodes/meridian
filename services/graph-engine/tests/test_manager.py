"""Tests for GraphManager cache and resilience behavior."""

import pickle
from unittest.mock import AsyncMock, patch

import networkx as nx
import pytest

from app.graph.manager import GraphManager
from meridian_shared.redis import RedisKeys


@pytest.fixture
def empty_manager():
    return GraphManager()


@pytest.mark.asyncio
async def test_load_from_cache_empty(empty_manager):
    """Test loading from empty cache."""
    with patch("app.graph.manager.get_redis_binary") as mock_redis_bin:
        mock_redis_bin.return_value.get = AsyncMock(return_value=None)
        
        result = await empty_manager._load_from_cache()
        assert result is False


@pytest.mark.asyncio
async def test_load_from_cache_valid(empty_manager):
    """Test loading valid serialized graph."""
    g = nx.DiGraph()
    g.add_node("A")
    g.add_node("B")
    g.add_edge("A", "B", weight=1.0)
    
    graph_bytes = pickle.dumps(g)
    
    with patch("app.graph.manager.get_redis_binary") as mock_redis_bin:
        mock_redis_bin.return_value.get = AsyncMock(return_value=graph_bytes)
        
        result = await empty_manager._load_from_cache()
        assert result is True
        assert empty_manager.builder.graph is not None
        assert empty_manager.builder.graph.number_of_nodes() == 2


@pytest.mark.asyncio
async def test_load_from_cache_corrupted(empty_manager):
    """Test loading corrupted bytes."""
    corrupted_bytes = b"not a valid pickle payload"
    
    with patch("app.graph.manager.get_redis_binary") as mock_redis_bin:
        mock_redis_bin.return_value.get = AsyncMock(return_value=corrupted_bytes)
        
        result = await empty_manager._load_from_cache()
        assert result is False


@pytest.mark.asyncio
async def test_load_from_cache_redis_unavailable(empty_manager):
    """Test behavior when Redis connection fails."""
    with patch("app.graph.manager.get_redis_binary") as mock_redis_bin:
        mock_redis_bin.return_value.get.side_effect = Exception("Redis connection error")
        
        result = await empty_manager._load_from_cache()
        assert result is False


@pytest.mark.asyncio
async def test_initialize_resilience(empty_manager):
    """Test initialization fallback to empty graph on total failure."""
    with patch.object(empty_manager, "_load_from_cache", new_callable=AsyncMock) as mock_load:
        with patch.object(empty_manager, "rebuild", new_callable=AsyncMock) as mock_rebuild:
            mock_load.return_value = False
            mock_rebuild.side_effect = Exception("DB unavailable")
            
            # Should not raise exception
            await empty_manager.initialize()
            
            # Should have an empty graph ready to serve
            assert empty_manager.builder.graph is not None
            assert empty_manager.builder.graph.number_of_nodes() == 0
