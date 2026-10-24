"""
Unit tests for Velvet Nadir Phase 7:
Hardware Natural Language Enriched Specs & AI Device Exploration 4-Step Pipeline.
"""

import pytest
from velvet.devices import (
    Device,
    DeviceType,
    DeviceRole,
    TrustLevel,
    HardwareSpecs,
    SoftwareSpecs,
    DeviceScript,
    HardwareRegistry,
)
from velvet.errors import TrustGateError
from velvet.skills.device_explore import DeviceExplorationPipeline


def test_nl_enriched_hardware_and_script_specs():
    """Verify natural language description fields on HardwareSpecs and DeviceScript."""
    hw = HardwareSpecs(
        cpu="Qualcomm Snapdragon 8 Gen 2",
        has_camera=True,
        has_microphone=True,
        nl_description="Handheld compute terminal with wide-angle camera and stereo mic array.",
        nl_safety_limits="Thermal throttle at 75C; camera LED must remain active during capture.",
        nl_capabilities="Local 4-bit LLM inference up to 7B parameters; 4K video recording.",
    )
    hw_dict = hw.to_dict()
    assert hw_dict["nl_description"] != ""
    assert hw_dict["nl_safety_limits"] != ""
    assert hw_dict["nl_capabilities"] != ""

    restored_hw = HardwareSpecs.from_dict(hw_dict)
    assert restored_hw.nl_safety_limits == hw.nl_safety_limits

    script = DeviceScript(
        action="read_battery_telemetry",
        script="result = {'battery_pct': 88, 'status': 'charging'}",
        description="Reads battery percentage via fuel-gauge sensor",
        nl_description="Queries hardware fuel-gauge controller over I2C to obtain SoC percentage.",
        nl_prerequisites="I2C bus 1 must be initialized; device power subsystem online.",
        nl_expected_outcome="Returns dict with 'battery_pct' integer between 0 and 100.",
        nl_failure_modes="I2C bus timeout or negative percentage indicating sensor desync.",
    )
    script_dict = script.to_dict()
    assert script_dict["nl_prerequisites"] != ""
    assert script_dict["nl_expected_outcome"] != ""
    assert script_dict["nl_failure_modes"] != ""

    restored_script = DeviceScript.from_dict(script_dict)
    assert restored_script.nl_expected_outcome == script.nl_expected_outcome


@pytest.mark.asyncio
async def test_device_exploration_pipeline_safe_vs_malicious():
    """Verify the 4-step AI exploration pipeline, AST validation, and TrustGate."""
    registry = HardwareRegistry()
    device = Device(
        device_id="cam_rover_01",
        name="Rover Inspection Platform",
        device_type=DeviceType.ROBOT,
        role=DeviceRole.PERIPHERAL,
        initial_trust_level=TrustLevel.TRUSTED,
        hardware=HardwareSpecs(cpu="Cortex-M7", motor_count=4),
        software=SoftwareSpecs(os="FreeRTOS"),
    )
    await registry.register(device)

    pipeline = DeviceExplorationPipeline(registry=registry)

    # 1. Read primitive verification
    driver = pipeline.get_read_primitive("cam_rover_01")
    status = await driver.get_status()
    assert status["device_id"] == "cam_rover_01"
    assert status["name"] == "Rover Inspection Platform"

    # 2. Vidya AST rejection on malicious script (e.g. banned subprocess or eval)
    malicious_script = "import subprocess\nsubprocess.run(['rm', '-rf', '/'])"
    res_malicious = await pipeline.explore_and_register_script(
        device_id="cam_rover_01",
        action="nuke_device",
        script_code=malicious_script,
    )
    assert res_malicious["success"] is False
    assert res_malicious["stage"] == "ast_validation"
    assert any("Banned module import" in v for v in res_malicious["violations"])

    # 3. Successful exploration on safe script
    safe_script = "result = {'motors': 4, 'speed': 1.5, 'ready': True}"
    res_safe = await pipeline.explore_and_register_script(
        device_id="cam_rover_01",
        action="calibrate_motors",
        script_code=safe_script,
        nl_description="Calibrates all 4 stepper motors and verifies ready state.",
    )
    assert res_safe["success"] is True
    assert res_safe["result"]["ready"] is True
    assert "calibrate_motors" in device.scripts

    # 4. TrustGate rejection on untrusted device without biometric authorization
    untrusted_device = Device(
        device_id="rogue_sensor_99",
        name="Unknown Rogue Sensor",
        device_type=DeviceType.SENSOR,
        role=DeviceRole.PERIPHERAL,
        initial_trust_level=TrustLevel.UNTRUSTED,
        hardware=HardwareSpecs(),
        software=SoftwareSpecs(),
    )
    await registry.register(untrusted_device)

    with pytest.raises(TrustGateError):
        await pipeline.explore_and_register_script(
            device_id="rogue_sensor_99",
            action="read_temp",
            script_code="result = 42",
            operator_biometric_authorized=False,
        )

    # With operator biometric override, it succeeds
    res_override = await pipeline.explore_and_register_script(
        device_id="rogue_sensor_99",
        action="read_temp",
        script_code="result = 42",
        operator_biometric_authorized=True,
    )
    assert res_override["success"] is True
