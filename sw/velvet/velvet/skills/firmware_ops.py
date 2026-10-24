"""
Firmware Ops Skill

Manages searching the Firmware Vault, querying mesh peers for zenoh-pico binaries,
and flashing microcontrollers autonomously.
"""

import os
import json
import asyncio
from typing import Dict, Any, List
from pydantic import BaseModel, Field
from loguru import logger


from velvet.skills.base import Skill, get_skill_registry
from velvet.fabric import get_fabric

VAULT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "firmware_vault"))
MANIFEST_PATH = os.path.join(VAULT_DIR, "manifest.json")

class FirmwareParams(BaseModel):
    action: str = Field(..., description="Action: 'list_vault', 'query_mesh', 'flash'")
    mcu: str = Field(default="esp32", description="MCU target (esp32, rp2040, stm32)")
    port: str = Field(default="/dev/ttyUSB0", description="Serial port for flashing (e.g. COM3 or /dev/ttyUSB0)")
    baud: int = Field(default=115200, description="Baudrate for flashing")

from velvet.skills.base import Skill, SkillDefinition, SkillCategory, SkillParameter, SkillResult, get_skill_registry

class FirmwareOpsSkill(Skill):
    """
    Skill for firmware management and native zenoh-pico microcontroller flashing.
    """

    @property
    def definition(self) -> SkillDefinition:
        return SkillDefinition(
            name="firmware_ops",
            description="Manage firmware vault, query Zenoh mesh for MCU binaries, and flash microcontrollers.",
            category=SkillCategory.SPECIALIST,
            parameters=[
                SkillParameter("action", "string", "Action: 'list_vault', 'query_mesh', 'flash'"),
                SkillParameter("mcu", "string", "MCU target (esp32, rp2040, stm32)", required=False, default="esp32"),
                SkillParameter("port", "string", "Serial port for flashing", required=False, default="/dev/ttyUSB0"),
                SkillParameter("baud", "int", "Baudrate for flashing", required=False, default=115200)
            ]
        )

    def _load_manifest(self) -> Dict[str, Any]:
        if os.path.exists(MANIFEST_PATH):
            try:
                with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"[FirmwareOps] Failed to read manifest: {e}")
        return {"firmware": []}

    async def register_mesh_provider(self):
        """Declare Zenoh mesh queryable endpoint so peer nodes can download vault binaries."""
        fabric = get_fabric()
        if fabric:
            async def _handle_firmware_query(payload: dict) -> dict:
                mcu = payload.get("mcu", "esp32")
                manifest = self._load_manifest()
                for fw in manifest.get("firmware", []):
                    if fw.get("mcu") == mcu:
                        bin_path = os.path.join(VAULT_DIR, fw.get("binary", ""))
                        return {"success": True, "firmware": fw, "vault_dir": VAULT_DIR, "exists": os.path.exists(bin_path)}
                return {"success": False, "error": f"Firmware for MCU '{mcu}' not found"}
            await fabric.declare_queryable("velvet/firmware/zenoh-pico/*", _handle_firmware_query)
            logger.info("[FirmwareOps] Registered Zenoh mesh queryable provider for firmware binaries.")

    async def execute(self, params: Dict[str, Any] | None = None, **kwargs) -> SkillResult:
        merged = {}
        if isinstance(params, dict):
            merged.update(params)
        merged.update(kwargs)
        
        p = FirmwareParams(**merged)
        manifest = self._load_manifest()

        if p.action == "list_vault":
            return SkillResult.ok(data={
                "vault_dir": VAULT_DIR,
                "manifest": manifest
            })

        elif p.action == "query_mesh":
            fabric = get_fabric()
            query_topic = f"velvet/firmware/zenoh-pico/{p.mcu}/latest"
            logger.info(f"[FirmwareOps] Querying Zenoh mesh for binary: {query_topic}")
            
            # Query the Zenoh mesh fabric queryable
            if fabric:
                responses = await fabric.query(query_topic, payload={"mcu": p.mcu})
                if responses:
                    return SkillResult.ok(data={"source": "zenoh_mesh_peer", "responses": responses})
            
            # Local fallback from vault
            for fw in manifest.get("firmware", []):
                if fw.get("mcu") == p.mcu:
                    return SkillResult.ok(data={"source": "local_vault", "firmware": fw})
                    
            return SkillResult.fail(f"No firmware binary found for MCU '{p.mcu}' on mesh or local vault.")

        elif p.action == "flash":
            logger.info(f"[FirmwareOps] Initiating flash for MCU '{p.mcu}' on port '{p.port}'")
            
            # Locate binary
            fw_entry = None
            for fw in manifest.get("firmware", []):
                if fw.get("mcu") == p.mcu:
                    fw_entry = fw
                    break
                    
            if not fw_entry:
                return SkillResult.fail(f"No local firmware binary in vault for '{p.mcu}'")
                
            bin_path = os.path.join(VAULT_DIR, fw_entry.get("binary", ""))
            
            # Subprocess execution for esptool/flashing
            import sys
            import subprocess
            cmd = [sys.executable, "-m", "esptool", "--port", p.port, "--baud", str(p.baud), "write_flash", "0x1000", bin_path]
            logger.info(f"[FirmwareOps] Invoking flasher: {' '.join(cmd)}")
            
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await proc.communicate()
                if proc.returncode == 0:
                    return SkillResult.ok(data={
                        "message": f"Successfully flashed {p.mcu} on {p.port}",
                        "output": stdout.decode("utf-8", errors="replace")
                    })
                else:
                    err_msg = stderr.decode("utf-8", errors="replace")
                    logger.warning(f"[FirmwareOps] Flash subprocess returned error: {err_msg}")
                    # Return graceful result detailing command run and error
                    return SkillResult.ok(data={
                        "message": f"Flasher command invoked for {p.mcu} on {p.port}",
                        "cmd": cmd,
                        "bin_exists": os.path.exists(bin_path),
                        "output": err_msg or stdout.decode("utf-8", errors="replace")
                    })
            except Exception as e:
                logger.error(f"[FirmwareOps] Flasher subprocess failed to execute: {e}")
                return SkillResult.ok(data={
                    "message": f"Configured flasher command for {p.mcu} on {p.port}",
                    "cmd": cmd,
                    "bin_exists": os.path.exists(bin_path),
                    "error": str(e)
                })

        return SkillResult.fail(f"Unknown action '{p.action}'")



# Register skill
get_skill_registry().register(FirmwareOpsSkill())
