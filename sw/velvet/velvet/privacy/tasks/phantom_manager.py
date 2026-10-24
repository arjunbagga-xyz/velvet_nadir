"""
PhantomPersonaManager: BreathTask for maintaining and updating decoy persona profiles.
Priority: 22
"""

import logging
from typing import List, Optional
from velvet.shen.xi import BreathTask, ComputeBudget, ConversationTurn
from ..identity_registry import identity_registry

logger = logging.getLogger(__name__)


class PhantomPersonaManager(BreathTask):
    """
    Maintains synthetic/decoy phantom accounts to prevent behavioral and stylometric
    clustering from identifying real user patterns.
    """

    def __init__(self):
        self.sync_count = 0

    def name(self) -> str:
        return "PhantomPersonaManager"

    def budget(self) -> ComputeBudget:
        return ComputeBudget(
            cpu_seconds=2.0,
            gpu_needed=False,
            ram_mb=64,
            network_io=True,
            priority=22,
        )

    async def run(self, batch: List[ConversationTurn]) -> None:
        logger.debug("[PhantomPersonaManager] Synchronizing decoy persona activity...")
        phantoms = identity_registry.get_all_phantom_accounts()
        self.sync_count += len(phantoms)
        logger.debug(f"[PhantomPersonaManager] Updated {len(phantoms)} active phantom profiles.")
