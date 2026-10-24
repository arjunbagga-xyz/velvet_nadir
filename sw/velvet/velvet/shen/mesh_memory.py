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
import json
import hmac
import hashlib
from typing import Optional
from loguru import logger
from velvet.security import verify_message, sign_message


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
            await self._fabric.subscribe(
                "velvet/anamnesis/handshake",
                self._on_handshake_received
            )
            await self._fabric.subscribe(
                "velvet/anamnesis/sync/request",
                self._on_sync_request_received
            )
            await self._fabric.subscribe(
                "velvet/anamnesis/sync/response",
                self._on_sync_response_received
            )
            await self._fabric.subscribe(
                "velvet/reconnection/resolved",
                self._on_conflict_resolved_received
            )
            self._running = True
            logger.info("[MeshMemorySync] Started — listening for memory sync events")
        except Exception as e:
            logger.warning(f"[MeshMemorySync] Failed to start: {e}")

    async def stop(self):
        """Stop listening."""
        self._running = False
        if self._fabric:
            try:
                await self._fabric.unsubscribe("velvet/memory/sync", self._on_mesh_write)
                await self._fabric.unsubscribe("velvet/memory/recall/request", self._on_mesh_recall_request)
                await self._fabric.unsubscribe("velvet/anamnesis/handshake", self._on_handshake_received)
                await self._fabric.unsubscribe("velvet/anamnesis/sync/request", self._on_sync_request_received)
                await self._fabric.unsubscribe("velvet/anamnesis/sync/response", self._on_sync_response_received)
                await self._fabric.unsubscribe("velvet/reconnection/resolved", self._on_conflict_resolved_received)
            except Exception as e:
                logger.error(f"[MeshMemorySync] Error unsubscribing: {e}")
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
            from velvet.privacy import PrivacyClassifier, PrivacyLevel
            classifier = PrivacyClassifier()
            level = classifier.classify(text)
            
            if level == PrivacyLevel.RESTRICTED:
                logger.info("[MeshMemorySync] Bypassing mesh broadcast for RESTRICTED memory (stay on device forever)")
                return
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

    # =========================================================================
    # Anamnesis Reconnection Sync Protocol
    # =========================================================================

    def _sign_payload(self, payload: dict, secret: str) -> str:
        """Sign a payload dict with HMAC-SHA256."""
        if not secret:
            logger.warning("[MeshMemorySync] Empty mesh_secret provided for payload signing.")
            return ""
        serialized = json.dumps(payload, sort_keys=True)
        return sign_message(serialized.encode("utf-8"), secret).hex()

    def _verify_payload(self, payload: dict, signature_hex: str, secret: str) -> bool:
        """Verify the HMAC signature of a serialized payload dict."""
        if not secret or not signature_hex:
            logger.warning("[MeshMemorySync] Empty secret or signature for payload verification (failing closed)")
            return False
        try:
            serialized = json.dumps(payload, sort_keys=True)
            sig_bytes = bytes.fromhex(signature_hex)
            return verify_message(serialized.encode("utf-8"), sig_bytes, secret)
        except Exception:
            return False

    async def initiate_handshake(self, peer_device_id: str):
        """Initiate cryptographic Anamnesis handshake (exchange Tín Phù)."""
        if not self._fabric or not self._running:
            return

        try:
            from velvet.config import get_config
            cfg = get_config()
            
            tin_phu = {
                "version_vector": self._jing.get_version_vector(),
                "merkle_root": self._jing.get_merkle_root(),
            }
            
            payload = {
                "source_device": cfg.device_id,
                "target_device": peer_device_id,
                "tin_phu": tin_phu,
            }
            
            sig = self._sign_payload(payload, cfg.security.mesh_secret)
            envelope = {
                **payload,
                "signature": sig
            }
            
            await self._fabric.publish("velvet/anamnesis/handshake", envelope)
            logger.info(f"[Anamnesis] Sent Tín Phù handshake to peer {peer_device_id}")
        except Exception as e:
            logger.error(f"[Anamnesis] Handshake initiation failed: {e}")

    async def _on_handshake_received(self, msg):
        """Handle incoming handshake. Validates signatures and determines delta."""
        if not self._jing or not self._fabric:
            return

        try:
            from velvet.config import get_config
            cfg = get_config()
            
            envelope = msg.payload if hasattr(msg, 'payload') else msg
            target = envelope.get("target_device")
            
            # 1. Target check
            if target != cfg.device_id:
                return

            source = envelope.get("source_device")
            sig = envelope.get("signature")
            tin_phu = envelope.get("tin_phu", {})
            
            # Reconstruct payload dict to verify signature
            payload = {
                "source_device": source,
                "target_device": target,
                "tin_phu": tin_phu,
            }
            
            # 2. Cryptographic check
            if not self._verify_payload(payload, sig, cfg.security.mesh_secret):
                logger.warning(f"[Anamnesis] Rejected handshake from {source}: Invalid signature")
                return

            logger.info(f"[Anamnesis] Validated handshake from {source}")

            # 3. Privacy check
            if self._privacy and not self._privacy.can_sync_memory(source):
                logger.debug(f"[Anamnesis] Rejected sync from untrusted {source}")
                return

            peer_vector = tin_phu.get("version_vector", {})
            my_vector = self._jing.get_version_vector()

            # Compare vectors to determine sync direction
            # A. If peer is lagging: send missing sutras
            missing_sutras = self._jing.get_sutras_since(peer_vector)
            if missing_sutras:
                response = {
                    "source_device": cfg.device_id,
                    "target_device": source,
                    "sutras": missing_sutras,
                }
                sig_res = self._sign_payload(response, cfg.security.mesh_secret)
                envelope_res = {**response, "signature": sig_res}
                await self._fabric.publish("velvet/anamnesis/sync/response", envelope_res)
                logger.info(f"[Anamnesis] Sent causal log delta ({len(missing_sutras)} sutras) to peer {source}")

            # B. If we are lagging: request missing sutras
            my_lagging = False
            for peer_dev, peer_ver in peer_vector.items():
                if my_vector.get(peer_dev, 0) < peer_ver:
                    my_lagging = True
                    break
            
            if my_lagging:
                request = {
                    "source_device": cfg.device_id,
                    "target_device": source,
                    "version_vector": my_vector,
                }
                sig_req = self._sign_payload(request, cfg.security.mesh_secret)
                envelope_req = {**request, "signature": sig_req}
                await self._fabric.publish("velvet/anamnesis/sync/request", envelope_req)
                logger.info(f"[Anamnesis] Requested causal log delta from peer {source}")
        except Exception as e:
            logger.error(f"[Anamnesis] Handshake handling failed: {e}")

    async def _on_sync_request_received(self, msg):
        """Handle incoming sync delta request from a lagging peer."""
        if not self._jing or not self._fabric:
            return

        try:
            from velvet.config import get_config
            cfg = get_config()
            
            envelope = msg.payload if hasattr(msg, 'payload') else msg
            target = envelope.get("target_device")
            
            if target != cfg.device_id:
                return

            source = envelope.get("source_device")
            sig = envelope.get("signature")
            peer_vector = envelope.get("version_vector", {})
            
            payload = {
                "source_device": source,
                "target_device": target,
                "version_vector": peer_vector,
            }
            
            if not self._verify_payload(payload, sig, cfg.security.mesh_secret):
                logger.warning(f"[Anamnesis] Rejected sync request from {source}: Invalid signature")
                return

            # Privacy check
            if self._privacy and not self._privacy.can_sync_memory(source):
                return

            missing_sutras = self._jing.get_sutras_since(peer_vector)
            if missing_sutras:
                response = {
                    "source_device": cfg.device_id,
                    "target_device": source,
                    "sutras": missing_sutras,
                }
                sig_res = self._sign_payload(response, cfg.security.mesh_secret)
                envelope_res = {**response, "signature": sig_res}
                await self._fabric.publish("velvet/anamnesis/sync/response", envelope_res)
                logger.info(f"[Anamnesis] Serviced sync request from {source}: Sent {len(missing_sutras)} sutras")
        except Exception as e:
            logger.error(f"[Anamnesis] Sync request handling failed: {e}")

    async def _on_sync_response_received(self, msg):
        """Handle sync response delta (Syzygy structural merge)."""
        if not self._jing:
            return

        try:
            from velvet.config import get_config
            cfg = get_config()
            
            envelope = msg.payload if hasattr(msg, 'payload') else msg
            target = envelope.get("target_device")
            
            if target != cfg.device_id:
                return

            source = envelope.get("source_device")
            sig = envelope.get("signature")
            sutras = envelope.get("sutras", [])
            
            payload = {
                "source_device": source,
                "target_device": target,
                "sutras": sutras,
            }
            
            if not self._verify_payload(payload, sig, cfg.security.mesh_secret):
                logger.warning(f"[Anamnesis] Rejected sync response from {source}: Invalid signature")
                return

            # Privacy check
            if self._privacy and not self._privacy.can_sync_memory(source):
                return

            logger.info(f"[Anamnesis] Merging delta of {len(sutras)} sutras from {source}")

            # Replicate each transaction structurally (Syzygy)
            replicated_count = 0
            for s in sutras:
                success = self._jing.replicate_sutra(s)
                if success:
                    replicated_count += 1
                    # If this is a fact insertion, write to local memory tiers
                    if s["action"] == "add":
                        p = s["payload"]
                        # Remember local without re-logging to causal log
                        await self._jing.remember(p["fact"], role=p.get("role", "user"), metadata=p.get("metadata"), skip_sutra_log=True)
            
            logger.info(f"[Anamnesis] Reconnection sync merge complete (integrated {replicated_count}/{len(sutras)} new sutras)")
        except Exception as e:
            logger.error(f"[Anamnesis] Sync response handling failed: {e}")

    async def _on_conflict_resolved_received(self, msg):
        """Handle real-time conflict resolution announcements from peers."""
        if not self._jing:
            return
        try:
            envelope = msg.payload if hasattr(msg, 'payload') else msg
            sutra_id = envelope.get("sutra_id")
            resolved_payload = envelope.get("payload")
            source = envelope.get("source_device", "")
            sig = envelope.get("signature", "")

            from velvet.config import get_config
            cfg = get_config()
            check_data = {"sutra_id": sutra_id, "payload": resolved_payload, "source_device": source}
            if sig and not self._verify_payload(check_data, sig, cfg.security.mesh_secret):
                logger.warning(f"[Anamnesis] Rejected conflict resolution message from {source}: Invalid signature")
                return

            if sutra_id and resolved_payload:
                self._jing.resolve_conflict(sutra_id, resolved_payload)
                logger.info(f"[Anamnesis] Merged real-time conflict resolution for {sutra_id}")
        except Exception as e:
            logger.error(f"[Anamnesis] Handling of conflict resolved message failed: {e}")
