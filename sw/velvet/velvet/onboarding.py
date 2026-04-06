"""
Device Onboarding and Interrogation Agent.

Handles the discovery, profiling, and registration of new devices into the Mesh.
Implements the "Interrogator" logic which acts as a security gatekeeper.
"""

__all__ = [
    "Interrogator",
    "scan_network",
    "interrogate_device",
    "onboard_device",
]

import asyncio
from typing import Any
from loguru import logger

from .scan import scan_all, ScannedDevice
from .devices import Device, DeviceType, DeviceRole, TrustLevel, ConnectionInfo, ConnectionMethod
from .skills import skill, SkillCategory, SkillParameter, AutonomyLevel, SkillResult
from .fabric import get_fabric, MessageType


class Interrogator:
    """
    Security Agent that profiles devices before admission.
    
    Phases:
    1. Scan (Raw Data)
    2. Profile (LLM Analysis) -> "This is likely a..."
    3. Vulnerability Check -> "Open telnet port found!"
    4. Report Generation
    """
    
    def __init__(self):
        self._pending_devices: dict[str, ScannedDevice] = {}
        
    async def profile_device(self, scanned: ScannedDevice) -> dict[str, Any]:
        """
        Analyze a scanned device to determine its likely type and capabilities.
        In a real implementation, this would call the LLM with scan data.
        """
        # Simulated LLM profiling logic for prototype
        profile = {
            "type": DeviceType.OTHER,
            "role": DeviceRole.PERIPHERAL,
            "likely_name": scanned.name,
            "confidence": 0.5,
            "vulns": []
        }
        
        # Heuristics (to be replaced by LLM)
        lower_name = scanned.name.lower()
        
        if "raspberry" in lower_name or "pi" in lower_name:
            profile["type"] = DeviceType.COMPUTE
            profile["role"] = DeviceRole.HOST
            profile["likely_name"] = "Raspberry Pi"
            profile["confidence"] = 0.9
            
        elif "jetson" in lower_name or "nvidia" in lower_name:
            profile["type"] = DeviceType.COMPUTE
            profile["role"] = DeviceRole.HOST
            profile["likely_name"] = "Jetson Edge Connect"
            profile["confidence"] = 0.95
            
        elif "cam" in lower_name or "axis" in lower_name or "hikvision" in lower_name:
            profile["type"] = DeviceType.SENSOR
            profile["role"] = DeviceRole.PERIPHERAL
            profile["likely_name"] = "IP Camera"
            profile["vulns"].append("Check for default RTSP credentials")
            
        elif "esp32" in lower_name or "light" in lower_name or "plug" in lower_name:
            profile["type"] = DeviceType.IOT
            profile["role"] = DeviceRole.PERIPHERAL
        
        # Port detection hints
        if 22 in scanned.ports:
            profile["type"] = DeviceType.COMPUTE
            profile["role"] = DeviceRole.HOST
        if 554 in scanned.ports:
            profile["type"] = DeviceType.SENSOR
        
        return profile

    async def generate_dossier(self, scanned: ScannedDevice) -> str:
        """Generate a markdown security dossier for the user."""
        profile = await self.profile_device(scanned)
        
        return f"""
## Security Dossier: {scanned.name}

**Identity**
- **IP**: `{scanned.ip_address}`
- **MAC**: `{scanned.mac_address}`
- **Type**: {profile['type'].value.upper()} (Confidence: {profile['confidence']})

**Capabilities**
- **Ports**: {scanned.ports if scanned.ports else "Unknown"}
- **Services**: {scanned.services if scanned.services else "None"}

**Analysis**
- **Suggested Role**: {profile['role'].value.upper()}
- **Vulnerabilities**: {", ".join(profile['vulns']) if profile['vulns'] else "None detected"}

**Recommendation**
{self._get_recommendation(profile)}
"""

    def _get_recommendation(self, profile: dict) -> str:
        if profile["vulns"]:
            return "⚠️ **CAUTION**: Vulnerabilities detected. Admit as Untrusted Peripheral or Quarantine."
        if profile["type"] == DeviceType.COMPUTE:
            return "✅ **Safe to Admit**: Capable of running Velvet Engine (Host Node)."
        return "ℹ️ **Admit as Peripheral**: Requires a Host Node to manage this resource."


# Global Interrogator instance
_interrogator = Interrogator()


@skill(
    name="scan_network",
    description="Scan the local network for new devices to onboard.",
    category=SkillCategory.PERCEPTION,
    parameters=[
        SkillParameter("type", "string", "Type of scan (all, network, ble)", required=False, default="all")
    ],
    tags=["discovery", "network", "admin"]
)
async def scan_network(type: str = "all") -> SkillResult:
    """Run a network scan and report found devices."""
    devices = await scan_all()
    
    if not devices:
        return SkillResult.ok(speak="No new devices found nearby.")
        
    summary = []
    for d in devices:
        # Cache for interrogation
        _interrogator._pending_devices[d.id] = d
        summary.append(f"- **{d.name}** ({d.id})")
        
    return SkillResult.ok(
        speak=f"I found {len(devices)} devices.",
        display={
            "markdown": "### Discovered Devices\n" + "\n".join(summary) + "\n\nAsk me to 'interrogate [device_id]' to proceed."
        }
    )


@skill(
    name="interrogate_device",
    description="Profile a specific device and generate a security report.",
    category=SkillCategory.SPECIALIST,
    parameters=[
        SkillParameter("device_id", "string", "ID (IP/MAC) of the device to interrogate")
    ],
    tags=["security", "onboarding"]
)
async def interrogate_device(device_id: str) -> SkillResult:
    """Deep profile a device."""
    # Check if we have it in cache, if not, do a quick targeted scan (omitted for prototype)
    scanned = _interrogator._pending_devices.get(device_id)
    
    if not scanned:
        # Try to find it in previous results or assume it's an IP
        # For prototype, we fail if not found in cache
        return SkillResult.fail(f"Device {device_id} not found in recent scans. Run scan_network first.")
        
    dossier = await _interrogator.generate_dossier(scanned)
    
    return SkillResult.ok(
        speak=f"Analysis complete for {scanned.name}. Please review the dossier.",
        display={"markdown": dossier}
    )


@skill(
    name="onboard_device",
    description="Admit a device into the mesh with a specific role and trust level.",
    category=SkillCategory.ROBOTICS, # Or Admin
    parameters=[
        SkillParameter("device_id", "string", "ID of device to onboard"),
        SkillParameter("role", "string", "host or peripheral"),
        SkillParameter("trust", "string", "trusted or untrusted"),
        SkillParameter("manager_id", "string", "ID of host managing this peripheral", required=False),
        SkillParameter("credentials", "dict", "SSH/RTSP credentials", required=False)
    ],
    autonomy=AutonomyLevel.LEVEL_2, # Requires confirmation
    tags=["onboarding", "admin"]
)
async def onboard_device(
    device_id: str,
    role: str = "host",
    trust: str = "trusted",
    manager_id: str | None = None,
    credentials: dict | None = None
) -> SkillResult:
    """
    Onboard a device to the mesh.
    
    For HOST: Performs SSH injection (simulated for now).
    For PERIPHERAL: Registers it as managed resource.
    """
    scanned = _interrogator._pending_devices.get(device_id)
    if not scanned:
        # Create a dummy scanned device if not found (e.g. manual entry)
        scanned = ScannedDevice(id=device_id, name=f"Device-{device_id}", scan_type="manual")
    
    try:
        r = DeviceRole(role.lower())
        t = TrustLevel(trust.lower())
    except ValueError:
        return SkillResult.fail("Invalid role or trust level.")
        
    # Instantiate appropriate driver
    from .drivers import NativeDriver, RTSPDriver, ConnectionInfo, ConnectionMethod
    
    driver = None
    conn_info = None
    
    if r == DeviceRole.HOST:
        driver = NativeDriver()
        # Assume SSH for now if credentials provided
        if credentials and "host" in credentials:
             # This assumes credentials dict has address/username/password
             conn_info = ConnectionInfo(
                 method=ConnectionMethod.SSH,
                 address=credentials.get("host", device_id), # fallback to ID if it's an IP
                 username=credentials.get("username", "pi"),
                 password=credentials.get("password", ""),
             )
    elif r == DeviceRole.PERIPHERAL:
        # Check if it's a camera
        if "cam" in scanned.name.lower() or "rtsp" in scanned.services:
            driver = RTSPDriver()
            creds = credentials or {}
            conn_info = ConnectionInfo(
                method=ConnectionMethod.HTTP_API, # or RTSP
                address=scanned.ip_address or device_id,
                username=creds.get("username", "admin"),
                password=creds.get("password", ""),
            )

    success_msg = ""
    sanitized_id = device_id.replace(":", "").replace(".", "_")
    if driver and conn_info:
        # Attempt connection
        if await driver.connect(conn_info):
            success_msg = "Driver connected successfully."
            if r == DeviceRole.HOST:
                await driver.inject_velvet(sanitized_id)
                success_msg += " Velvet Agent + mTLS certs injected."
        else:
            return SkillResult.fail(f"Failed to connect using {driver.__class__.__name__}.")
            
    # Create the Device object within the registry
    from .devices import Device, DeviceStatus, HardwareSpecs, ConnectionInfo as DeviceConnInfo
    
    new_device = Device(
        device_id=sanitized_id,
        name=scanned.name,
        device_type=DeviceType.COMPUTE if r == DeviceRole.HOST else DeviceType.SENSOR,
        role=r,
        trust_level=t,
        manager_id=manager_id,
        connection=conn_info, # Save connection info
        status=DeviceStatus.ONLINE, 
        hardware=HardwareSpecs(custom={"scanned_data": str(scanned.__dict__)}),
        metadata={"driver": driver.__class__.__name__ if driver else "None"}
    )
    
    # Publish MESH_DEVICE_ANNOUNCE
    fabric = get_fabric()
    await fabric.publish(MessageType.MESH_DEVICE_ANNOUNCE.value, new_device.to_dict())
    
    return SkillResult.ok(
        speak=f"Device {scanned.name} onboarded as {t.value} {r.value}. {success_msg}",
        display={"markdown": f"✅ **Success**: {scanned.name} is now part of the mesh.\n\n{success_msg}"}
    )
