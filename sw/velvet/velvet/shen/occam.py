"""
Occam's Razor: Background Causal Log Conflict Resolver.

Uses parsimony-driven LLM evaluation to reconcile divergent offline memories
and transaction logs across devices, updating states or logging unresolved states.
"""

from __future__ import annotations

import json
from loguru import logger

from velvet.shen.xi import BreathTask, ComputeBudget, ConversationTurn
from velvet.llm import get_llm_adapter


class OccamsRazorTask(BreathTask):
    """
    OccamsRazorTask (background conflict resolver).
    
    Reconciles divergent causal log (Sutra) records structurally or via LLM.
    """

    def __init__(self, jing=None):
        self.jing = jing

    def name(self) -> str:
        return "OccamsRazorTask"

    def budget(self) -> ComputeBudget:
        # Occam's Razor requires LLM queries, so priority is lower, priority 8.
        return ComputeBudget(
            cpu_seconds=5.0,
            gpu_needed=True,
            ram_mb=128,
            network_io=True,
            priority=8
        )

    async def run(self, batch: list[ConversationTurn]) -> None:
        """Fetch unresolved database conflicts and attempt LLM-mediated reconciliation."""
        if not self.jing:
            return

        conflicts = self.jing.get_unresolved_conflicts()
        if not conflicts:
            return

        logger.info(f"[OccamsRazor] Found {len(conflicts)} unresolved database conflicts to reconcile")

        # Group conflicts by transaction ID
        # (Since each node has its own causal log, conflicts occur when we have duplicate transaction IDs
        # with different hashes or when the transaction payloads are logically contradictory).
        conflict_groups: dict[str, list[dict]] = {}
        for c in conflicts:
            conflict_groups.setdefault(c["id"], []).append(c)

        for sutra_id, items in conflict_groups.items():
            if len(items) < 2:
                # If only one item exists under this ID but it is marked unresolved, we check if we can resolve it directly
                # Or wait for another node's concurrent version to arrive.
                continue

            # Let's arbitrate the first two divergent versions
            item_a = items[0]
            item_b = items[1]
            
            logger.info(f"[OccamsRazor] Reconciling divergent versions for transaction {sutra_id}...")
            
            try:
                resolved_payload = await self._arbitrate_conflict(sutra_id, item_a, item_b)
                if resolved_payload:
                    # Update local database state
                    self.jing.resolve_conflict(sutra_id, resolved_payload)
                    
                    # Store the resolved memory fact in active layers
                    await self.jing.remember(
                        resolved_payload["fact"],
                        role=resolved_payload.get("role", "user"),
                        metadata=resolved_payload.get("metadata", {}),
                        skip_sutra_log=True
                    )
                    
                    # Broadcast instant conflict-resolution over Zenoh mesh
                    try:
                        from velvet.fabric import get_fabric
                        fabric = get_fabric()
                        await fabric.publish(
                            "velvet/reconnection/resolved",
                            {
                                "sutra_id": sutra_id,
                                "payload": resolved_payload
                            }
                        )
                        logger.info(f"[OccamsRazor] Broadcasted conflict resolution for {sutra_id}")
                    except Exception as e:
                        logger.debug(f"[OccamsRazor] Zenoh broadcast skipped or unavailable: {e}")

                    logger.info(f"[OccamsRazor] Successfully resolved conflict for transaction {sutra_id}")
                else:
                    logger.warning(f"[OccamsRazor] Conflict {sutra_id} remains unresolved (ambiguous divergence)")
            except Exception as e:
                logger.error(f"[OccamsRazor] Failed to run arbitration for {sutra_id}: {e}")

    async def _arbitrate_conflict(self, sutra_id: str, a: dict, b: dict) -> dict | None:
        """Invoke the LLM to arbitrate and resolve a memory conflict."""
        adapter = get_llm_adapter()
        
        prompt = (
            "You are Occam's Razor, the parsimony-driven conflict resolver for a distributed AI memory mesh.\n"
            f"We have a divergent causal log conflict under transaction ID '{sutra_id}'.\n\n"
            f"Record A (device: {a.get('device_id')}):\n"
            f"Payload: {json.dumps(a['payload'])}\n"
            f"Timestamp: {a.get('timestamp')}\n\n"
            f"Record B (device: {b.get('device_id')}):\n"
            f"Payload: {json.dumps(b['payload'])}\n"
            f"Timestamp: {b.get('timestamp')}\n\n"
            "Analyze these two entries. Reconcile them according to these principles:\n"
            "1. If they are semantically identical or complementary details that don't contradict, merge them.\n"
            "2. If there is a direct contradiction, choose the more recent or detailed entry, or combine them logically.\n"
            "3. If they are completely irreconcilable or highly ambiguous, do NOT resolve (resolved=false).\n\n"
            "Output your decision strictly as a JSON object with this schema:\n"
            "{\n"
            '  "resolved": true,\n'
            '  "decision": "merged",\n'
            '  "fact": "Reconciled fact string here",\n'
            '  "role": "user",\n'
            '  "metadata": {},\n'
            '  "rationale": "Brief rationale for this decision"\n'
            "}\n"
            "Output ONLY the JSON object, with no markdown code blocks, explanations, or extra characters."
        )

        try:
            # We construct a system message and a user message
            messages = [
                {"role": "system", "content": "You are a parsimony-driven conflict resolution engine. Output ONLY valid JSON."},
                {"role": "user", "content": prompt}
            ]
            response = await adapter.generate(messages, max_tokens=512)
            
            # Clean response text
            text = response.text.strip()
            if text.startswith("```"):
                # strip code block tags if the model ignored instructions
                lines = text.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].startswith("```"):
                    lines = lines[:-1]
                text = "\n".join(lines).strip()

            result = json.loads(text)
            if result.get("resolved") is True:
                # Reconstruct final payload
                return {
                    "fact": result.get("fact"),
                    "role": result.get("role", "user"),
                    "metadata": result.get("metadata", {})
                }
            return None
        except Exception as e:
            logger.error(f"[OccamsRazor] LLM conflict resolution failed: {e}")
            return None
