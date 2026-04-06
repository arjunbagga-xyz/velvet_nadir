"""
Tests for Jing (Memory) Integration.
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import sys

# Mock powermem module before importing Jing
mock_powermem_module = MagicMock()
sys.modules["powermem"] = mock_powermem_module

from velvet.shen.jing import Jing
from velvet.config import get_config

@pytest.fixture
def mock_powermem():
    """Mock the PowerMem instance creation."""
    mock_instance = MagicMock()
    mock_powermem_module.create_memory.return_value = mock_instance
    return mock_instance

def test_jing_initialization(mock_powermem):
    """Jing should initialize PowerMemory via create_memory."""
    # We need to mock get_polymath as well because Jing calls it
    with patch("velvet.shen.polymath.get_polymath") as mock_poly_get:
        mock_poly = MagicMock()
        mock_poly.build_memory_config.return_value = {"mock": "config"}
        mock_poly_get.return_value = mock_poly
        
        jing = Jing()
        
        mock_powermem_module.create_memory.assert_called()
        assert jing._mem == mock_powermem

@pytest.mark.asyncio
async def test_jing_recall(mock_powermem):
    """Jing.recall should route to PowerMemory.search."""
    mock_powermem.search.return_value = {
        "results": [{"memory": "memory1"}, {"memory": "memory2"}]
    }
    
    # Mock get_polymath to avoid real hardware probe
    with patch("velvet.shen.polymath.get_polymath"):
        jing = Jing()
        results = await jing.recall("test query", limit=5)
        
        mock_powermem.search.assert_called_once_with("test query", limit=5)
        assert results == ["memory1", "memory2"]

@pytest.mark.asyncio
async def test_jing_remember(mock_powermem):
    """Jing.remember should route to PowerMemory.add."""
    # Mock get_polymath
    with patch("velvet.shen.polymath.get_polymath"):
        jing = Jing()
        await jing.remember("User likes cats")
        
        # In jing.py: self._mem.add(messages, agent_id="velvet", metadata=extra_meta)
        # messages = [{"role": role, "content": fact}]
        mock_powermem.add.assert_called_once_with(
            [{"role": "user", "content": "User likes cats"}],
            agent_id="velvet",
            metadata={}
        )
