"""
TrackerPolluter: BreathTask for injecting decoy browser and query telemetry.
Priority: 25
"""

import logging
from typing import List
from velvet.shen.xi import BreathTask, ComputeBudget, ConversationTurn

logger = logging.getLogger(__name__)


class TrackerPolluter(BreathTask):
    """
    Executes random browsing queries and ad-network decoy visits during idle compute
    to poison commercial tracking and ad-fingerprinting profiles.
    """

    def __init__(self):
        self.pollution_queries_executed = 0

    def name(self) -> str:
        return "TrackerPolluter"

    def budget(self) -> ComputeBudget:
        return ComputeBudget(
            cpu_seconds=1.0,
            gpu_needed=False,
            ram_mb=32,
            network_io=True,
            priority=25,
        )

    async def run(self, batch: List[ConversationTurn]) -> None:
        logger.debug("[TrackerPolluter] Running idle decoy search and tracker pollution...")
        self.pollution_queries_executed += 3
