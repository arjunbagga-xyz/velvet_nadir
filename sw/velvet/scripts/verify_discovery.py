"""
Integration test for Device Discovery and Onboarding (Sprint 3).
"""

import asyncio
import sys
from loguru import logger
from velvet.devices import init_registry, DeviceRole, TrustLevel
from velvet.scan import scan_all, ScannedDevice
from velvet.onboarding import _interrogator, onboard_device, interrogate_device
from velvet.fabric import init_fabric

# Configure logging to stdout
logger.remove()
logger.add(sys.stderr, level="INFO")

async def test_discovery():
    logger.info("--- Testing Discovery Scanners ---")
    devices = await scan_all()
    logger.info(f"Found {len(devices)} devices:")
    for d in devices:
        logger.info(f"  - [{d.scan_type}] {d.name} ({d.id})")
    return devices

async def test_interrogator():
    logger.info("\n--- Testing Interrogator Agent ---")
    
    # Create dummy devices to test profiling logic
    dummies = [
        ScannedDevice("192.168.1.50", "raspberrypi", "network", ip_address="192.168.1.50", ports=[22]),
        ScannedDevice("192.168.1.51", "Generic-Camera-01", "network", ip_address="192.168.1.51", services=["_rtsp._tcp"]),
        ScannedDevice("AA:BB:CC:DD:EE:FF", "JBL Flip 6", "ble", mac_address="AA:BB:CC:DD:EE:FF"),
    ]
    
    for d in dummies:
        logger.info(f"Profiling {d.name}...")
        report = await _interrogator.generate_dossier(d)
        print(report)
        
        # Inject into cache for onboarding test
        _interrogator._pending_devices[d.id] = d

async def test_onboarding():
    logger.info("\n--- Testing Onboarding Skill ---")
    
    # Initialize infrastructure
    await init_fabric("test-device", mode="peer")
    registry = await init_registry(with_fabric=True)
    
    # Test 1: Onboard the Pi as Host
    logger.info("Onboarding Raspberry Pi as Host...")
    result = await onboard_device(
        device_id="192.168.1.50",
        role="host",
        trust="trusted",
        credentials={"host": "192.168.1.50", "username": "pi", "password": "password"}
    )
    logger.info(f"Result: {result.speak}")
    
    # Verify in registry
    # Note: Registry update is async via Zenoh, might need a moment
    await asyncio.sleep(0.5)
    
    pi_dev = registry.get_device("192_168_1_50")
    if pi_dev:
        logger.info(f"Registry Verification: Found {pi_dev.name}")
        logger.info(f"  Role: {pi_dev.role.value}")
        logger.info(f"  Trust: {pi_dev.trust_level.value}")
    else:
        logger.error("Registry Verification: Device NOT found!")

    # Test 2: Onboard Camera as Peripheral
    logger.info("\nOnboarding Camera as Peripheral...")
    result = await onboard_device(
        device_id="192.168.1.51",
        role="peripheral",
        trust="untrusted",
        manager_id="test-device"
    )
    logger.info(f"Result: {result.speak}")
    
    await asyncio.sleep(0.5)
    cam_dev = registry.get_device("192_168_1_51")
    if cam_dev:
         logger.info(f"Registry Verification: Found {cam_dev.name}")
         logger.info(f"  Role: {cam_dev.role.value}")
         logger.info(f"  Trust: {cam_dev.trust_level.value}")
         logger.info(f"  Manager: {cam_dev.manager_id}")
    else:
         logger.error("Registry Verification: Device NOT found!")

async def main():
    try:
        await test_discovery()
        await test_interrogator()
        await test_onboarding()
        logger.info("\n✅ Verification Complete")
    except Exception as e:
        logger.exception(f"Verification Failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
