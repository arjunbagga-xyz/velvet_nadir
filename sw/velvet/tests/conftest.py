import os
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
import msgpack

# Set required env vars for testing BEFORE config loading
os.environ["VELVET_SECURITY_MESH_SECRET"] = "test-secret-key-123"

from velvet.devices import Device, DeviceType, DeviceRole, TrustLevel
from velvet.fabric import VelvetMessage, MessageType, match_pattern
import velvet.fabric

# ============================================================================
# Loopback Fabric (Replaces MockFabric and ZenohFabric for testing)
# ============================================================================

class LoopbackFabric:
    """
    An in-memory communications fabric that simulates ZenohFabric behavior
    by performing actual msgpack serialization, HMAC signing, and signature verification.
    """
    def __init__(self, device_id: str = "test-device", mode: str = "peer"):
        self.device_id = device_id
        self.mode = mode
        self._subscribers = {}
        self._queryables = {}

    def is_real_zenoh(self) -> bool:
        return False

    async def start(self, **kwargs):
        pass

    async def stop(self):
        pass

    async def subscribe(self, topic: str, handler):
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        self._subscribers[topic].append(handler)

    async def publish(self, topic: str, payload: dict, correlation_id: str | None = None):
        # 1. Create real message
        msg = VelvetMessage(
            msg_type=topic,
            payload=payload,
            source_device=self.device_id,
            correlation_id=correlation_id
        )
        # 2. Serialize message (this tests msgpack packing and HMAC signing if mesh_secret is set)
        data = msg.to_bytes()

        # 3. Route to subscribers matching Zenoh topic patterns
        for pattern, handlers in self._subscribers.items():
            if match_pattern(pattern, topic):
                for handler in handlers:
                    # 4. Deserialize message (this tests msgpack unpacking and HMAC validation)
                    restored_msg = VelvetMessage.from_bytes(data)
                    # Fire-and-forget in event loop to avoid deadlocks
                    asyncio.create_task(handler(restored_msg))

    async def register_query_handler(self, topic: str, handler):
        self._queryables[topic] = handler

    async def request(self, topic: str, payload: dict, timeout_sec: float = 5.0) -> list[VelvetMessage]:
        # 1. Create request message
        msg = VelvetMessage(
            msg_type=topic,
            payload=payload,
            source_device=self.device_id
        )
        # 2. Serialize
        data = msg.to_bytes()

        # 3. Call queryable handler
        handler = self._queryables.get(topic)
        if not handler:
            return []

        restored_msg = VelvetMessage.from_bytes(data)
        resp_payload = await handler(restored_msg)
        if resp_payload is None:
            return []

        # 4. Create and serialize response
        resp_msg = VelvetMessage(
            msg_type=f"{topic}/reply",
            payload=resp_payload,
            source_device="remote-device"
        )
        resp_data = resp_msg.to_bytes()

        # 5. Deserialize response
        restored_resp = VelvetMessage.from_bytes(resp_data)
        return [restored_resp]


@pytest.fixture
def mock_fabric():
    """Installs the LoopbackFabric as the global fabric singleton."""
    loopback = LoopbackFabric(device_id="test-device")
    original_fabric = velvet.fabric._fabric
    velvet.fabric._fabric = loopback
    yield loopback
    velvet.fabric._fabric = original_fabric


# ============================================================================
# Realistic LLM Response Dataset and Mocks
# ============================================================================

@pytest.fixture
def realistic_llm_responses():
    """Returns a dictionary of realistic raw LLM outputs."""
    return {
        "single_tool": 'Use Tool: {"tool": "get_time", "params": {}}',
        "multi_tool": '[{"name": "list_devices"}, {"name": "remember", "arguments": {"key": "hobby", "value": "painting"}}]',
        "markdown_json": '```json\n{\n  "tool": "system_status",\n  "params": {}\n}\n```',
        "malformed_json": 'Use Tool: {"tool": "get_weather", "params": {"location": "London"} (missing brace)',
        "plain_text": "Hello! I am Velvet Nadir, your personal AI assistant. How can I help you today?",
    }


@pytest.fixture
def mock_llm():
    """Mock LLM adapter that can return canned or custom responses."""
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
