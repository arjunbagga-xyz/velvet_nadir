from __future__ import annotations

import json
from pathlib import Path
from loguru import logger

from velvet.config import get_config
from velvet.shen.xi import BreathTask, ComputeBudget, ConversationTurn
from velvet.fabric import get_fabric, MessageType

class SkillApprovalTask(BreathTask):
    """
    Background skill approval checker.

    Runs between conversations to check if any skills are pending approval
    and proactively prompts the user if appropriate.
    """

    def __init__(self):
        self.config = get_config()
        self._pending_file = Path(self.config.storage.data_dir) / "pending_skills.json"
        self._last_prompt_time = 0.0

    def name(self) -> str:
        return "skill_approval"

    def budget(self) -> ComputeBudget:
        return ComputeBudget(
            cpu_seconds=0.5,
            gpu_needed=False,
            ram_mb=16,
            network_io=False,
            priority=9,  # Low priority, runs during idle
        )

    async def run(self, batch: list[ConversationTurn]) -> None:
        """Check for pending skills and notify/prompt if needed."""
        if not self._pending_file.exists():
            return

        try:
            pending = json.loads(self._pending_file.read_text())
        except Exception:
            return

        if not pending:
            return

        # Simple rate limit: only prompt once every 10 minutes
        import time
        now = time.time()
        if now - self._last_prompt_time < 600:
            return

        # Pick the first pending skill
        skill_name = list(pending.keys())[0]
        skill_data = pending[skill_name]
        
        logger.info(f"[SkillApprovalTask] Found pending skill: {skill_name}. Emitting proactive approval event.")
        self._last_prompt_time = now

        # Publish approval message to fabric
        fabric = get_fabric()
        await fabric.publish(
            MessageType.SKILL_PENDING_APPROVAL.value,
            {
                "skill_name": skill_name,
                "description": skill_data.get("description", ""),
                "proactive": True
            }
        )
