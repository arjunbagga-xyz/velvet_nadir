"""
Jing (精): The Essence / Memory.

Persistent long-term memory for the Shen system.
Wraps PowerMem for vector + graph storage with Ebbinghaus intelligent decay.

Memory tiers:
  Aether     — Hot: active vector index, fast embedding similarity
  Mnemosyne  — Warm: still searchable, lower priority (retention 0.1-0.3)
  Tartarus   — Cold: archived, FTS5 text search, promotable back to Aether

All tiers are mesh-wide. MeshMemorySync handles cross-device replication.
"""

from __future__ import annotations

from typing import Optional
from loguru import logger


class Jing:
    """
    Jing (精): The Essence / Memory.

    Provides persistent long-term memory via PowerMem with Aether/Mnemosyne/Tartarus tiers.
    Falls back to ephemeral (empty) memory if PowerMem is unavailable.
    """

    def __init__(self):
        self._mem = None
        self._tartarus = None
        self._ready = False
        self._ensure_loaded()

    def _ensure_loaded(self):
        """Initialize PowerMem with Polymath-built config and Tartarus cold store."""
        if self._ready:
            return

        # Tartarus (cold store) — always available, no external deps
        try:
            from velvet.shen.tartarus import ColdStore
            from velvet.config import get_config
            cfg = get_config()
            self._tartarus = ColdStore(cfg.memory.tartarus_db_path)
            logger.debug("[Jing] Tartarus cold store initialized")
        except Exception as e:
            logger.warning(f"[Jing] Tartarus init failed: {e}")
            self._tartarus = None

        # PowerMem (hot/warm tiers)
        try:
            from powermem import create_memory
            from velvet.shen.polymath import get_polymath

            poly = get_polymath()
            config = poly.build_memory_config()
            self._mem = create_memory(config=config, agent_id="velvet")
            logger.info("[Jing] PowerMem initialized via Polymath config (agent_id=velvet)")
        except ImportError:
            logger.warning("[Jing] powermem not installed. Memory will be ephemeral.")
            self._mem = None
        except Exception as e:
            logger.error(f"[Jing] PowerMem init failed: {e}")
            self._mem = None

        self._ready = True

    # =========================================================================
    # Write Path
    # =========================================================================

    async def remember(self, fact: str, role: str = "user",
                       scope: str | None = None, metadata: dict | None = None):
        """
        Crystallize new information into long-term memory (Aether tier).

        PowerMem's intelligent mode automatically extracts structured facts,
        updates graph relations, and applies Ebbinghaus retention scoring.

        Args:
            fact: Text to remember.
            role: Message role ("user", "assistant", "system").
            scope: Memory scope for agent_memory ("public", "private").
            metadata: Additional metadata dict to attach.
        """
        if not self._mem:
            return

        try:
            messages = [{"role": role, "content": fact}]
            extra_meta = metadata or {}
            if scope:
                extra_meta["scope"] = scope

            self._mem.add(messages, agent_id="velvet", metadata=extra_meta)
        except Exception as e:
            logger.error(f"[Jing] Remember failed: {e}")

    async def replicate(self, payload: dict):
        """
        Replicate a memory received from a mesh peer.

        Called by MeshMemorySync when another device broadcasts a memory.
        """
        text = payload.get("text", "")
        role = payload.get("role", "user")
        metadata = payload.get("metadata", {})
        metadata["replicated_from"] = payload.get("source_device", "unknown")

        if text:
            await self.remember(text, role=role, metadata=metadata)

    # =========================================================================
    # Read Path
    # =========================================================================

    async def recall(self, query: str, limit: int = 5,
                     deep: bool = False) -> list[str]:
        """
        Retrieve relevant context from memory.

        Searches Aether (embedding similarity) first. If deep=True or results
        are insufficient, also searches Tartarus (FTS5 text + keyword expansion).

        Args:
            query: Search query.
            limit: Max results to return.
            deep: If True, also search Tartarus cold archive.

        Returns:
            List of memory strings.
        """
        results = await self.local_search(query, limit=limit)

        # Deep search: Tartarus FTS5
        if (deep or len(results) < limit) and self._tartarus:
            try:
                remaining = limit - len(results)
                keywords = await self._expand_query(query)
                cold_results = self._tartarus.search(keywords, limit=remaining)
                for cr in cold_results:
                    self._tartarus.mark_accessed(cr["id"])
                    results.append(cr["text"])
            except Exception as e:
                logger.error(f"[Jing] Tartarus search failed: {e}")

        return results

    async def local_search(self, query: str, limit: int = 5) -> list[str]:
        """Search only the local Aether (hot) store — no mesh, no Tartarus."""
        if not self._mem:
            return []

        try:
            results = self._mem.search(query, limit=limit)
            memories = [r["memory"] for r in results.get("results", [])]
            return memories
        except Exception as e:
            logger.error(f"[Jing] Local search failed: {e}")
            return []

    async def graph_query(self, query: str) -> list[str]:
        """
        Query the knowledge graph for entity/relation information.

        Uses PowerMem's built-in graph store (SQLite + LLM entity extraction).
        """
        if not self._mem:
            return []

        try:
            results = self._mem.search(query, limit=5)
            relations = results.get("relations", [])
            return [str(r) for r in relations]
        except Exception as e:
            logger.error(f"[Jing] Graph query failed: {e}")
            return []

    # =========================================================================
    # Memory Management (used by Agni)
    # =========================================================================

    async def get_memories_by_retention(
        self, retention_below: float | None = None,
        importance_above: float | None = None,
        importance_below: float | None = None,
        limit: int = 50
    ) -> list[dict]:
        """
        Get memories filtered by retention/importance scores.

        Used by Agni (purification) for tiered management.
        Returns raw memory dicts with id, text, retention, importance.
        """
        if not self._mem:
            return []

        try:
            # Get all memories and filter by retention/importance
            all_memories = self._mem.get_all(agent_id="velvet", limit=limit)
            filtered = []
            for m in all_memories:
                retention = m.get("retention", 1.0)
                importance = m.get("importance", 0.5)

                if retention_below is not None and retention >= retention_below:
                    continue
                if importance_above is not None and importance <= importance_above:
                    continue
                if importance_below is not None and importance >= importance_below:
                    continue
                filtered.append(m)

            return filtered
        except Exception as e:
            logger.error(f"[Jing] get_memories_by_retention failed: {e}")
            return []

    async def reinforce(self, memory_id: str):
        """Reinforce a memory (boost Ebbinghaus retention)."""
        if not self._mem:
            return
        try:
            self._mem.reinforce(memory_id)
        except Exception as e:
            logger.error(f"[Jing] Reinforce failed: {e}")

    async def forget(self, memory_id: str):
        """Remove a memory from the active store."""
        if not self._mem:
            return
        try:
            self._mem.delete(memory_id)
        except Exception as e:
            logger.error(f"[Jing] Forget failed: {e}")

    async def compact(self):
        """Compact storage (SQLite VACUUM)."""
        if not self._mem:
            return
        try:
            # PowerMem may or may not expose a compact method
            if hasattr(self._mem, "compact"):
                self._mem.compact()
        except Exception as e:
            logger.error(f"[Jing] Compact failed: {e}")

    # =========================================================================
    # Helpers
    # =========================================================================

    async def _expand_query(self, query: str) -> list[str]:
        """
        Generate keyword synonyms for Tartarus FTS5 search.

        Light LLM task — can run on any mesh node.
        Falls back to raw query words if LLM is unavailable.
        """
        try:
            from velvet.llm import get_llm_adapter
            adapter = get_llm_adapter()
            prompt = (
                f'Generate 5 keyword synonyms or related terms for searching: "{query}". '
                f'Output as a comma-separated list, nothing else.'
            )
            response = await adapter.generate(prompt, max_tokens=50)
            keywords = [kw.strip() for kw in response.split(",") if kw.strip()]
            keywords.append(query)  # Always include the original
            return keywords
        except Exception:
            # Fallback: just use the raw query words
            return query.split()

    @property
    def is_persistent(self) -> bool:
        """True if PowerMem is available (not ephemeral mode)."""
        return self._mem is not None

    @property
    def has_tartarus(self) -> bool:
        """True if cold store is available."""
        return self._tartarus is not None
