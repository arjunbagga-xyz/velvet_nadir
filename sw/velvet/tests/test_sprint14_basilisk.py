"""
Verification tests for Sprint 14 Phase 1: The Basilisk Protocol.
Tests memory isolation, sanitization, and P2P RPC auth skills.
"""

import pytest
import numpy as np
import asyncio
import gc
from unittest.mock import AsyncMock, patch, MagicMock

from velvet.basilisk import BasiliskEnclave, sanitize_for_hun
from velvet.skills.basilisk_skill import basilisk_authenticate, basilisk_query
from velvet.fabric import VelvetMessage, MessageType

@pytest.mark.asyncio
async def test_basilisk_enclave_cleanup():
    """Verify that objects tracked in the enclave are referenced 0 times after exit."""
    
    class LargeBlob:
        def __init__(self):
            self.data = np.zeros(1000)
            
    blob = LargeBlob()
    
    async with BasiliskEnclave("test_cleanup") as enclave:
        enclave.track(blob)
        assert len(enclave._tracked_refs) == 1
        # Manual check that it's the same object
        assert enclave._tracked_refs[0] is blob
        
    # After exit, enclave._tracked_refs is cleared and gc.collect() called
    assert len(enclave._tracked_refs) == 0
    # blob still exists in THIS scope, but we verified the enclave dropped its ref.


@pytest.mark.asyncio
async def test_sanitize_for_hun():
    """Verify that raw tensors are stripped but other structure is preserved."""
    raw_payload = {
        "verified": True,
        "identity": "owner",
        "face_embedding": np.random.rand(512),
        "frame": np.random.rand(100, 100, 3),
        "nested": {
            "score": 0.99,
            "tensor_data": [1.0, 2.0, 3.0] # Not a numpy array but key-based match
        }
    }
    
    safe = sanitize_for_hun(raw_payload)
    
    assert safe["verified"] is True
    assert safe["identity"] == "owner"
    assert "face_embedding" in safe
    assert "BASILISK_STRIPPED" in str(safe["face_embedding"])
    assert "BASILISK_STRIPPED" in str(safe["frame"])
    assert safe["nested"]["score"] == 0.99
    assert safe["nested"]["tensor_data"] == "<BASILISK_STRIPPED:list>"


@pytest.mark.asyncio
async def test_basilisk_authenticate_skill_success():
    """Test the basilisk_authenticate skill logic from request to local auth pipe."""
    
    mock_fabric = MagicMock()
    mock_fabric.request = AsyncMock()
    
    # 1. First request to device: returns a frame (mocked as dict)
    device_response = VelvetMessage(
        msg_type="mesh/device/cam1/capture_basilisk",
        payload={"frame": np.zeros(100), "source": "cam1"},
        source_device="cam1"
    )
    
    # 2. Second request to local TrustGate: returns verification boolean
    gate_response = VelvetMessage(
        msg_type=MessageType.BASILISK_AUTH.value,
        payload={"verified": True, "node_id": "gateway"},
        source_device="gateway"
    )
    
    mock_fabric.request.side_effect = [[device_response], [gate_response]]
    
    with patch("velvet.skills.basilisk_skill.get_fabric", return_value=mock_fabric):
        result = await basilisk_authenticate(device_id="cam1")
        
        assert result.success is True
        assert result.data["verified"] is True
        assert "verified" in result.speak or "authenticated" in result.speak


@pytest.mark.asyncio
async def test_basilisk_query_skill_sanitization():
    """Verify that basilisk_query skill sanitizes its output for the LLM."""
    
    mock_fabric = MagicMock()
    mock_fabric.request = AsyncMock()
    
    # Mock some sensitive response from a device
    raw_response = {
        "status": "ok",
        "biometrics": [0.1, 0.2, 0.3],
        "log": "Access granted"
    }
    
    device_msg = VelvetMessage(
        msg_type="some/topic",
        payload=raw_response,
        source_device="remote_node"
    )
    
    mock_fabric.request.return_value = [device_msg]
    
    with patch("velvet.skills.basilisk_skill.get_fabric", return_value=mock_fabric):
        # Even if the dev returns raw biometrics
        result = await basilisk_query(topic="some/topic", payload={"cmd": "get_secrets"})
        
        assert result.success is True
        # result.data should be sanitized
        assert result.data["status"] == "ok"
        assert result.data["biometrics"] == "<BASILISK_STRIPPED:list>"
        assert result.data["log"] == "Access granted"
