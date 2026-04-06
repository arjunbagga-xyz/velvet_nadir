"""
Mesh Memory Sync: Hive Mind Memory Replication.

Keeps memory in sync across all TRUSTED mesh nodes.
Every local write broadcasts to peers. Every peer broadcast gets replicated locally.
The mesh IS the device — one brain, physically distributed.

Respects PrivacyGuard:
  - Only syncs to TRUSTED devices
  - Untrusted devices are used (compute, sensors) but get NO data
"""

from __future__ import annotations

import asyncio
from typing import Optional

from loguru import logger


class MeshMemorySync:
    """
    Mesh-wide memory synchronization.

    Listens for memory events on Zenoh fabric and replicates across trusted peers.
    """

    def __init__(self, jing=None, privacy_guard=None):
        self._jing = jing
        self._privacy = privacy_guard
        self._fabric = None
        self._running = False

    async def start(self):
        """Start listening for memory sync events on the fabric."""
        try:
            from velvet.fabric import get_fabric
            self._fabric = get_fabric()

            await self._fabric.subscribe(
                "velvet/memory/sync",
                self._on_mesh_write
            )
            await self._fabric.subscribe(
                "velvet/memory/recall/request",
                self._on_mesh_recall_request
            )
            self._running = True
            logger.info("[MeshMemorySync] Started — listening for memory sync events")
        except Exception as e:
            logger.warning(f"[MeshMemorySync] Failed to start: {e}")

    async def stop(self):
        """Stop listening."""
        self._running = False
        logger.info("[MeshMemorySync] Stopped")

    async def on_local_write(self, text: str, role: str = "user",
                              metadata: dict | None = None):
        """
        After a local Jing.remember(), broadcast to all trusted mesh peers.

        Called by Jing after successful local write.
        """
        if not self._fabric or not self._running:
            return

        try:
            from velvet.config import get_config
            cfg = get_config()

            payload = {
                "action": "add",
                "text": text,
                "role": role,
                "metadata": metadata or {},
                "source_device": cfg.device_id,
            }

            await self._fabric.publish("velvet/memory/sync", payload)
            logger.debug(f"[MeshMemorySync] Broadcast memory to mesh: {text[:50]}...")
        except Exception as e:
            logger.error(f"[MeshMemorySync] Broadcast failed: {e}")

    async def _on_mesh_write(self, msg):
        """
        Handle memory broadcast from a peer — replicate locally.

        Respects privacy: only replicates from trusted peers.
        """
        if not self._jing:
            return

        try:
            payload = msg.payload if hasattr(msg, 'payload') else msg
            source = payload.get("source_device", "unknown")

            # Don't replicate our own broadcasts
            from velvet.config import get_config
            if source == get_config().device_id:
                return

            # Privacy check: only accept from trusted peers
            if self._privacy and not self._privacy.can_sync_memory(source):
                logger.debug(f"[MeshMemorySync] Rejected sync from untrusted {source}")
                return

            # Replicate into local Jing
            await self._jing.replicate(payload)
            logger.debug(f"[MeshMemorySync] Replicated memory from {source}")
        except Exception as e:
            logger.error(f"[MeshMemorySync] Replication failed: {e}")

    async def _on_mesh_recall_request(self, msg):
        """Handle incoming recall request from a peer."""
        if not self._jing:
            return
            
        try:
            payload = msg.payload if hasattr(msg, 'payload') else msg
            source = msg.source_device if hasattr(msg, 'source_device') else payload.get("source_device", "unknown")
            
            from velvet.config import get_config
            if source == get_config().device_id:
                return  # Default ignore own broadcast, though it's pub/sub
                
            # Privacy check
            if self._privacy and not self._privacy.can_sync_memory(source):
                logger.debug(f"[MeshMemorySync] Rejected recall request from untrusted {source}")
                return
                
            query = payload.get("query", "")
            limit = payload.get("limit", 5)
            reply_to = payload.get("reply_to")
            
            if not query or not reply_to:
                return
                
            # Perform local recall
            results = await self._jing.recall(query, k=limit)
            
            # Send results back
            response_payload = {
                "request_id": payload.get("request_id"),
                "source_device": get_config().device_id,
                "results": results
            }
            await self._fabric.publish(reply_to, response_payload)
            logger.debug(f"[MeshMemorySync] Serviced recall request from {source}")
        except Exception as e:
            logger.error(f"[MeshMemorySync] Recall request failed: {e}")

    async def mesh_recall(self, query: str, limit: int = 5) -> list[str]:
        """
        Fan-out recall request to all mesh peers.

        Returns combined results from all trusted peers.
        """
        if not self._fabric:
            return []

        try:
            import uuid
            request_id = str(uuid.uuid4())
            reply_topic = f"velvet/memory/recall/response/{request_id}"
            
            collected_results = []
            
            async def on_response(msg):
                try:
                    payload = msg.payload if hasattr(msg, 'payload') else msg
                    # Optionally check trust of responder
                    source = payload.get("source_device", "unknown")
                    if self._privacy and not self._privacy.can_sync_memory(source):
                        return
                    results = payload.get("results", [])
                    collected_results.extend(results)
                except Exception as e:
                    logger.error(f"[MeshMemorySync] Response handler error: {e}")
            
            # Subscribe to responses
            await self._fabric.subscribe(reply_topic, on_response)
            
            # Broadcast request
            from velvet.config import get_config
            payload = {
                "request_id": request_id,
                "source_device": get_config().device_id,
                "query": query,
                "limit": limit,
                "reply_to": reply_topic
            }
            await self._fabric.publish("velvet/memory/recall/request", payload)
            
            # Wait a short duration for peers to respond (e.g. 2s)
            await asyncio.sleep(2.0)
            
            # Cleanup
            await self._fabric.unsubscribe(reply_topic, on_response)
            
            # Deduplicate and sort/return (simplistic implementation)
            unique_results = []
            seen = set()
            for r in collected_results:
                if isinstance(r, dict):
                    # For dict results (memory objects), hash the text
                    text = r.get("text", "")
                    if text not in seen:
                        seen.add(text)
                        unique_results.append(r)
                else:
                    # For string results
                    if r not in seen:
                        seen.add(r)
                        unique_results.append(r)
                        
            return unique_results[:limit]
        except Exception as e:
            logger.error(f"[MeshMemorySync] Mesh recall failed: {e}")
            return []
