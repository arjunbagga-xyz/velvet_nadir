import os
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

# Set required env vars for testing BEFORE config loading
os.environ["VELVET_SECURITY_MESH_SECRET"] = "test-secret-key-123"

from velvet.devices import Device, DeviceType, DeviceRole, TrustLevel
from velvet.fabric import MessageType

@pytest.fixture
def mock_fabric():
    """Mock the Zenoh fabric for isolated testing."""
    mock = AsyncMock()
    mock.publish = AsyncMock()
    mock.subscribe = AsyncMock()
    
    # Simple pub/sub mechanism for testing interaction
    subscribers = {}
    
    async def subscribe(topic, handler):
        if topic not in subscribers:
            subscribers[topic] = []
        subscribers[topic].append(handler)
        
    async def publish(topic, payload, correlation_id=None):
        handlers = subscribers.get(topic, [])
        for handler in handlers:
            msg = MagicMock()
            msg.payload = payload
            msg.msg_type = topic
            msg.source_device = "test_source"
            await handler(msg)
            
    mock.subscribe.side_effect = subscribe
    mock.publish.side_effect = publish
    return mock

@pytest.fixture
def mock_llm():
    """Mock LLM adapter that returns canned responses."""
    mock = AsyncMock()
    mock.generate = AsyncMock()
    mock.generate.return_value.text = "This is a mock LLM response."
    return mock

@pytest.fixture
def mock_registry():
    """Mock Hardware Registry with some sample devices."""
    mock = AsyncMock()
    mock.get_device.return_value = Device(
        device_id="test_device",
        name="Test Device",
        device_type=DeviceType.COMPUTE,
        role=DeviceRole.HOST,
        initial_trust_level=TrustLevel.TRUSTED
    )
    return mock


