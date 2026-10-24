import pytest
import json
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from velvet.models import ModelRegistry, ModelInfo, ModelType, ModelFormat, get_model_registry
from velvet.credentials import get_credential_pool
from velvet.skills.cua_skill import CUASandboxSkill
from velvet.limen import LimenGateway


class MockResponse:
    def __init__(self, json_data, status):
        self._json_data = json_data
        self.status = status

    async def json(self):
        return self._json_data

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.fixture
def clean_registry():
    """Create a clean ModelRegistry."""
    # Temporarily reset registry benchmarks for testing
    reg = ModelRegistry()
    reg.benchmarks = {
        "text": {
            "gpt-4o": 1286,
            "gemini-1.5-pro": 1262,
            "llama-3-8b-instruct": 1150
        },
        "code": {
            "claude-3-5-sonnet": 1325,
            "gpt-4o": 1310,
            "gemini-1.5-pro": 1280
        }
    }
    return reg


@pytest.mark.asyncio
async def test_online_benchmark_fetching(clean_registry):
    """Test crawling api.wulong.dev successfully updates benchmarks."""
    mock_data = [
        {"model": "gpt-4o", "rating": 1350},
        {"model": "claude-3-5-sonnet", "rating": 1340}
    ]
    
    # Mock aiohttp client session GET call
    mock_session = MagicMock()
    mock_session.__aenter__.return_value = mock_session
    mock_session.get = MagicMock(return_value=MockResponse(mock_data, 200))
    
    with patch("aiohttp.ClientSession", return_value=mock_session):
        await clean_registry.fetch_online_benchmarks()
        
        # Verify text category ELO score was updated
        assert clean_registry.benchmarks["text"]["gpt-4o"] == 1350
        assert clean_registry.benchmarks["text"]["claude-3-5-sonnet"] == 1340


def test_specialization_score_multiplier_routing(clean_registry):
    """Verify that ELO scores skew routing candidates toward specialized models."""
    gpt_info = ModelInfo(
        model_id="gpt-4o",
        name="GPT-4o",
        model_type=ModelType.LLM,
        format=ModelFormat.OTHER,
        capabilities=["chat", "code"],
        context_length=8192
    )
    
    llama_info = ModelInfo(
        model_id="llama-3-8b-instruct",
        name="Llama 3 8B",
        model_type=ModelType.LLM,
        format=ModelFormat.GGUF,
        capabilities=["chat", "code"],
        context_length=4096
    )
    
    # We mock device registry check inside best_device_for
    mock_device = MagicMock()
    mock_device.is_online.return_value = True
    
    mock_device_registry = MagicMock()
    mock_device_registry.get_device.return_value = mock_device
    
    with patch("velvet.devices.get_registry", return_value=mock_device_registry):
        # Register both models on same device with 0 utilization
        # Under normal conditions, they have same utilization. But ELO score multiplier should prioritize GPT-4o
        asyncio.run(clean_registry.register_model("device_alpha", gpt_info))
        asyncio.run(clean_registry.register_model("device_alpha", llama_info))
        
        # 1. Routing for general "text" capability
        res = asyncio.run(clean_registry.best_device_for(capabilities=["chat"]))
        assert res is not None
        # GPT-4o (1286 ELO) is chosen over Llama 3 (1150 ELO) due to higher score multiplier
        assert res[1] == "gpt-4o"
        
        # 2. Routing for "code" capability (GPT-4o = 1310 ELO)
        res_code = asyncio.run(clean_registry.best_device_for(capabilities=["chat", "code"]))
        assert res_code is not None
        assert res_code[1] == "gpt-4o"


@pytest.mark.asyncio
async def test_fallback_broadcasts_and_upgrades():
    """Verify fallback and upgrades trigger Zenoh model announcements."""
    pool = get_credential_pool()
    
    mock_fabric = AsyncMock()
    with patch("velvet.fabric.get_fabric", return_value=mock_fabric):
        # 1. Trigger local fallback
        pool.adapt_to_local_fallback()
        await asyncio.sleep(0.1)  # allow task schedule to execute
        
        # Assert model capability announce was published
        assert mock_fabric.publish.called
        args, kwargs = mock_fabric.publish.call_args_list[0]
        assert args[0] == "velvet/mesh/model/announce"
        assert args[1]["model"]["model_id"] == "llama3.1:8b"
        
        # 2. Trigger recovery upgrade announcement
        mock_fabric.publish.reset_mock()
        pool.recover_from_fallback("google", "gemini-1.5-pro")
        await asyncio.sleep(0.1)
        
        assert mock_fabric.publish.called
        args, kwargs = mock_fabric.publish.call_args_list[0]
        assert args[0] == "velvet/mesh/model/announce"
        assert args[1]["model"]["model_id"] == "gemini-1.5-pro"


@pytest.mark.asyncio
async def test_mcp_capabilities_dynamic_announcements():
    """Verify that LimenGateway registers and publishes MCP capability announcements."""
    gateway = LimenGateway()
    mock_fabric = AsyncMock()
    
    with patch("velvet.fabric.get_fabric", return_value=mock_fabric):
        mock_tools = [
            {"name": "fetch_logs", "description": "Fetches system logs", "parameters": {"type": "object", "properties": {}}}
        ]
        # Dynamically import schemas
        gateway._import_tool_schemas("log_server", mock_tools)
        await asyncio.sleep(0.1)
        
        # Assert MCP capability announce was published to Zenoh
        assert mock_fabric.publish.called
        args, kwargs = mock_fabric.publish.call_args_list[0]
        assert args[0] == "velvet/mesh/mcp/announce"
        assert args[1]["server_name"] == "log_server"
        assert "mcp_log_server_fetch_logs" in args[1]["tools"]
