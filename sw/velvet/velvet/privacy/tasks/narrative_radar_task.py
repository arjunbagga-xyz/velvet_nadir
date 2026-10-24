"""
NarrativeRadarTask: BreathTask for executing periodic narrative analysis cycles.
Priority: 12
"""

import logging
from typing import List, Optional
from velvet.shen.xi import BreathTask, ComputeBudget, ConversationTurn
from ..narrative_radar import NarrativeRadar, DailyIntelligenceBrief

logger = logging.getLogger(__name__)


class NarrativeRadarTask(BreathTask):
    """
    Executes daily narrative radar collection, physical event correlation,
    and demographic virality analysis within Xi's scheduler.
    """

    def __init__(self, radar: Optional[NarrativeRadar] = None):
        self.radar = radar or NarrativeRadar()
        self.last_brief: Optional[DailyIntelligenceBrief] = None

    def name(self) -> str:
        return "NarrativeRadar"

    def budget(self) -> ComputeBudget:
        return ComputeBudget(
            cpu_seconds=5.0,
            gpu_needed=False,
            ram_mb=128,
            network_io=True,
            priority=12,
        )

    async def run(self, batch: List[ConversationTurn]) -> None:
        logger.info("[NarrativeRadarTask] Executing scheduled radar cycle...")
        try:
            self.last_brief = await self.radar.execute_radar_cycle()
        except Exception as e:
            logger.error(f"[NarrativeRadarTask] Radar cycle failed: {e}")
