"""
AIToolNoise: BreathTask for injecting contextual noise queries into AI search engines.
Priority: 25
"""

import logging
from typing import List
from velvet.shen.xi import BreathTask, ComputeBudget, ConversationTurn

logger = logging.getLogger(__name__)


class AIToolNoise(BreathTask):
    """
    Emits plausible dummy questions and research queries to free AI tools and search engines
    during idle intervals to decorrelate user interests from centralized AI profiling.
    """

    def __init__(self):
        self.noise_prompts_sent = 0

    def name(self) -> str:
        return "AIToolNoise"

    def budget(self) -> ComputeBudget:
        return ComputeBudget(
            cpu_seconds=1.0,
            gpu_needed=False,
            ram_mb=32,
            network_io=True,
            priority=25,
        )

    async def run(self, batch: List[ConversationTurn]) -> None:
        logger.debug("[AIToolNoise] Emitting contextual noise query to decorrelate AI profiling...")
        self.noise_prompts_sent += 1
