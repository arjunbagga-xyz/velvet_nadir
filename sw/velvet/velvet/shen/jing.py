"""
Jing (精): The Essence / Memory.

Persistent long-term memory for the Shen system.
Wraps PowerMem for vector storage with Ebbinghaus intelligent decay,
MemPalace KnowledgeGraph for temporal entity-relationship graph,
and Tartarus for cold FTS5 archive.

Memory tiers:
  Aether     — Hot: active vector index, fast embedding similarity
  Mnemosyne  — Warm: still searchable, lower priority (retention 0.1-0.3)
  Tartarus   — Cold: archived, FTS5 text search, promotable back to Aether

Knowledge Graph (MemPalace):
  Temporal entity-relationship triples backed by local SQLite.
  Supports add_triple(), query_entity(), timeline(), invalidate().

All tiers are mesh-wide. MeshMemorySync handles cross-device replication.
"""

from __future__ import annotations

from typing import Optional
from loguru import logger


class Jing:
    """
    Jing (精): The Essence / Memory.

    Provides persistent long-term memory via:
    - PowerMem: vector embeddings with Ebbinghaus decay (Aether/Mnemosyne)
    - MemPalace KnowledgeGraph: temporal entity-relationship graph (SQLite)
    - Tartarus: cold FTS5 archive

    Falls back to ephemeral (empty) memory if dependencies are unavailable.
    """

    def __init__(self):
        self._mem = None
        self._tartarus = None
        self._kg = None  # MemPalace KnowledgeGraph
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

        # MemPalace KnowledgeGraph (temporal entity-relationship graph)
        try:
            from mempalace.knowledge_graph import KnowledgeGraph
            from velvet.config import get_config
            cfg = get_config()
            db_path = cfg.memory.graph_db_path
            self._kg = KnowledgeGraph(db_path=db_path)
            logger.info(f"[Jing] MemPalace KnowledgeGraph initialized at {db_path}")
        except ImportError:
            logger.warning("[Jing] mempalace not installed. Knowledge graph unavailable.")
            self._kg = None
        except Exception as e:
            logger.error(f"[Jing] MemPalace KG init failed: {e}")
            self._kg = None

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

    async def remember_person(self, name: str, face_emb: list[float] | None = None, voice_emb: list[float] | None = None):
        """
        Store a person identity with biometrics in Jing.
        """
        metadata = {"type": "person", "name": name}
        if face_emb:
            metadata["face_embedding"] = face_emb
        if voice_emb:
            metadata["voice_embedding"] = voice_emb
            
        text = f"Known person identity: {name}"
        await self.remember(text, role="system", metadata=metadata)
        
        # Local mock implementation for testing if PowerMem is off
        if not hasattr(self, '_mock_people'):
            self._mock_people = []
        self._mock_people.append(metadata)

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

    async def recall_by_embedding(self, embedding: list[float], type_tag: str = "person", modality: str = "face") -> dict | None:
        """
        Recall known memories (identities) by vector similarity on the embedding.
        """
        # If we have a _mem structure that supports it
        if self._mem and hasattr(self._mem, 'search_by_vector'):
            try:
                results = self._mem.search_by_vector(embedding, limit=1, filter={"type": type_tag})
                if results and results.get("results"):
                    best = results["results"][0]
                    return {
                        "name": best["metadata"].get("name", "unknown"),
                        "confidence": best.get("score", 0.0)
                    }
            except Exception as e:
                logger.error(f"[Jing] recall_by_embedding powermem failed: {e}")
                
        # Mock / Fallback logic for testing
        if hasattr(self, '_mock_people'):
            best_person = None
            best_score = -1.0
            
            import numpy as np
            emb_vec = np.array(embedding)
            
            for p in self._mock_people:
                target_emb = p.get(f"{modality}_embedding")
                if target_emb:
                    t_vec = np.array(target_emb)
                    # cosine similarity = A.dot(B) / (|A|*|B|)
                    norm_emb = np.linalg.norm(emb_vec)
                    norm_t = np.linalg.norm(t_vec)
                    if norm_emb and norm_t:
                        sim = np.dot(emb_vec, t_vec) / (norm_emb * norm_t)
                        if sim > best_score:
                            best_score = float(sim)
                            best_person = p["name"]
                        
            if best_person is not None:
                return {"name": best_person, "confidence": best_score}
                
        return None

    async def graph_query(self, query: str) -> list[str]:
        """
        Query the knowledge graph for entity/relation information.

        Uses MemPalace's temporal KnowledgeGraph (SQLite-backed).
        """
        if not self._kg:
            return []

        try:
            results = self._kg.query_entity(query)
            return [str(r) for r in results]
        except Exception as e:
            logger.error(f"[Jing] Graph query failed: {e}")
            return []

    async def graph_add_entity(self, name: str, entity_type: str = "concept"):
        """Register an entity in the knowledge graph."""
        if not self._kg:
            return
        try:
            self._kg.add_entity(name, entity_type=entity_type)
            logger.debug(f"[Jing] KG entity added: {name} ({entity_type})")
        except Exception as e:
            logger.error(f"[Jing] KG add_entity failed: {e}")

    async def graph_add_relation(self, subject: str, predicate: str, obj: str,
                                  valid_from: str | None = None):
        """Add a relationship triple to the knowledge graph."""
        if not self._kg:
            return
        try:
            kwargs = {}
            if valid_from:
                kwargs["valid_from"] = valid_from
            self._kg.add_triple(subject, predicate, obj, **kwargs)
            logger.debug(f"[Jing] KG triple added: {subject} → {predicate} → {obj}")
        except Exception as e:
            logger.error(f"[Jing] KG add_triple failed: {e}")

    async def graph_invalidate(self, subject: str, predicate: str, obj: str,
                                ended: str | None = None):
        """Invalidate a fact in the knowledge graph (it stopped being true)."""
        if not self._kg:
            return
        try:
            kwargs = {}
            if ended:
                kwargs["ended"] = ended
            self._kg.invalidate(subject, predicate, obj, **kwargs)
            logger.debug(f"[Jing] KG fact invalidated: {subject} → {predicate} → {obj}")
        except Exception as e:
            logger.error(f"[Jing] KG invalidate failed: {e}")

    async def graph_timeline(self, entity: str) -> list:
        """Get the chronological story of an entity."""
        if not self._kg:
            return []
        try:
            return self._kg.timeline(entity)
        except Exception as e:
            logger.error(f"[Jing] KG timeline failed: {e}")
            return []

    def get_graph_snapshot(self) -> dict:
        """
        Return full graph state for UI visualization.

        Returns {nodes: [...], links: [...]} for the D3 force-directed graph.
        """
        if not self._kg:
            return {"nodes": [], "links": []}

        try:
            stats = self._kg.stats()
            nodes = []
            links = []

            # Build nodes from entity types reported by stats
            # Query all entities by fetching relationships for known types
            seen_entities = set()

            # Get all relationship types and query each
            for rel_type in stats.get("relationship_types", []):
                try:
                    rels = self._kg.query_relationship(rel_type)
                    for r in rels:
                        subj = str(r.get("subject", r) if isinstance(r, dict) else r)
                        obj_val = str(r.get("object", "") if isinstance(r, dict) else "")
                        pred = str(r.get("predicate", rel_type) if isinstance(r, dict) else rel_type)

                        if subj and subj not in seen_entities:
                            seen_entities.add(subj)
                            nodes.append({
                                "id": subj,
                                "type": r.get("subject_type", "concept") if isinstance(r, dict) else "concept",
                                "tier": 1
                            })
                        if obj_val and obj_val not in seen_entities:
                            seen_entities.add(obj_val)
                            nodes.append({
                                "id": obj_val,
                                "type": r.get("object_type", "concept") if isinstance(r, dict) else "concept",
                                "tier": 2
                            })
                        if subj and obj_val:
                            links.append({
                                "source": subj,
                                "target": obj_val,
                                "label": pred,
                                "value": 1
                            })
                except Exception:
                    continue

            return {"nodes": nodes, "links": links}
        except Exception as e:
            logger.error(f"[Jing] get_graph_snapshot failed: {e}")
            return {"nodes": [], "links": []}

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
            keywords = [kw.strip() for kw in response.text.split(",") if kw.strip()]
            keywords.append(query)  # Always include the original
            return keywords
        except Exception:
            # Fallback: just use the raw query words
            return query.split()

    @property
    def is_persistent(self) -> bool:
        """True if at least one persistent store is available."""
        return self._mem is not None or self._kg is not None

    @property
    def has_knowledge_graph(self) -> bool:
        """True if MemPalace KnowledgeGraph is available."""
        return self._kg is not None

    @property
    def has_tartarus(self) -> bool:
        """True if cold store is available."""
        return self._tartarus is not None
