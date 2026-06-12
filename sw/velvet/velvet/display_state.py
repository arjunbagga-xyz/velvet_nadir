"""
State serializers for the Display Bridge.
Translates Velvet internal dataclasses into the exact JSON shapes expected by the UI.
"""

from datetime import datetime
from velvet.devices import Device
from velvet.context import ContextWorkspace
from velvet.agents import AgentIdentity
from velvet.entities import HumanEntity, ExternalEntity
# Optional spatial support
try:
    from velvet.services.locus.engine import LocusEngine
except ImportError:
    LocusEngine = None

def serialize_device_for_ui(device: Device, locus=None) -> dict:
    """Serialize a Device into the UI's expected format."""
    
    # Resolve location
    loc = None
    loc_name = None
    if locus and hasattr(locus, "get_device_location"):
        loc_data = locus.get_device_location(device.device_id)
        if loc_data and "lat" in loc_data and "lon" in loc_data:
            loc = [loc_data["lat"], loc_data["lon"]]
            loc_name = loc_data.get("name", None)
            
    # Resolve peripherals
    peripherals = []
    # If the device is online, peripherals are 'active'. Otherwise 'offline' or 'inactive'.
    p_status = "active" if device.is_online() else "inactive"
    if device.hardware.has_camera:
        peripherals.append({"name": "Camera", "status": p_status})
    if device.hardware.has_microphone:
        peripherals.append({"name": "Microphone", "status": p_status})
    if device.hardware.has_gps:
        peripherals.append({"name": "GPS", "status": p_status})
    if getattr(device.hardware, 'has_speaker', False): # Failsafe since hardware specs vary
        peripherals.append({"name": "Speaker", "status": p_status})

    return {
        "id": device.device_id,
        "name": device.name,
        "type": device.display_type,             # "compute"| "sensor"| "hybrid"
        "status": "degraded" if device.status.value == "error" else device.status.value,
        "load": int(device.load.cpu_percent) if device.load else 0,
        "battery": int(device.load.battery_percent) if device.load and device.load.battery_percent is not None else None,
        "trust_level": device.trust_level.value,
        "models": device.loaded_models,
        "capabilities": device.capabilities,
        "location": loc,
        "locationName": loc_name,
        "peripherals": peripherals,
        "files": [], # Populated dynamically by file explorer
        "ui_position": device.metadata.get("ui_position", {})
    }


def serialize_workspace_for_ui(ws: ContextWorkspace, device_map: dict[str, Device], agent_map: dict[str, AgentIdentity], human_map: dict[str, HumanEntity]) -> dict:
    """Serialize a ContextWorkspace into the UI's expected format."""
    
    agents = []
    for aid in ws.agent_ids:
        if aid in agent_map:
            agt = agent_map[aid]
            agents.append({"name": agt.agent_id, "task": agt.current_task, "status": agt.status})
            
    humans = []
    for hid in ws.human_ids:
        if hid in human_map:
            hum = human_map[hid]
            humans.append({"name": hum.name, "task": hum.current_task, "status": hum.status})
            
    hardware = []
    # Mix device_ids and robot_ids for UI's list formats
    for did in ws.device_ids:
        if did in device_map:
            dev = device_map[did]
            hardware.append({"name": dev.name, "task": "Active", "status": dev.status.value})
            
    robots = []
    for rid in ws.robot_ids:
        if rid in device_map:
            rob = device_map[rid]
            robots.append({"name": rob.name, "task": "Active", "status": rob.status.value})

    return {
        "id": ws.workspace_id,
        "name": ws.name,
        # Default the type string to lowercase of the enum name
        "type": ws.track_type.name.lower() if ws.track_type else "custom",
        "subtype": ws.subtype,
        "status": ws.status,
        "progress": int(ws.progress),
        "parent_id": ws.parent_id,
        "x": ws.ui_position.get("x", 0),
        "y": ws.ui_position.get("y", 0),
        "agents": agents,
        "humans": humans,
        "hardware": hardware,
        "robots": robots,
        "artifacts": ws.artifacts
    }


def serialize_agent_for_ui(agent: AgentIdentity) -> dict:
    """Serialize AgentIdentity for the agent tab."""
    return {
        "id": agent.agent_id,
        "name": agent.agent_id,
        "type": agent.agent_type,
        "role": agent.role.value,
        "status": agent.status,
        "task": agent.current_task,
        "trust_level": agent.trust_level,
        "capabilities": agent.capabilities,
        "custom_fields": agent.custom_fields,
        "parent_id": agent.parent_id
    }


def serialize_log_event(msg_id: str, ts: datetime, source: str, msg_type: str, content: str) -> dict:
    """Serialize a system event for the log view."""
    
    # Map Velvet message types to UI levels
    level = "info"
    if "wake" in msg_type.lower():
        level = "wake"
    elif "reasoning" in msg_type.lower() or "skill" in msg_type.lower():
        level = "reasoning"
    elif "alert" in msg_type.lower() or "security" in msg_type.lower() or "error" in msg_type.lower():
        level = "alert"
        
    # Map high-level type for UI icons
    display_type = "system"
    if "audio" in msg_type.lower():
        display_type = "audio"
    elif "vision" in msg_type.lower():
        display_type = "video"
        
    return {
        "id": msg_id,
        "timestamp": ts.strftime("%H:%M:%S"),
        "source": source,
        "type": display_type,
        "content": content,
        "level": level
    }

def serialize_memory_graph(nodes: list[dict], edges: list[dict]) -> dict:
    """Serialize Jing memory structures into D3-compatible node/link arrays.
    nodes: list of dicts with at least 'id', 'type'
    edges: list of dicts with 'source', 'target', 'weight', 'label'
    """
    
    # Map Node types to UI tiers
    def _get_tier(n_type: str) -> int:
        n = str(n_type).lower()
        if n in ("context", "workspace", "project"): return 1
        if n in ("agent", "system", "service"): return 2
        return 3 # Entities, assets, materials, data
        
    formatted_nodes = []
    for n in nodes:
        formatted_nodes.append({
            "id": n["id"],
            "tier": _get_tier(n.get("type", "entity")),
            "type": n.get("type", "entity")
        })
        
    formatted_links = []
    for e in edges:
        formatted_links.append({
            "source": e["source"],
            "target": e["target"],
            "value": e.get("weight", 1),
            "label": e.get("label", "")
        })
        
    return {
        "nodes": formatted_nodes,
        "links": formatted_links
    }
