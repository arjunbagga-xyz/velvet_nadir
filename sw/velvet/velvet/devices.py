"""
Device Registry for Velvet Nadir.

Tracks all devices on the P2P mesh including:
- Compute devices (GPU servers, Jetson, etc.)
- Sensors (phones, cameras, microphones)
- Vehicles (cars, drones)
- Robots (arms, rovers)
- IoT (smart home, switches)

Devices announce themselves over Zenoh and maintain heartbeats.
"""

__all__ = [
    "DeviceType",
    "DeviceRole",
    "TrustLevel",
    "DeviceStatus",
    "ConnectionMethod",
    "ConnectionInfo",
    "HardwareSpecs",
    "SoftwareSpecs",
    "DeviceScript",
    "DeviceLoad",
    "Device",
    "HardwareRegistry",
    "create_registry_with_fabric",
    "detect_local_hardware",
    "detect_local_software",
    "create_local_device",
    "get_registry",
    "init_registry",
]

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Awaitable
from loguru import logger


class DeviceType(Enum):
    """Types of devices that can join the mesh."""
    COMPUTE = "compute"      # GPU servers, Jetson, laptops
    SENSOR = "sensor"        # Cameras, phones, microphones
    VEHICLE = "vehicle"      # Cars, drones, boats
    ROBOT = "robot"          # Robotic arms, rovers, humanoids
    IOT = "iot"              # Smart home, switches, lights
    OTHER = "other"          # Anything else


class DeviceRole(Enum):
    """Role of the device in the mesh."""
    HOST = "host"              # Runs Velvet engine
    PERIPHERAL = "peripheral"  # Managed resource (camera, sensor)


class TrustLevel(Enum):
    """Trust level of the device."""
    TRUSTED = "trusted"        # Full access (owned device)
    UNTRUSTED = "untrusted"    # Restricted access (guest/borrowed)


class DeviceStatus(Enum):
    """Device online status."""
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    ERROR = "error"


class ConnectionMethod(Enum):
    """
    Methods to connect to/onboard a device.
    
    Velvet is agnostic about how devices join the mesh.
    Each method has its own connection handler.
    """
    ZENOH = "zenoh"              # Already on mesh, native Zenoh
    WEBSOCKET = "websocket"      # WebSocket (like phone app)
    SSH = "ssh"                  # SSH for remote machines
    BLUETOOTH = "bluetooth"      # Bluetooth pairing
    USB = "usb"                  # USB/cable connection
    SERIAL = "serial"            # Serial port (Arduino, etc.)
    IR = "ir"                    # Infrared
    HTTP_API = "http_api"        # REST API
    MQTT = "mqtt"                # MQTT broker
    ZIGBEE = "zigbee"            # Zigbee/Z-Wave
    CAN = "can"                  # CAN bus (vehicles)
    CUSTOM = "custom"            # Custom script (Rubber Ducky, etc.)


@dataclass
class ConnectionInfo:
    """
    Connection details for reaching a device.
    
    Stores how to connect and any credentials/params needed.
    """
    method: ConnectionMethod
    address: str = ""            # IP, MAC, port, path, etc.
    port: int = 0
    username: str = ""
    password: str = ""           # Or key path for SSH
    script: str = ""             # For CUSTOM method
    params: dict = field(default_factory=dict)  # Extra connection params
    
    def to_dict(self) -> dict:
        return {
            "method": self.method.value,
            "address": self.address,
            "port": self.port,
            "username": self.username,
            "password": self.password if self.password else None,
            "script": self.script if self.script else None,
            "params": self.params,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ConnectionInfo":
        return cls(
            method=ConnectionMethod(data.get("method", "zenoh")),
            address=data.get("address", ""),
            port=data.get("port", 0),
            username=data.get("username", ""),
            password=data.get("password", ""),
            script=data.get("script", ""),
            params=data.get("params", {}),
        )


@dataclass
class HardwareSpecs:
    """Hardware specifications of a device."""
    cpu: str = ""
    cpu_cores: int = 0
    ram_gb: float = 0
    gpu: str = ""
    gpu_vram_gb: float = 0
    storage_gb: float = 0
    # Sensors
    has_camera: bool = False
    has_microphone: bool = False
    has_gps: bool = False
    has_accelerometer: bool = False
    # Special hardware
    can_bus: bool = False       # Vehicle CAN bus
    obd2: bool = False          # Vehicle OBD-II
    motor_count: int = 0        # Robot motors
    custom: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "cpu": self.cpu,
            "cpu_cores": self.cpu_cores,
            "ram_gb": self.ram_gb,
            "gpu": self.gpu,
            "gpu_vram_gb": self.gpu_vram_gb,
            "storage_gb": self.storage_gb,
            "has_camera": self.has_camera,
            "has_microphone": self.has_microphone,
            "has_gps": self.has_gps,
            "has_accelerometer": self.has_accelerometer,
            "can_bus": self.can_bus,
            "obd2": self.obd2,
            "motor_count": self.motor_count,
            "custom": self.custom,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "HardwareSpecs":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class SoftwareSpecs:
    """Software specifications of a device."""
    os: str = ""
    os_version: str = ""
    python_version: str = ""
    cuda_version: str = ""
    installed_packages: list[str] = field(default_factory=list)
    custom: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "os": self.os,
            "os_version": self.os_version,
            "python_version": self.python_version,
            "cuda_version": self.cuda_version,
            "installed_packages": self.installed_packages,
            "custom": self.custom,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "SoftwareSpecs":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class DeviceScript:
    """A plug-n-play script for controlling a device."""
    action: str                  # "unlock_doors", "start_cleaning"
    script: str                  # Python/shell code
    description: str = ""
    verified: bool = False
    is_sandboxed: bool = False   # Whether this script has passed sandbox validation
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Reuses the same banned-call list as Vidya (shen/saraswati.py)
    _BANNED_CALLS = {
        "eval", "exec", "compile", "__import__", "globals", "locals",
        "getattr", "setattr", "delattr", "open",
    }
    _BANNED_IMPORTS = {
        "subprocess", "os.system", "shutil", "ctypes",
        "requests", "urllib", "httpx", "aiohttp", "socket",
        "pickle", "shelve", "marshal",
    }

    def validate_script(self) -> tuple[bool, list[str]]:
        """
        Validate the script using AST analysis.

        Returns (is_safe, list_of_violations).
        Mirrors the Vidya validator from shen/saraswati.py.
        """
        import ast as _ast

        violations: list[str] = []
        try:
            tree = _ast.parse(self.script)
        except SyntaxError as e:
            return False, [f"Syntax error: {e}"]

        for node in _ast.walk(tree):
            if isinstance(node, _ast.Call):
                name = None
                if isinstance(node.func, _ast.Name):
                    name = node.func.id
                elif isinstance(node.func, _ast.Attribute):
                    name = node.func.attr
                if name and name in self._BANNED_CALLS:
                    violations.append(f"Banned call: {name}()")

            if isinstance(node, _ast.Import):
                for alias in node.names:
                    if alias.name in self._BANNED_IMPORTS:
                        violations.append(f"Banned import: {alias.name}")

            if isinstance(node, _ast.ImportFrom):
                module = node.module or ""
                if module in self._BANNED_IMPORTS:
                    violations.append(f"Banned import: from {module}")

        is_safe = len(violations) == 0
        if is_safe:
            self.is_sandboxed = True
        return is_safe, violations

    def run_sandboxed(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Execute the script with restricted globals.

        Only runs if validate_script() has passed (is_sandboxed=True).
        Returns a dict with 'success', 'result', and optionally 'error'.
        """
        if not self.is_sandboxed:
            return {"success": False, "error": "Script not validated. Call validate_script() first."}

        # Build restricted globals — only safe builtins
        safe_builtins = {
            k: v for k, v in __builtins__.items()  # type: ignore
            if k not in self._BANNED_CALLS
        } if isinstance(__builtins__, dict) else {
            k: getattr(__builtins__, k)
            for k in dir(__builtins__)
            if not k.startswith("_") and k not in self._BANNED_CALLS
        }

        restricted_globals: dict[str, Any] = {
            "__builtins__": safe_builtins,
            "__name__": "__sandbox__",
        }
        if context:
            restricted_globals.update(context)

        try:
            exec(compile(self.script, f"<device_script:{self.action}>", "exec"), restricted_globals)  # noqa: S102
            # Collect any 'result' the script set
            result = restricted_globals.get("result", None)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}


@dataclass
class DeviceLoad:
    """Real-time load statistics of a device."""
    cpu_percent: float = 0.0
    ram_percent: float = 0.0
    gpu_load: float = 0.0
    vram_free_gb: float = 0.0
    active_tasks: int = 0
    measured_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "cpu_percent": self.cpu_percent,
            "ram_percent": self.ram_percent,
            "gpu_load": self.gpu_load,
            "vram_free_gb": self.vram_free_gb,
            "active_tasks": self.active_tasks,
            "measured_at": self.measured_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DeviceLoad":
        return cls(
            cpu_percent=data.get("cpu_percent", 0.0),
            ram_percent=data.get("ram_percent", 0.0),
            gpu_load=data.get("gpu_load", 0.0),
            vram_free_gb=data.get("vram_free_gb", 0.0),
            active_tasks=data.get("active_tasks", 0),
            measured_at=datetime.fromisoformat(data["measured_at"]) if "measured_at" in data else datetime.now(timezone.utc),
        )


@dataclass
class Device:
    """A device on the Velvet mesh."""
    device_id: str
    name: str
    device_type: DeviceType
    role: DeviceRole = DeviceRole.HOST
    trust_level: TrustLevel = TrustLevel.TRUSTED
    manager_id: str | None = None  # If PERIPHERAL, which HOST manages it
    hardware: HardwareSpecs = field(default_factory=HardwareSpecs)
    software: SoftwareSpecs = field(default_factory=SoftwareSpecs)
    connection: ConnectionInfo | None = None  # How to reach this device
    load: DeviceLoad = field(default_factory=DeviceLoad)  # Real-time state
    capabilities: list[str] = field(default_factory=list)  # ["inference", "camera", "tts"]
    scripts: dict[str, DeviceScript] = field(default_factory=dict)  # action -> script
    loaded_models: list[str] = field(default_factory=list)  # For compute devices
    status: DeviceStatus = DeviceStatus.OFFLINE
    last_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict = field(default_factory=dict)
    
    def is_compute(self) -> bool:
        """Check if device can run inference."""
        return self.device_type == DeviceType.COMPUTE or "inference" in self.capabilities
    
    def is_online(self) -> bool:
        return self.status == DeviceStatus.ONLINE
    
    def has_capability(self, cap: str) -> bool:
        return cap in self.capabilities
        
    def is_host(self) -> bool:
        return self.role == DeviceRole.HOST
        
    def is_trusted(self) -> bool:
        return self.trust_level == TrustLevel.TRUSTED
    
    def to_dict(self) -> dict:
        return {
            "device_id": self.device_id,
            "name": self.name,
            "device_type": self.device_type.value,
            "role": self.role.value,
            "trust_level": self.trust_level.value,
            "manager_id": self.manager_id,
            "hardware": self.hardware.to_dict(),
            "software": self.software.to_dict(),
            "connection": self.connection.to_dict() if self.connection else None,
            "load": self.load.to_dict(),
            "capabilities": self.capabilities,
            "loaded_models": self.loaded_models,
            "status": self.status.value,
            "last_seen": self.last_seen.isoformat(),
            "registered_at": self.registered_at.isoformat(),
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Device":
        conn_data = data.get("connection")
        return cls(
            device_id=data["device_id"],
            name=data["name"],
            device_type=DeviceType(data["device_type"]),
            role=DeviceRole(data.get("role", "host")),
            trust_level=TrustLevel(data.get("trust_level", "trusted")),
            manager_id=data.get("manager_id"),
            hardware=HardwareSpecs.from_dict(data.get("hardware", {})),
            software=SoftwareSpecs.from_dict(data.get("software", {})),
            connection=ConnectionInfo.from_dict(conn_data) if conn_data else None,
            load=DeviceLoad.from_dict(data.get("load", {})),
            capabilities=data.get("capabilities", []),
            loaded_models=data.get("loaded_models", []),
            status=DeviceStatus(data.get("status", "offline")),
            last_seen=datetime.fromisoformat(data["last_seen"]) if "last_seen" in data else datetime.now(timezone.utc),
            registered_at=datetime.fromisoformat(data["registered_at"]) if "registered_at" in data else datetime.now(timezone.utc),
            metadata=data.get("metadata", {}),
        )


class HardwareRegistry:
    """
    Registry of all devices on the Velvet mesh.
    
    Devices announce themselves over Zenoh and maintain heartbeats.
    The registry tracks online/offline status and capabilities.
    """
    
    def __init__(self, heartbeat_timeout_seconds: float = 30.0):
        self._devices: dict[str, Device] = {}
        self._heartbeat_timeout = heartbeat_timeout_seconds
        self._listeners: list[Callable[[Device, str], Awaitable[None]]] = []
        self._cleanup_task: asyncio.Task | None = None
        self._heartbeat_task: asyncio.Task | None = None
        
    async def start(self):
        """Start the registry and cleanup task."""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Hardware registry started")
        
    async def stop(self):
        """Stop the registry."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("Hardware registry stopped")

    def start_heartbeat(self, device_id: str, interval: float = 10.0):
        """Start publishing heartbeats for a local device to keep it online."""
        self._heartbeat_task = asyncio.create_task(
            self._heartbeat_loop(device_id, interval)
        )
        logger.info(f"Heartbeat started for {device_id} (every {interval}s)")

    async def _heartbeat_loop(self, device_id: str, interval: float):
        """Periodically refresh last_seen for the local device and publish on mesh."""
        from velvet.fabric import get_fabric, MessageType
        fabric = get_fabric()
        
        while True:
            await asyncio.sleep(interval)
            device = self._devices.get(device_id)
            if device:
                device.last_seen = datetime.now(timezone.utc)
                device.status = DeviceStatus.ONLINE
                # Publish on mesh so remote registries see it too
                try:
                    await fabric.publish(
                        MessageType.HEARTBEAT.value,
                        {"device_id": device_id, "timestamp": device.last_seen.isoformat()}
                    )
                except Exception:
                    pass  # Don't crash on publish failure
        
    async def _cleanup_loop(self):
        """Periodically mark stale devices as offline."""
        while True:
            await asyncio.sleep(10)
            now = datetime.now(timezone.utc)
            for device in self._devices.values():
                if device.status == DeviceStatus.ONLINE:
                    elapsed = (now - device.last_seen).total_seconds()
                    if elapsed > self._heartbeat_timeout:
                        device.status = DeviceStatus.OFFLINE
                        logger.warning(f"Device {device.device_id} went offline (no heartbeat)")
                        await self._notify_listeners(device, "offline")
    
    async def register(self, device: Device) -> None:
        """Register or update a device."""
        existing = self._devices.get(device.device_id)
        device.last_seen = datetime.now(timezone.utc)
        device.status = DeviceStatus.ONLINE
        self._devices[device.device_id] = device
        
        if existing:
            # logger.debug(f"Device updated: {device.device_id}")
            await self._notify_listeners(device, "updated")
        else:
            logger.info(f"Device registered: {device.device_id} ({device.name}, {device.device_type.value}, {device.role.value})")
            await self._notify_listeners(device, "registered")
    
    async def heartbeat(self, device_id: str) -> bool:
        """Update last_seen for a device."""
        device = self._devices.get(device_id)
        if device:
            device.last_seen = datetime.now(timezone.utc)
            if device.status != DeviceStatus.ONLINE:
                device.status = DeviceStatus.ONLINE
                logger.info(f"Device {device_id} back online")
                await self._notify_listeners(device, "online")
            return True
        return False
    
    async def unregister(self, device_id: str) -> bool:
        """Remove a device from the registry."""
        device = self._devices.pop(device_id, None)
        if device:
            logger.info(f"Device unregistered: {device_id}")
            await self._notify_listeners(device, "unregistered")
            return True
        return False
    
    def get_device(self, device_id: str) -> Device | None:
        """Get a device by ID."""
        return self._devices.get(device_id)
    
    def get_all_devices(self) -> list[Device]:
        """Get all registered devices."""
        return list(self._devices.values())
    
    def get_online_devices(self) -> list[Device]:
        """Get all online devices."""
        return [d for d in self._devices.values() if d.is_online()]
    
    def find_by_type(self, device_type: DeviceType) -> list[Device]:
        """Find devices by type."""
        return [d for d in self._devices.values() if d.device_type == device_type]
    
    def find_by_capability(self, capability: str, online_only: bool = True) -> list[Device]:
        """Find devices with a specific capability."""
        devices = self._devices.values()
        if online_only:
            devices = [d for d in devices if d.is_online()]
        return [d for d in devices if d.has_capability(capability)]
    
    def find_compute_devices(self, online_only: bool = True) -> list[Device]:
        """Find devices capable of running inference."""
        devices = self._devices.values()
        if online_only:
            devices = [d for d in devices if d.is_online()]
        return [d for d in devices if d.is_compute()]
    
    def find_by_model(self, model_id: str, online_only: bool = True) -> list[Device]:
        """Find devices that have a specific model loaded."""
        devices = self._devices.values()
        if online_only:
            devices = [d for d in devices if d.is_online()]
        return [d for d in devices if model_id in d.loaded_models]
    
    def add_listener(self, callback: Callable[[Device, str], Awaitable[None]]):
        """Add a listener for device events."""
        self._listeners.append(callback)
    
    async def _notify_listeners(self, device: Device, event: str):
        """Notify all listeners of a device event."""
        for listener in self._listeners:
            try:
                await listener(device, event)
            except Exception as e:
                logger.error(f"Error in device listener: {e}")
    
    def get_stats(self) -> dict:
        """Get registry statistics."""
        online = [d for d in self._devices.values() if d.is_online()]
        return {
            "total_devices": len(self._devices),
            "online_devices": len(online),
            "by_type": {
                t.value: len([d for d in self._devices.values() if d.device_type == t])
                for t in DeviceType
            },
            "compute_capable": len([d for d in self._devices.values() if d.is_compute()]),
        }


# ============================================================================
# Zenoh Integration
# ============================================================================

async def create_registry_with_fabric() -> HardwareRegistry:
    """
    Create a HardwareRegistry integrated with Zenoh fabric.
    
    Listens for device announcements and heartbeats.
    """
    from .fabric import get_fabric, MessageType
    
    registry = HardwareRegistry()
    fabric = get_fabric()
    
    async def on_device_announce(msg):
        """Handle device announcement."""
        data = msg.payload
        device = Device.from_dict(data)
        await registry.register(device)
    
    async def on_heartbeat(msg):
        """Handle device heartbeat."""
        payload = msg.payload
        device_id = payload.get("device_id")
        if device_id:
            await registry.heartbeat(device_id)
            # Update load if present
            device = registry.get_device(device_id)
            if device and "load" in payload:
                device.load = DeviceLoad.from_dict(payload["load"])
                # logger.debug(f"Updated load for {device_id}: tasks={device.load.active_tasks}")
            
    async def on_device_leave(msg):
        """Handle device leave."""
        device_id = msg.payload.get("device_id")
        if device_id:
            await registry.unregister(device_id)
    
    # Subscribe to device topics
    await fabric.subscribe(MessageType.MESH_DEVICE_ANNOUNCE.value, on_device_announce)
    await fabric.subscribe(MessageType.MESH_DEVICE_HEARTBEAT.value, on_heartbeat)
    await fabric.subscribe(MessageType.MESH_DEVICE_LEAVE.value, on_device_leave)
    
    await registry.start()
    return registry


# ============================================================================
# Self-Detection Utilities
# ============================================================================

def detect_local_hardware() -> HardwareSpecs:
    """Auto-detect hardware specs of the local machine."""
    import platform
    import os
    
    specs = HardwareSpecs(
        cpu=platform.processor() or platform.machine(),
        cpu_cores=os.cpu_count() or 1,
    )
    
    # Try to get RAM
    try:
        import psutil
        specs.ram_gb = round(psutil.virtual_memory().total / (1024**3), 1)
    except ImportError:
        pass
    
    # Try to detect NVIDIA GPU via Python API (no subprocess)
    try:
        import pynvml
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        name = pynvml.nvmlDeviceGetName(handle)
        if isinstance(name, bytes):
            name = name.decode("utf-8")
        specs.gpu = name
        mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        specs.gpu_vram_gb = round(mem_info.total / (1024**3), 1)
        pynvml.nvmlShutdown()
    except Exception:
        pass
    
    return specs


def detect_local_software() -> SoftwareSpecs:
    """Auto-detect software specs of the local machine."""
    import platform
    import sys
    
    specs = SoftwareSpecs(
        os=platform.system(),
        os_version=platform.release(),
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    )
    
    # Try to detect CUDA/driver version via Python API (no subprocess)
    try:
        import pynvml
        pynvml.nvmlInit()
        specs.cuda_version = pynvml.nvmlSystemGetDriverVersion()
        if isinstance(specs.cuda_version, bytes):
            specs.cuda_version = specs.cuda_version.decode("utf-8")
        pynvml.nvmlShutdown()
    except Exception:
        pass
    
    return specs


def create_local_device(device_id: str, name: str, device_type: DeviceType) -> Device:
    """Create a Device object representing the local machine."""
    return Device(
        device_id=device_id,
        name=name,
        device_type=device_type,
        hardware=detect_local_hardware(),
        software=detect_local_software(),
        capabilities=_detect_capabilities(),
    )


def _detect_capabilities() -> list[str]:
    """Detect capabilities of the local machine."""
    caps = []
    
    # Check for GPU inference
    try:
        import torch
        if torch.cuda.is_available():
            caps.append("inference")
            caps.append("cuda")
    except ImportError:
        pass
    
    # Check for audio
    try:
        import pyaudio
        caps.append("audio_capture")
    except ImportError:
        pass
    
    # Check for TTS
    try:
        from .audio import TextToSpeech
        caps.append("tts")
    except ImportError:
        pass
    
    return caps


# ============================================================================
# Singleton
# ============================================================================

_registry: HardwareRegistry | None = None


def get_registry() -> HardwareRegistry:
    """Get the global hardware registry."""
    if _registry is None:
        raise RuntimeError("Hardware registry not initialized. Call init_registry() first.")
    return _registry


async def init_registry(with_fabric: bool = True) -> HardwareRegistry:
    """Initialize the global hardware registry."""
    global _registry
    if with_fabric:
        _registry = await create_registry_with_fabric()
    else:
        _registry = HardwareRegistry()
        await _registry.start()
    return _registry
