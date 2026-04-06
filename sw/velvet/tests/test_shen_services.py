"""
Integration Tests for Shen Services (Yi/Po/Hun).
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path

from velvet.shen.yi import Yi
from velvet.shen.po import Po
from velvet.shen.hun import Hun
from velvet.shen.polymath import InferenceBackend

# Mock Config to ensure paths exist (logically)
@pytest.fixture
def mock_config():
    with patch("velvet.shen.po.get_config") as mock_conf_po, \
         patch("velvet.shen.hun.get_config") as mock_conf_hun, \
         patch("velvet.shen.yi.get_config") as mock_conf_yi:
         
        # Create a mock config object
        conf = MagicMock()
        conf.shen.po_reflex_model = MagicMock()
        conf.shen.po_reflex_model.exists.return_value = True
        
        conf.shen.hun_reasoning_model = MagicMock()
        conf.shen.hun_reasoning_model.exists.return_value = True

        mock_conf_po.return_value = conf
        mock_conf_hun.return_value = conf
        mock_conf_yi.return_value = conf
        yield conf

# Mock Polymath/Vision components
@pytest.fixture
def mock_inference():
    """Mock the LLM inference function for Yi/Hun."""
    mock = AsyncMock()
    mock.return_value = "Deep Thought Computed"
    return mock

@pytest.fixture
def mock_vision():
    """Mock VisionEngine for Po."""
    with patch("velvet.shen.po.VisionEngine") as mock_cls:
        instance = MagicMock()
        mock_adapter = AsyncMock()
        mock_adapter.generate.return_value.text = "Reflex Action Triggered"
        instance.adapter = mock_adapter
        mock_cls.return_value = instance
        yield instance

# Mock Jing to avoid DB calls
@pytest.fixture
def mock_jing():
    with patch("velvet.shen.yi.Jing") as mock_jing_cls:
        jing_instance = AsyncMock()
        jing_instance.recall.return_value = ["Previous context item"]
        mock_jing_cls.return_value = jing_instance
        yield jing_instance

@pytest.mark.asyncio
async def test_yi_dispatch_reflex(mock_config, mock_inference, mock_vision, mock_jing, mock_fabric):
    """Yi should route short commands to Po."""
    # Patch get_fabric to return our mock_fabric
    with patch("velvet.shen.po.get_fabric", return_value=mock_fabric):
        yi = Yi(llm_inference=mock_inference)
        
        # "turn on lights" is short -> Regex Reflex in Po
        response = await yi.dispatch("turn on lights")
        
        assert "Turning on" in response
    
@pytest.mark.asyncio
async def test_yi_dispatch_reasoning(mock_config, mock_inference, mock_vision, mock_jing, mock_fabric):
    """Yi should route complex commands to Hun."""
    with patch("velvet.shen.po.get_fabric", return_value=mock_fabric):
        yi = Yi(llm_inference=mock_inference)
        
        # Long query -> Reasoning in Hun
        long_query = "explain the theory of relativity and how it relates to time dilation in simple terms"
        response = await yi.dispatch(long_query)
        
        assert "Deep Thought" in response
        mock_inference.assert_called_once()
