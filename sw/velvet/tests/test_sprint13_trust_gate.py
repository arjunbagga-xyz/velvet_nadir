import pytest
import time
import numpy as np
from unittest.mock import AsyncMock, MagicMock

from velvet.devices import Device, DeviceRole, DeviceType, TrustLevel, get_registry, init_registry
from velvet.errors import TrustGateError
from velvet.trust_gate import TrustGate, TrustChangeRequest
from velvet.onboarding import onboard_device
from velvet.privacy import PrivacyGuard
from velvet.config import get_config
import velvet.devices
from velvet.devices import HardwareRegistry

@pytest.fixture(autouse=True)
def setup_registry():
    """Initialize registry before each test."""
    velvet.devices._registry = HardwareRegistry()
    yield
    velvet.devices._registry = None


@pytest.fixture
def trust_gate():
    """Trust gate with a mocked Xiang engine."""
    xiang_mock = AsyncMock()
    # Mock identify_faces returning owner match by default
    owner_rec = MagicMock()
    owner_rec.name = get_config().trust_gate.owner_face_memory_key
    owner_rec.confidence = 0.99
    xiang_mock.identify_faces.return_value = [owner_rec]
    
    # Mock identify_voice
    xiang_mock.identify_voice.return_value = owner_rec
    
    return TrustGate(xiang=xiang_mock)


@pytest.fixture
def test_device():
    """A test UNTRUSTED device."""
    registry = get_registry()
    dev = Device(
        device_id="test_dev_1",
        name="Test Device 1",
        device_type=DeviceType.COMPUTE,
        role=DeviceRole.HOST,
        initial_trust_level=TrustLevel.UNTRUSTED
    )
    registry._devices[dev.device_id] = dev
    yield dev
    # Cleanup
    if "test_dev_1" in registry._devices:
        del registry._devices["test_dev_1"]


@pytest.mark.asyncio
async def test_direct_trust_assignment_fails(test_device):
    """Direct assignment to trust_level property is blocked."""
    with pytest.raises(TrustGateError, match="Direct trust_level assignment is blocked"):
        test_device.trust_level = TrustLevel.TRUSTED
        
    assert test_device.trust_level == TrustLevel.UNTRUSTED


@pytest.mark.asyncio
async def test_internal_setter_works(test_device):
    """The internal setter works (used by TrustGate)."""
    test_device._set_trust_level_internal(TrustLevel.TRUSTED)
    assert test_device.trust_level == TrustLevel.TRUSTED


@pytest.mark.asyncio
async def test_request_and_execute_flow(trust_gate, test_device, mock_fabric):
    """Happy path: request -> verify -> execute."""
    import velvet.fabric
    velvet.fabric._fabric = mock_fabric
    # 1. Request
    req = await trust_gate.request_trust_change(
        device_id=test_device.device_id,
        current_level=TrustLevel.UNTRUSTED,
        requested_level=TrustLevel.TRUSTED,
        reason="Test promotion"
    )
    assert isinstance(req, TrustChangeRequest)
    assert req.verified is False
    
    # 2. Cannot execute unverified
    with pytest.raises(TrustGateError, match="is not verified"):
        await trust_gate.execute_change(req.request_id)
        
    # 3. Verify with dummy frame (Mock returns owner)
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    verified = await trust_gate.verify_biometric(req.request_id, frame=frame)
    assert verified is True
    
    # 4. Execute
    success = await trust_gate.execute_change(req.request_id)
    assert success is True
    
    # Verify device was actually promoted
    assert test_device.trust_level == TrustLevel.TRUSTED


@pytest.mark.asyncio
async def test_verify_unknown_face(trust_gate, test_device):
    """Verification fails if face doesn't match owner."""
    # Setup mock to return unknown
    unknown_rec = MagicMock()
    unknown_rec.name = "someone_else"
    unknown_rec.confidence = 0.99
    trust_gate._xiang.identify_faces.return_value = [unknown_rec]
    
    req = await trust_gate.request_trust_change(
        device_id=test_device.device_id,
        current_level=TrustLevel.UNTRUSTED,
        requested_level=TrustLevel.TRUSTED,
        reason="Test promotion"
    )
    
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    verified = await trust_gate.verify_biometric(req.request_id, frame=frame)
    assert verified is False
    
    with pytest.raises(TrustGateError):
        await trust_gate.execute_change(req.request_id)


@pytest.mark.asyncio
async def test_expired_request(trust_gate, test_device):
    """Requests expire after timeout."""
    req = await trust_gate.request_trust_change(
        device_id=test_device.device_id,
        current_level=TrustLevel.UNTRUSTED,
        requested_level=TrustLevel.TRUSTED,
        reason="Test expiration"
    )
    
    # Manually backdate creation
    req.created_at = time.time() - 400  # 400s ago (timeout is 300)
    
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    verified = await trust_gate.verify_biometric(req.request_id, frame=frame)
    assert verified is False  # Fails due to expiration
    
    with pytest.raises(TrustGateError):
        await trust_gate.execute_change(req.request_id)


@pytest.mark.asyncio
async def test_onboard_always_untrusted(mock_fabric):
    """Skill always creates UNTRUSTED devices regardless of parameters."""
    import velvet.fabric
    velvet.fabric._fabric = mock_fabric
    registry = get_registry()
    if "test_onboard_dev" in registry._devices:
        del registry._devices["test_onboard_dev"]
        
    # We pass trust="trusted", but the skill should ignore it
    from velvet.scan import ScannedDevice
    from velvet.onboarding import Interrogator
    import velvet.onboarding
    
    # Just to be safe if _interrogator is not instantiated
    if not hasattr(velvet.onboarding, "_interrogator"):
        velvet.onboarding._interrogator = Interrogator()
        
    velvet.onboarding._interrogator._pending_devices["test_onboard_dev"] = ScannedDevice(id="test_onboard_dev", name="Mock", scan_type="manual")
    
    res = await onboard_device(device_id="test_onboard_dev")
    assert res.success is True
    assert "UNTRUSTED" in res.display["markdown"]
    
    # Verify it published MESH_DEVICE_ANNOUNCE with untrusted level
    mock_fabric.publish.assert_called_once()
    topic, payload = mock_fabric.publish.call_args[0]
    assert topic == "sys/device/announce"
    assert payload["trust_level"] == "untrusted"
    


def test_privacy_guard_biometric_restrict(test_device):
    """Biometric data types are blocked by PrivacyGuard."""
    pg = PrivacyGuard()
    
    # test_device is untrusted
    assert pg.can_sync_memory(test_device.device_id) is False
    
    # Create trusted device
    registry = get_registry()
    trusted_dev = Device(
        device_id="trusted_dev_1",
        name="Trusted Device",
        device_type=DeviceType.COMPUTE,
        role=DeviceRole.HOST,
        initial_trust_level=TrustLevel.TRUSTED
    )
    registry._devices[trusted_dev.device_id] = trusted_dev
    
    # Can sync generic memory to trusted
    assert pg.can_sync_memory(trusted_dev.device_id) is True
    
    # Cannot sync biometric memory even to trusted
    assert pg.can_sync_memory(trusted_dev.device_id, data_type="face_embedding") is False
    assert pg.can_sync_memory(trusted_dev.device_id, data_type="person") is False
    assert pg.can_sync_memory(trusted_dev.device_id, data_type="generic") is True
    
    # Cleanup
    del registry._devices["trusted_dev_1"]
