"""
Inari (稲荷): The Fox of Discernment / Trust Cache Refresh.

Named after the Shinto deity of foxes and wisdom — Inari sees what others miss.

Inari is a BreathTask that refreshes the TrustEngine hot cache and
the ModelAffinityTracker from Jing between conversations.
"""

from __future__ import annotations

from loguru import logger

from velvet.shen.xi import BreathTask, ComputeBudget, ConversationTurn


class Inari(BreathTask):
    """
    Inari (稲荷): Trust cache materialization BreathTask.

    Low-priority task that refreshes trust decisions and model affinity
    data from Jing into hot caches between conversations.
    """

    def __init__(self, trust_engine=None, affinity_tracker=None):
        self._trust = trust_engine
        self._affinity = affinity_tracker

    def name(self) -> str:
        return "inari"

    def budget(self) -> ComputeBudget:
        return ComputeBudget(
            cpu_seconds=1.0,
            gpu_needed=False,
            ram_mb=32,
            network_io=False,
            priority=7,  # Low priority — runs after Fuxi and Agni
        )

    async def run(self, batch: list[ConversationTurn]) -> None:
        """Refresh trust and affinity caches from Jing."""

        # 1. Refresh trust cache
        if self._trust:
            try:
                await self._trust.refresh_cache()
            except Exception as e:
                logger.error(f"[Inari] Trust cache refresh failed: {e}")

        # 2. Refresh affinity cache
        if self._affinity:
            try:
                await self._affinity.refresh_cache()
            except Exception as e:
                logger.error(f"[Inari] Affinity cache refresh failed: {e}")

        logger.debug("[Inari] Cache refresh complete")
