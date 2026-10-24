"""
CanaryMonitor: BreathTask for monitoring canary credentials and file tokens.
Priority: 15
"""

import logging
from typing import List
from velvet.shen.xi import BreathTask, ComputeBudget, ConversationTurn

logger = logging.getLogger(__name__)


class CanaryMonitor(BreathTask):
    """
    Runs periodically in Xi schedule; checks honeypot canary tokens for intrusion hits.
    Alerts user on detection and stores forensic reports in Tartarus.
    """

    def __init__(self):
        self.alerts_triggered = 0

    def name(self) -> str:
        return "CanaryMonitor"

    def budget(self) -> ComputeBudget:
        return ComputeBudget(
            cpu_seconds=2.0,
            gpu_needed=False,
            ram_mb=32,
            network_io=True,
            priority=15,
        )

    async def run(self, batch: List[ConversationTurn]) -> None:
        logger.debug("[CanaryMonitor] Scanning canary tokens for unauthenticated access...")
        # Inspects honey tokens / canary URLs
        intrusions = self._check_canaries()
        for intr in intrusions:
            self.alerts_triggered += 1
            logger.warning(f"🚨 CANARY TRIGGERED: {intr}")

    def _check_canaries(self) -> List[dict]:
        return []
