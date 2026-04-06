"""
Tests for Device Discovery and Onboarding.
"""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from velvet.devices import DeviceRole, TrustLevel, DeviceType
from velvet.scan import ScannedDevice
from velvet.onboarding import Interrogator, onboard_device, interrogate_device

# ============================================================================
# Discovery Tests
# ============================================================================

@pytest.mark.asyncio
async def test_scanners():
    """Test that scanners return valid ScannedDevice objects."""
    # We mock the actual scan functions to avoid network calls
    with patch("velvet.scan.NetworkScanner.scan_arp", new_callable=AsyncMock) as mock_arp:
        mock_arp.return_value = [
            ScannedDevice("192.168.1.100", "Test-Device", "network", ip_address="192.168.1.100")
        ]
        
        from velvet.scan import scan_all
        devices = await scan_all()
        
        assert len(devices) == 1
        assert devices[0].id == "192.168.1.100"
        assert devices[0].name == "Test-Device"


# ============================================================================
# Interrogator Tests
# ============================================================================

@pytest.mark.asyncio
async def test_interrogator_profile_host():
    """Test interrogator correctly profiles a potential Host."""
    interrogator = Interrogator()
    scanned = ScannedDevice(
        id="192.168.1.50",
        name="raspberrypi",
        scan_type="network",
        ip_address="192.168.1.50",
        ports=[22]
    )
    
    profile = await interrogator.profile_device(scanned)
    
    assert profile["type"] == DeviceType.COMPUTE
    assert profile["role"] == DeviceRole.HOST
    assert profile["confidence"] >= 0.9

@pytest.mark.asyncio
async def test_interrogator_profile_peripheral():
    """Test interrogator correctly profiles a potential Peripheral."""
    interrogator = Interrogator()
    scanned = ScannedDevice(
        id="192.168.1.51",
        name="Axis-Camera-01",
        scan_type="network",
        ip_address="192.168.1.51",
        services=["_rtsp._tcp"]
    )
    
    profile = await interrogator.profile_device(scanned)
    
    assert profile["type"] == DeviceType.SENSOR
    assert profile["role"] == DeviceRole.PERIPHERAL
    assert "vulns" in profile
    assert len(profile["vulns"]) > 0


# ============================================================================
# Onboarding Tests
# ============================================================================

@pytest.mark.asyncio
async def test_onboard_host_success(mock_fabric):
    """Test successful onboarding of a Host Node."""
    # Mock the fabric to intercept announce
    with patch("velvet.onboarding.get_fabric", return_value=mock_fabric), \
         patch("velvet.drivers.NativeDriver") as MockDriver:
        
        # Setup mock driver
        driver_instance = MockDriver.return_value
        driver_instance.connect = AsyncMock(return_value=True)
        driver_instance.inject_velvet = AsyncMock(return_value=True)
        
        # Pre-seed capability in cache
        from velvet.onboarding import _interrogator
        _interrogator._pending_devices["192.168.1.50"] = ScannedDevice(
            "192.168.1.50", "raspberrypi", "network"
        )
        
        result = await onboard_device(
            device_id="192.168.1.50",
            role="host",
            trust="trusted",
            credentials={"host": "192.168.1.50", "username": "pi", "password": "pw"}
        )
        
        assert result.success
        assert "trusted host" in result.speak
        
        # Verify driver usage
        driver_instance.connect.assert_called_once()
        driver_instance.inject_velvet.assert_called_with("192_168_1_50")
        
        # Verify fabric publish
        mock_fabric.publish.assert_called()
        args, _ = mock_fabric.publish.call_args
        assert args[0] == "mesh/device/announce"
        assert args[1]["name"] == "raspberrypi"
        assert args[1]["role"] == "host"

@pytest.mark.asyncio
async def test_onboard_fail_invalid_role():
    """Test onboarding fails with invalid role."""
    result = await onboard_device("test-id", role="invalid_role")
    assert not result.success
    assert "Invalid role" in result.error
