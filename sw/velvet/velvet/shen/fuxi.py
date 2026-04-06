"""
Fuxi (伏羲): The Consolidator.

Named after Fu Xi from Chinese mythology — the sage who observed patterns
in nature and created the Eight Trigrams (八卦), bringing order from chaos.

Fuxi is a BreathTask that consolidates conversation turns into long-term memory.
It embeds each turn into Jing (Aether tier), identifies skill usage patterns
for Po reflex learning, and prepares data for Saraswati (workflow learning).
"""

from __future__ import annotations

from loguru import logger

from velvet.shen.xi import BreathTask, ComputeBudget, ConversationTurn


class Fuxi(BreathTask):
    """
    Fuxi (伏羲): Consolidation BreathTask.

    Processes recent conversation turns:
    1. Embeds each turn into Jing (long-term memory)
    2. Groups turns by skill → identifies patterns for Po reflex learning
    3. Feeds data to Saraswati pipeline (when Phase 4 is ready)
    """

    def __init__(self, jing=None, po=None):
        self._jing = jing
        self._po = po

    def name(self) -> str:
        return "fuxi"

    def budget(self) -> ComputeBudget:
        return ComputeBudget(
            cpu_seconds=2.0,
            gpu_needed=False,
            gpu_vram_mb=0,
            ram_mb=64,
            network_io=False,
            priority=3,  # High priority — consolidation is core
        )

    async def run(self, batch: list[ConversationTurn]) -> None:
        """Consolidate conversation turns into long-term memory."""
        if not batch:
            return

        jing = self._get_jing()
        if not jing:
            logger.warning("[Fuxi] No Jing available, skipping consolidation")
            return

        # 1. Embed each turn into Jing
        embedded = 0
        for turn in batch:
            try:
                # Store the exchange as a coherent memory
                memory_text = (
                    f"User said: \"{turn.user_input}\"\n"
                    f"Velvet responded ({turn.routed_to}): \"{turn.response}\""
                )
                if turn.skill_used:
                    memory_text += f"\nSkill used: {turn.skill_used}"

                await jing.remember(memory_text, role="assistant", metadata={
                    "source": "fuxi_consolidation",
                    "skill_used": turn.skill_used or "",
                    "routed_to": turn.routed_to,
                    "timestamp": turn.timestamp,
                })
                embedded += 1
            except Exception as e:
                logger.error(f"[Fuxi] Failed to embed turn: {e}")

        logger.info(f"[Fuxi] Consolidated {embedded}/{len(batch)} turns into Jing")

        # 2. Identify skill patterns for Po reflex learning
        await self._learn_patterns(batch)

    async def _learn_patterns(self, batch: list[ConversationTurn]):
        """Identify repeated skill usage patterns for Po reflex learning."""
        po = self._get_po()
        if not po:
            return

        # Group turns by skill
        skill_groups: dict[str, list[ConversationTurn]] = {}
        for turn in batch:
            if turn.skill_used:
                skill_groups.setdefault(turn.skill_used, []).append(turn)

        # If a skill was used 3+ times in this batch, teach Po
        for skill_name, turns in skill_groups.items():
            if len(turns) >= 3:
                # Teach Po a pattern from the most recent usage
                latest = turns[-1]
                try:
                    if hasattr(po, 'learn_reflex'):
                        po.learn_reflex(
                            user_input=latest.user_input,
                            skill_name=skill_name,
                            params=latest.params,
                        )
                        logger.info(
                            f"[Fuxi] Taught Po reflex: '{latest.user_input[:40]}' → {skill_name}"
                        )
                except Exception as e:
                    logger.error(f"[Fuxi] Reflex learning failed: {e}")

    def _get_jing(self):
        """Lazy-load Jing."""
        if self._jing is None:
            try:
                from velvet.shen.jing import Jing
                self._jing = Jing()
            except Exception:
                pass
        return self._jing

    def _get_po(self):
        """Lazy-load Po."""
        if self._po is None:
            try:
                from velvet.shen.po import Po
                self._po = Po(start_vision_monitor=False)
            except Exception:
                pass
        return self._po
