"""
AI Device Exploration 4-Step Pipeline for Velvet Nadir.
Enables Hun / Saraswati to safely discover, probe, script, and verify devices on the mesh:
1. Exposes read primitive DeviceDriver.get_status() and sandboxed write primitive DeviceScript.run_sandboxed().
2. Iterative Hun reasoning loop probes device status, drafts control commands, and observes physical responses.
3. Saraswati Vidya AST validator inspects proposed script AST (strictly bans eval, exec, subprocess, raw network sockets).
4. Gated behind TrustEngine: new scripts for untrusted or first-time devices require operator biometric authorization.
"""

import ast
import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple

from velvet.devices import (
    Device,
    DeviceScript,
    DeviceStatus,
    HardwareRegistry,
    TrustLevel,
    get_registry,
)
from velvet.errors import TrustGateError
from velvet.skills.base import (
    skill,
    SkillCategory,
    SkillParameter,
    SkillResult,
    AutonomyLevel,
)

logger = logging.getLogger(__name__)


class DeviceDriverMock:
    """Read primitive interface for querying device physical state."""

    def __init__(self, device: Device):
        self.device = device

    async def get_status(self) -> Dict[str, Any]:
        """Read primitive returning current device telemetry and status."""
        return {
            "device_id": self.device.device_id,
            "name": self.device.name,
            "status": self.device.status.value,
            "trust_level": self.device.trust_level.value,
            "nl_description": self.device.hardware.nl_description,
            "nl_safety_limits": self.device.hardware.nl_safety_limits,
            "nl_capabilities": self.device.hardware.nl_capabilities,
            "load": self.device.load.to_dict() if hasattr(self.device.load, "to_dict") else {},
            "scripts": list(self.device.scripts.keys()),
        }


class DeviceExplorationPipeline:
    """
    4-Step AI Device Exploration Engine.
    """

    def __init__(self, registry: Optional[HardwareRegistry] = None):
        self.registry = registry or get_registry()

    def get_read_primitive(self, device_id: str) -> DeviceDriverMock:
        """Step 1: Expose read primitive."""
        device = self.registry.get_device(device_id)
        if not device:
            raise ValueError(f"Device not found: {device_id}")
        return DeviceDriverMock(device)

    def validate_script_ast(self, script_code: str) -> Tuple[bool, List[str]]:
        """
        Step 3: Saraswati Vidya AST validator.
        Strictly bans eval, exec, subprocess, raw network sockets, and file system mutations.
        """
        banned_calls = {"eval", "exec", "compile", "__import__", "globals", "locals", "open"}
        banned_modules = {"subprocess", "os", "shutil", "socket", "urllib", "requests", "httpx"}

        violations = []
        try:
            tree = ast.parse(script_code)
        except SyntaxError as e:
            return False, [f"Syntax error in script: {e}"]

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                call_name = None
                if isinstance(node.func, ast.Name):
                    call_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    call_name = node.func.attr
                if call_name in banned_calls:
                    violations.append(f"Banned function call: {call_name}()")

            elif isinstance(node, ast.Import):
                for alias in node.names:
                    root_mod = alias.name.split(".")[0]
                    if root_mod in banned_modules:
                        violations.append(f"Banned module import: {alias.name}")

            elif isinstance(node, ast.ImportFrom):
                root_mod = (node.module or "").split(".")[0]
                if root_mod in banned_modules:
                    violations.append(f"Banned module import: from {node.module}")

        return len(violations) == 0, violations

    async def explore_and_register_script(
        self,
        device_id: str,
        action: str,
        script_code: str,
        nl_description: str = "",
        nl_prerequisites: str = "",
        nl_expected_outcome: str = "",
        nl_failure_modes: str = "",
        operator_biometric_authorized: bool = False,
    ) -> Dict[str, Any]:
        """
        Executes the full 4-step pipeline:
        1. Probes device telemetry.
        2. Inspects proposed script via Vidya AST validator.
        3. Enforces TrustEngine gate: untrusted or first-time scripts require biometric authorization.
        4. Sandboxed execution & registration.
        """
        device = self.registry.get_device(device_id)
        if not device:
            return {"success": False, "error": f"Device {device_id} not found."}

        # Step 1: Read status
        driver = self.get_read_primitive(device_id)
        status = await driver.get_status()

        # Step 2: Validate AST
        is_safe, violations = self.validate_script_ast(script_code)
        if not is_safe:
            logger.warning(f"[DeviceExplore] Script for {device_id} rejected by Vidya AST: {violations}")
            return {
                "success": False,
                "stage": "ast_validation",
                "error": "Script failed Vidya AST validation",
                "violations": violations,
            }

        # Step 3: TrustGate verification
        if device.trust_level != TrustLevel.TRUSTED and not operator_biometric_authorized:
            raise TrustGateError(
                f"Device '{device_id}' has trust level '{device.trust_level.value}'. "
                f"Execution requires operator biometric authorization."
            )

        # Step 4: Sandboxed execution & observation
        device_script = DeviceScript(
            action=action,
            script=script_code,
            description=f"AI-explored action '{action}' for {device.name}",
            nl_description=nl_description,
            nl_prerequisites=nl_prerequisites,
            nl_expected_outcome=nl_expected_outcome,
            nl_failure_modes=nl_failure_modes,
            verified=True,
            is_sandboxed=True,
        )

        exec_res = device_script.run_sandboxed(context={"device_status": status})
        if not exec_res.get("success"):
            return {
                "success": False,
                "stage": "sandboxed_run",
                "error": exec_res.get("error"),
            }

        # Register script onto device
        device.scripts[action] = device_script
        logger.info(f"[DeviceExplore] Successfully explored and registered action '{action}' on device '{device_id}'")

        return {
            "success": True,
            "action": action,
            "device_id": device_id,
            "result": exec_res.get("result"),
            "device_script": device_script.to_dict(),
        }


@skill(
    name="explore_device",
    description="Safely explore, validate, and test new control scripts on a mesh device",
    category=SkillCategory.ROBOTICS,
    parameters=[
        SkillParameter("device_id", "str", "ID of the target mesh device", required=True),
        SkillParameter("action", "str", "Action verb (e.g. read_telemetry, toggle_led)", required=True),
        SkillParameter("script_code", "str", "Python control code to probe and control device", required=True),
        SkillParameter("nl_description", "str", "Natural language description of what script does", required=False, default=""),
        SkillParameter("operator_biometric_authorized", "bool", "Biometric authorization override", required=False, default=False),
    ],
    autonomy=AutonomyLevel.LEVEL_2,
    tags=["device", "hardware", "explore", "ai_pipeline"],
)
async def explore_device_skill(
    device_id: str,
    action: str,
    script_code: str,
    nl_description: str = "",
    operator_biometric_authorized: bool = False,
) -> SkillResult:
    """Skill wrapper for AI device exploration."""
    pipeline = DeviceExplorationPipeline()
    try:
        res = await pipeline.explore_and_register_script(
            device_id=device_id,
            action=action,
            script_code=script_code,
            nl_description=nl_description,
            operator_biometric_authorized=operator_biometric_authorized,
        )
        if res.get("success"):
            return SkillResult.ok(
                data=res,
                speak=f"Exploration for {action} on {device_id} succeeded.",
            )
        return SkillResult.fail(
            error=res.get("error", "Exploration failed"),
            data=res,
        )
    except TrustGateError as e:
        return SkillResult.blocked(
            blocker_kind="NEEDS_INPUT",
            description=str(e),
            requires_biometrics=True,
        )
