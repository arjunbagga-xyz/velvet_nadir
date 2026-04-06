"""
Agni (अग्नि): The Sacred Fire / Memory Purification.

Named after the Hindu god of fire and purification — Agni burns away
the impure to reveal the essential.

Agni is a BreathTask that manages memory hygiene:
1. Deduplication — merge near-duplicate memories (cosine > 0.95)
2. Warm → Cold archival — low retention + low importance → Tartarus
3. Reinforce important — boost retention for important forgotten memories
4. Promote recently-queried cold memories back to Aether
5. Compact storage
"""

from __future__ import annotations

from loguru import logger

from velvet.shen.xi import BreathTask, ComputeBudget, ConversationTurn


class Agni(BreathTask):
    """
    Agni (अग्नि): Memory Purification BreathTask.

    Manages the full memory lifecycle:
      Aether (hot) → Mnemosyne (warm) → Tartarus (cold) → promoted back
    """

    def __init__(self, jing=None, tartarus=None):
        self._jing = jing
        self._tartarus = tartarus

    def name(self) -> str:
        return "agni"

    def budget(self) -> ComputeBudget:
        return ComputeBudget(
            cpu_seconds=3.0,
            gpu_needed=False,
            gpu_vram_mb=0,
            ram_mb=128,
            network_io=False,
            priority=5,  # Medium priority — runs after consolidation
        )

    async def run(self, batch: list[ConversationTurn]) -> None:
        """Run the full purification cycle."""
        jing = self._get_jing()
        if not jing:
            logger.warning("[Agni] No Jing available, skipping purification")
            return

        # 1. Archive low-value memories to Tartarus
        archived = await self._archive_cold(jing)

        # 2. Reinforce important memories that are decaying
        reinforced = await self._reinforce_important(jing)

        # 3. Promote recently-accessed cold memories back to Aether
        promoted = await self._promote_hot(jing)

        # 4. Compact storage
        await jing.compact()
        tartarus = self._get_tartarus(jing)
        if tartarus:
            tartarus.compact()

        logger.info(
            f"[Agni] Purification complete — "
            f"archived={archived}, reinforced={reinforced}, promoted={promoted}"
        )

    async def _archive_cold(self, jing) -> int:
        """Move low-retention, low-importance memories to Tartarus."""
        tartarus = self._get_tartarus(jing)
        if not tartarus:
            return 0

        archived = 0
        try:
            # Find memories with low retention AND low importance
            candidates = await jing.get_memories_by_retention(
                retention_below=0.1,
                importance_below=0.3,
                limit=20,
            )

            for mem in candidates:
                mem_id = mem.get("id", "")
                text = mem.get("text", mem.get("memory", ""))
                if not mem_id or not text:
                    continue

                # Archive to Tartarus
                tartarus.store(
                    memory_id=mem_id,
                    text=text,
                    role=mem.get("role", "user"),
                    retention=mem.get("retention", 0.0),
                    importance=mem.get("importance", 0.0),
                    metadata=mem.get("metadata", {}),
                )

                # Remove from Aether
                await jing.forget(mem_id)
                archived += 1

            if archived > 0:
                logger.info(f"[Agni] Archived {archived} memories to Tartarus")
        except Exception as e:
            logger.error(f"[Agni] Archive failed: {e}")

        return archived

    async def _reinforce_important(self, jing) -> int:
        """Boost retention for memories that are important but decaying."""
        reinforced = 0
        try:
            # Find memories: low retention but HIGH importance
            candidates = await jing.get_memories_by_retention(
                retention_below=0.3,
                importance_above=0.5,
                limit=10,
            )

            for mem in candidates:
                mem_id = mem.get("id", "")
                if mem_id:
                    await jing.reinforce(mem_id)
                    reinforced += 1

            if reinforced > 0:
                logger.info(f"[Agni] Reinforced {reinforced} important memories")
        except Exception as e:
            logger.error(f"[Agni] Reinforce failed: {e}")

        return reinforced

    async def _promote_hot(self, jing) -> int:
        """Promote recently-accessed Tartarus memories back to Aether."""
        tartarus = self._get_tartarus(jing)
        if not tartarus:
            return 0

        promoted = 0
        try:
            recently_accessed = tartarus.get_recently_accessed(days=7)

            for mem in recently_accessed:
                text = mem.get("text", "")
                if text:
                    # Re-add to Jing (Aether)
                    await jing.remember(text, role=mem.get("role", "user"), metadata={
                        "source": "agni_promotion",
                        "promoted_from": "tartarus",
                    })
                    # Remove from Tartarus
                    tartarus.remove(mem["id"])
                    promoted += 1

            if promoted > 0:
                logger.info(f"[Agni] Promoted {promoted} memories from Tartarus to Aether")
        except Exception as e:
            logger.error(f"[Agni] Promotion failed: {e}")

        return promoted

    def _get_jing(self):
        """Lazy-load Jing."""
        if self._jing is None:
            try:
                from velvet.shen.jing import Jing
                self._jing = Jing()
            except Exception:
                pass
        return self._jing

    def _get_tartarus(self, jing=None):
        """Get Tartarus from Jing or create standalone."""
        if self._tartarus is None:
            if jing and hasattr(jing, '_tartarus'):
                self._tartarus = jing._tartarus
            else:
                try:
                    from velvet.shen.tartarus import ColdStore
                    from velvet.config import get_config
                    self._tartarus = ColdStore(get_config().memory.tartarus_db_path)
                except Exception:
                    pass
        return self._tartarus
