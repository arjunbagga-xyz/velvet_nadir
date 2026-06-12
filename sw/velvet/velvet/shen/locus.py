"""
Locus (定位): Spatial Awareness Engine.

Manages coordinate streams, tracks geofences, and evaluates spatial trust.
Uses Haversine formula to compute distances on the sphere.
"""

import math
from dataclasses import dataclass
from typing import Dict, List, Optional
from loguru import logger

from velvet.config import get_config

@dataclass
class Geofence:
    name: str
    lat: float
    lon: float
    radius_meters: float

@dataclass
class LocationUpdate:
    device_id: str
    lat: float
    lon: float
    timestamp: str
    accuracy_meters: float = 10.0


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great circle distance in meters between two points."""
    R = 6371000 # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


class LocusEngine:
    def __init__(self, start_subscriber: bool = True):
        self._config = get_config().locus
        self._enabled = self._config.enabled
        self._geofences: Dict[str, Geofence] = {}
        self._last_locations: Dict[str, LocationUpdate] = {}
        
        # Load static geofences from config
        self._load_config_fences()
        
        if self._enabled and start_subscriber:
            self._start()

    def _load_config_fences(self):
        for data in self._config.seed_fences:
            self.add_geofence(
                data['name'], 
                data['lat'], 
                data['lon'], 
                data.get('radius_meters', 100.0)
            )

    def _start(self):
        try:
            from velvet.fabric import get_fabric, MessageType
            fabric = get_fabric()
            # Subscribe to location updates
            fabric.subscribe(MessageType.LOCATION_UPDATE.value, self._handle_location)
            logger.info("[Locus] Subscribed to spatial coordinate streams.")
        except Exception as e:
            logger.error(f"[Locus] Failed to start subscriber: {e}")

    async def _handle_location(self, payload: dict):
        device_id = payload.get("device_id")
        lat = payload.get("lat")
        lon = payload.get("lon")
        
        if device_id and lat is not None and lon is not None:
            update = LocationUpdate(
                device_id=device_id,
                lat=lat,
                lon=lon,
                timestamp=payload.get("timestamp", ""),
                accuracy_meters=payload.get("accuracy", 10.0)
            )
            self._last_locations[device_id] = update
            
            # Check if this changed any geofence states and emit events
            self._check_geofence_triggers(update)

    def _check_geofence_triggers(self, update: LocationUpdate):
        # We could emit SPATIAL_FENCE_EVENT but keeping it simple for now
        pass

    def add_geofence(self, name: str, lat: float, lon: float, radius: float):
        self._geofences[name] = Geofence(name, lat, lon, radius)
        logger.debug(f"[Locus] Added geofence: {name} ({radius}m)")

    def get_device_location(self, device_id: str) -> Optional[LocationUpdate]:
        return self._last_locations.get(device_id)

    def is_device_in_fence(self, device_id: str, fence_name: str) -> bool:
        loc = self._last_locations.get(device_id)
        fence = self._geofences.get(fence_name)
        if not loc or not fence:
            return False
            
        dist = haversine_distance(loc.lat, loc.lon, fence.lat, fence.lon)
        return dist <= fence.radius_meters

    def get_current_fences(self, lat: float, lon: float) -> List[str]:
        """Return a list of geofence names that the given coordinates are inside."""
        inside = []
        for name, fence in self._geofences.items():
            if haversine_distance(lat, lon, fence.lat, fence.lon) <= fence.radius_meters:
                inside.append(name)
        return list(inside)
