"""
Device Mesh Skills for Velvet Nadir.

Provides skills for managing devices and models on the mesh.
"""

from ..skills import (
    skill,
    SkillCategory,
    SkillParameter,
    SkillResult,
    AutonomyLevel,
)


@skill(
    name="list_devices",
    description="List all devices on the Velvet mesh",
    category=SkillCategory.DIGITAL,
    parameters=[],
    autonomy=AutonomyLevel.LEVEL_0,
    tags=["mesh", "device", "status"],
)
async def list_devices() -> SkillResult:
    """List all registered devices."""
    from ..devices import get_registry, DeviceType
    
    try:
        registry = get_registry()
        devices = registry.get_all_devices()
        
        if not devices:
            return SkillResult.ok(
                data={"devices": []},
                speak="No devices registered on the mesh yet.",
            )
        
        device_list = []
        for d in devices:
            device_list.append({
                "id": d.device_id,
                "name": d.name,
                "type": d.device_type.value,
                "online": d.is_online(),
                "gpu": d.hardware.gpu or None,
            })
        
        online_count = len([d for d in devices if d.is_online()])
        return SkillResult.ok(
            data={"devices": device_list},
            speak=f"There are {len(devices)} devices on the mesh, {online_count} online.",
        )
    except RuntimeError:
        return SkillResult.ok(
            data={"devices": []},
            speak="Device registry not initialized. Run in mesh mode to enable.",
        )


@skill(
    name="list_models",
    description="List all ML models available across devices",
    category=SkillCategory.DIGITAL,
    parameters=[],
    autonomy=AutonomyLevel.LEVEL_0,
    tags=["mesh", "model", "inference"],
)
async def list_models() -> SkillResult:
    """List all registered models."""
    from ..models import get_model_registry, ModelType
    
    try:
        registry = get_model_registry()
        stats = registry.get_stats()
        
        if stats["total_models"] == 0:
            return SkillResult.ok(
                data={"models": []},
                speak="No models registered yet.",
            )
        
        models = []
        for model_type in ModelType:
            for m in registry.find_models_by_type(model_type):
                models.append({
                    "id": m.model_id,
                    "name": m.name,
                    "type": m.model_type.value,
                    "devices": registry.get_model_devices(m.model_id),
                })
        
        return SkillResult.ok(
            data={"models": models, "stats": stats},
            speak=f"There are {stats['total_models']} models across {stats['devices_with_models']} devices.",
        )
    except RuntimeError:
        return SkillResult.ok(
            data={"models": []},
            speak="Model registry not initialized.",
        )


@skill(
    name="add_device",
    description="Add a new device to the Velvet mesh",
    category=SkillCategory.DIGITAL,
    parameters=[
        SkillParameter("name", "string", "Friendly name for the device"),
        SkillParameter("device_type", "string", "Type: compute, sensor, vehicle, robot, iot"),
        SkillParameter("ip", "string", "IP address (optional)", required=False),
    ],
    autonomy=AutonomyLevel.LEVEL_2,
    tags=["mesh", "device", "add"],
)
async def add_device(
    name: str,
    device_type: str = "compute",
    ip: str = "",
) -> SkillResult:
    """Add a device to the mesh."""
    from ..devices import Device, DeviceType, HardwareSpecs, SoftwareSpecs, get_registry
    
    try:
        dtype = DeviceType(device_type.lower())
    except ValueError:
        types = ", ".join(t.value for t in DeviceType)
        return SkillResult.fail(f"Invalid device type. Use: {types}")
    
    device_id = name.lower().replace(" ", "-")
    if ip:
        device_id += f"-{ip.replace('.', '-')}"
    
    device = Device(
        device_id=device_id,
        name=name,
        device_type=dtype,
        hardware=HardwareSpecs(),
        software=SoftwareSpecs(),
        capabilities=[],
        metadata={"ip": ip} if ip else {},
    )
    
    try:
        registry = get_registry()
        await registry.register(device)
        
        return SkillResult.ok(
            data={"device_id": device_id, "name": name, "type": dtype.value},
            speak=f"Added {name} to the mesh as a {dtype.value} device.",
        )
    except RuntimeError:
        return SkillResult.fail("Device registry not initialized.")


@skill(
    name="remove_device",
    description="Remove a device from the Velvet mesh",
    category=SkillCategory.DIGITAL,
    parameters=[
        SkillParameter("device_id", "string", "ID of the device to remove"),
    ],
    autonomy=AutonomyLevel.LEVEL_2,
    tags=["mesh", "device", "remove"],
)
async def remove_device(device_id: str) -> SkillResult:
    """Remove a device from the mesh."""
    from ..devices import get_registry
    
    try:
        registry = get_registry()
        device = registry.get_device(device_id)
        
        if not device:
            return SkillResult.fail(f"Device '{device_id}' not found.")
        
        await registry.unregister(device_id)
        return SkillResult.ok(
            data={"device_id": device_id},
            speak=f"Removed {device.name} from the mesh.",
        )
    except RuntimeError:
        return SkillResult.fail("Device registry not initialized.")


@skill(
    name="device_info",
    description="Get detailed information about a device",
    category=SkillCategory.DIGITAL,
    parameters=[
        SkillParameter("device_id", "string", "ID or name of the device"),
    ],
    autonomy=AutonomyLevel.LEVEL_0,
    tags=["mesh", "device", "info"],
)
async def device_info(device_id: str) -> SkillResult:
    """Get detailed device information."""
    from ..devices import get_registry
    
    try:
        registry = get_registry()
        device = registry.get_device(device_id)
        
        # Try partial match if not found
        if not device:
            devices = registry.get_all_devices()
            matches = [d for d in devices if device_id.lower() in d.device_id.lower() or device_id.lower() in d.name.lower()]
            if matches:
                device = matches[0]
        
        if not device:
            return SkillResult.fail(f"Device '{device_id}' not found.")
        
        info = {
            "device_id": device.device_id,
            "name": device.name,
            "type": device.device_type.value,
            "status": "online" if device.is_online() else "offline",
            "hardware": {
                "cpu": device.hardware.cpu,
                "cpu_cores": device.hardware.cpu_cores,
                "ram_gb": device.hardware.ram_gb,
                "gpu": device.hardware.gpu,
                "gpu_vram_gb": device.hardware.gpu_vram_gb,
            },
            "capabilities": device.capabilities,
            "models": device.loaded_models,
        }
        
        hw = device.hardware
        gpu_str = hw.gpu or "no GPU"
        return SkillResult.ok(
            data=info,
            speak=f"{device.name} is {'online' if device.is_online() else 'offline'}. It has {hw.cpu_cores} CPU cores, {hw.ram_gb}GB RAM, and {gpu_str}.",
        )
    except RuntimeError:
        return SkillResult.fail("Device registry not initialized.")


@skill(
    name="find_compute",
    description="Find available compute devices on the mesh",
    category=SkillCategory.DIGITAL,
    parameters=[
        SkillParameter("online_only", "bool", "Only show online devices", required=False, default=True),
    ],
    autonomy=AutonomyLevel.LEVEL_0,
    tags=["mesh", "compute", "find"],
)
async def find_compute(online_only: bool = True) -> SkillResult:
    """Find compute devices."""
    from ..devices import get_registry
    
    try:
        registry = get_registry()
        devices = registry.find_compute_devices(online_only=online_only)
        
        if not devices:
            return SkillResult.ok(
                data={"devices": []},
                speak="No compute devices available.",
            )
        
        device_list = [{
            "id": d.device_id,
            "name": d.name,
            "gpu": d.hardware.gpu,
            "vram_gb": d.hardware.gpu_vram_gb,
        } for d in devices]
        
        return SkillResult.ok(
            data={"devices": device_list},
            speak=f"Found {len(devices)} compute device(s): {', '.join(d.name for d in devices)}",
        )
    except RuntimeError:
        return SkillResult.fail("Device registry not initialized.")
