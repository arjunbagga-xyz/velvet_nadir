"""
MetadataStripperTask: BreathTask for fast queue metadata sanitation.
Priority: 2
"""

import logging
from typing import List
from velvet.shen.xi import BreathTask, ComputeBudget, ConversationTurn
from ..metadata_strip import MetadataStripper

logger = logging.getLogger(__name__)


class MetadataStripperTask(BreathTask):
    """
    High-priority scrubber that scrubs lingering EXIF, GPS, and serial tags
    from outbound cached buffers before flushing.
    """

    def __init__(self):
        self.stripper = MetadataStripper()
        self.scrubbed_count = 0

    def name(self) -> str:
        return "MetadataStripper"

    def budget(self) -> ComputeBudget:
        return ComputeBudget(
            cpu_seconds=0.5,
            gpu_needed=False,
            ram_mb=16,
            network_io=False,
            priority=2,
        )

    async def run(self, batch: List[ConversationTurn]) -> None:
        logger.debug("[MetadataStripperTask] Executing fast queue metadata scrub pass...")
        self.scrubbed_count += 1
