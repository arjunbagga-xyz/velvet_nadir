"""
Triangulation (三角): Spatial learning task.

Analyzes location history in Jing to automatically infer new geofences
for frequently visited locations.
"""
from loguru import logger
from velvet.shen.xi import BreathTask, ComputeBudget, ConversationTurn


class TriangulationTask(BreathTask):
    """
    Scans recent location events or conversation context to register
    new frequent places automatically.
    """
    def __init__(self, locus=None):
        self._locus = locus

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
        if not batch:
            return
            
        # In a real implementation this would query Jing for location traces,
        # run DBSCAN clustering, and register new geofences.
        # For Sprint 13 MVP, we just do a mock learning pass.
        
        if self._locus:
            logger.debug("[Triangulation] Analyzed new coordinate clusters.")
            # e.g., self._locus.add_geofence("gym", lat, lon, radius)
