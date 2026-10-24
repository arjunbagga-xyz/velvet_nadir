"""
Triangulation (三角): Spatial learning task.

Analyzes location history in Jing to automatically infer new geofences
for frequently visited locations.
"""
from loguru import logger
from velvet.shen.xi import BreathTask, ComputeBudget, ConversationTurn


import math
from typing import List, Tuple
from loguru import logger
from velvet.shen.xi import BreathTask, ComputeBudget, ConversationTurn


class TriangulationTask(BreathTask):
    """
    Scans recent location events or conversation context to register
    new frequent places automatically via spatial centroid clustering.
    """
    def __init__(self, locus=None):
        self._locus = locus
        self._discovered_clusters: dict[str, tuple[float, float, int]] = {}

    def name(self) -> str:
        return "triangulation"

    def budget(self) -> ComputeBudget:
        return ComputeBudget(
            cpu_seconds=1.5,
            gpu_needed=False,
            gpu_vram_mb=0,
            ram_mb=128,
            priority=6,
        )

    async def run(self, batch: list[ConversationTurn]) -> None:
        if not batch or not self._locus:
            return

        # 1. Extract lat/lon pairs from batch text and location updates
        coords: List[Tuple[float, float]] = []
        for turn in batch:
            u_input = str(getattr(turn, "user_input", ""))
            resp = str(getattr(turn, "response", ""))
            text = (u_input + " " + resp).lower()
            # Simple regex search for lat, lon pattern if mentioned in logs
            import re
            matches = re.findall(r"(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)", text)
            for m in matches:
                try:
                    lat, lon = float(m[0]), float(m[1])
                    if -90 <= lat <= 90 and -180 <= lon <= 180:
                        coords.append((lat, lon))
                except ValueError:
                    pass

        # 2. Cluster coordinates (Centroid distance < 100 meters)
        from velvet.shen.locus import haversine_distance
        for lat, lon in coords:
            matched = False
            for name, (clat, clon, count) in list(self._discovered_clusters.items()):
                if haversine_distance(lat, lon, clat, clon) <= 100.0:
                    # Update cluster centroid running average
                    new_count = count + 1
                    new_lat = clat + (lat - clat) / new_count
                    new_lon = clon + (lon - clon) / new_count
                    self._discovered_clusters[name] = (new_lat, new_lon, new_count)
                    matched = True

                    # If visited 3+ times, promote to active geofence
                    if new_count >= 3:
                        fence_name = f"auto_cluster_{name}"
                        self._locus.add_geofence(fence_name, new_lat, new_lon, radius=100.0)
                        logger.info(f"[Triangulation] Auto-discovered frequent geofence: {fence_name} at ({new_lat:.4f}, {new_lon:.4f})")
                    break

            if not matched:
                c_id = f"c_{len(self._discovered_clusters) + 1}"
                self._discovered_clusters[c_id] = (lat, lon, 1)

        logger.debug(f"[Triangulation] Analyzed {len(coords)} coordinates, tracking {len(self._discovered_clusters)} clusters.")
