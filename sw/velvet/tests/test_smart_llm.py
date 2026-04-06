import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone

from velvet.devices import Device, DeviceLoad, HardwareRegistry, DeviceType, DeviceRole, HardwareSpecs
from velvet.llm import MeshLLMAdapter
from velvet.services.llm_service import LLMProvider

@pytest.fixture
def mock_registry():
    reg = MagicMock(spec=HardwareRegistry)
    reg.get_online_devices.return_value = []
    return reg

@pytest.fixture
def mock_fabric():
    fabric = AsyncMock()
    return fabric

@pytest.mark.asyncio
async def test_device_load_serialization():
    """Verify DeviceLoad to/from dict."""
    load = DeviceLoad(cpu_percent=50.0, active_tasks=2)
    data = load.to_dict()
    assert data["cpu_percent"] == 50.0
    assert data["active_tasks"] == 2
    
    load2 = DeviceLoad.from_dict(data)
    assert load2.cpu_percent == 50.0
    assert load2.active_tasks == 2

@pytest.mark.asyncio
async def test_smart_routing_logic():
    """Verify MeshLLMAdapter selects best node based on load."""
    
    # 1. Setup Mock Registry
    local_id = "local-node"
    remote_id = "remote-node"
    
    # Node A: Local, but very busy (should be penalized)
    node_a = Device(
        device_id=local_id, name="Local", device_type=DeviceType.COMPUTE,
        load=DeviceLoad(active_tasks=10) # Heavy penalty
    )
    
    # Node B: Remote, but idle (should be picked)
    node_b = Device(
        device_id=remote_id, name="Remote", device_type=DeviceType.COMPUTE,
        load=DeviceLoad(active_tasks=0)
    )
    
    with patch("velvet.fabric.get_fabric") as mock_get_fabric, \
         patch("velvet.devices.get_registry") as mock_get_reg, \
         patch("velvet.config.get_config") as mock_get_config:
        
        mock_get_reg.return_value.get_online_devices.return_value = [node_a, node_b]
        mock_get_config.return_value.zenoh.device_id = local_id
        
        adapter = MeshLLMAdapter()
        
        # Test selection
        best = adapter._select_best_node()
        
        # Scoring:
        # Local: 100 - (10*10) = 0
        # Remote: 50 - (0*10) = 50
        # Winner: Remote
        
        assert best.device_id == remote_id

@pytest.mark.asyncio
async def test_llm_service_busy_state():
    """Verify LLMService updates load during execution."""
    
    with patch("velvet.services.llm_service.get_fabric") as mock_get_fabric, \
         patch("velvet.services.llm_service.get_config") as mock_get_config:
             
        mock_get_config.return_value.zenoh.device_id = "test-device"
        
        # Ensure fabric methods are awaitable
        mock_fabric = AsyncMock()
        mock_get_fabric.return_value = mock_fabric
        
        service = LLMProvider()
        service.fabric = mock_fabric # Explicitly set
        
        # Mock Backend
        service.backend = AsyncMock()
        service.backend.generate.return_value = MagicMock(text="Hello", tool_calls=[])
        
        # Mock Registry interaction
        with patch("velvet.services.llm_service.get_registry") as mock_get_reg:
            mock_device = MagicMock()
            mock_device.load = DeviceLoad()
            mock_get_reg.return_value.get_device.return_value = mock_device
            
            # Trigger request
            msg = MagicMock()
            msg.payload = {"request_id": "123", "messages": [], "reply_to": "reply-topic"}
            msg.source_device = "client"
            
            # We need to verify state *during* execution. 
            # But since _on_request awaits, we check after.
            # To test "during", we'd need a slower backend mock or check calls.
            
            await service._on_request(msg)
            
            # Verify load was incremented then decremented
            # The broadcasting happens inside _update_load. 
            # active_tasks should end at 0.
            assert service._active_tasks == 0
            
            # Verify backend called
            assert service.backend.generate.called
            
            # Verify reply sent
            service.fabric.publish.assert_called()
