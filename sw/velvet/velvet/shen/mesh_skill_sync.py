"""
MeshSkillSync: Distributed Skill Synchronization via Zenoh Fabric.

Broadcasts skill announcements across the mesh when skills are registered or upgraded,
and supports remote skill discovery and peer proxying.
"""

import hashlib
import json
from typing import Any, Optional
from loguru import logger

from velvet.fabric import get_fabric, VelvetMessage, MessageType
from velvet.skills.base import get_skill_registry, SkillRegistry, Skill


class MeshSkillSync:
    """
    Manages skill discovery, announcement, and synchronization across the mesh.
    """

    TOPIC_ANNOUNCE = "velvet/mesh/skills/announce"
    TOPIC_DISCOVER = "velvet/mesh/skills/discover"
    TOPIC_RESPONSE = "velvet/mesh/skills/response"

    def __init__(self, registry: SkillRegistry | None = None, device_id: str = "local"):
        self.registry = registry or get_skill_registry()
        self.device_id = device_id
        self.fabric = get_fabric()
        self._subscribed = False

    async def start(self) -> None:
        """Subscribe to mesh skill topics."""
        if not self._subscribed:
            await self.fabric.subscribe(self.TOPIC_ANNOUNCE, self._on_skill_announced)
            await self.fabric.subscribe(f"{self.TOPIC_DISCOVER}/*", self._on_skill_query)
            self._subscribed = True
            logger.info("[MeshSkillSync] Subscribed to skill discovery & announce topics")

    async def stop(self) -> None:
        """Unsubscribe from mesh skill topics."""
        if self._subscribed:
            await self.fabric.unsubscribe(self.TOPIC_ANNOUNCE, self._on_skill_announced)
            self._subscribed = False

    async def announce_skill(self, skill: Skill) -> None:
        """Broadcast a local skill announcement to all mesh nodes."""
        defn = skill.definition
        payload = {
            "source_device": self.device_id,
            "skill_name": defn.name,
            "category": defn.category.value,
            "description": defn.description,
            "tags": defn.tags,
            "tool_schema": defn.to_tool_schema(),
            "sha256": hashlib.sha256(f"{defn.name}-{defn.description}".encode()).hexdigest(),
        }
        await self.fabric.publish(self.TOPIC_ANNOUNCE, payload)
        logger.info(f"[MeshSkillSync] Announced skill '{defn.name}' to mesh.")

    async def discover_skill(self, skill_name: str, timeout: float = 3.0) -> dict[str, Any] | None:
        """
        Query the mesh for a skill that is not available locally.
        Returns peer response or None on timeout.
        """
        import asyncio
        future: asyncio.Future[dict[str, Any]] = asyncio.Future()
        response_topic = f"{self.TOPIC_RESPONSE}/{skill_name}/{self.device_id}"

        async def _on_response(msg: VelvetMessage):
            if not future.done():
                future.set_result(msg.payload)

        await self.fabric.subscribe(response_topic, _on_response)
        try:
            query_topic = f"{self.TOPIC_DISCOVER}/{skill_name}"
            await self.fabric.publish(query_topic, {
                "skill_name": skill_name,
                "requesting_device": self.device_id,
                "reply_to": response_topic,
            })
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            logger.debug(f"[MeshSkillSync] Discovery timed out for skill '{skill_name}'")
            return None
        finally:
            await self.fabric.unsubscribe(response_topic, _on_response)

    async def _on_skill_announced(self, msg: VelvetMessage) -> None:
        """Handle incoming skill announcement from a remote node."""
        data = msg.payload
        if data.get("source_device") == self.device_id:
            return  # Ignore self announcement

        skill_name = data.get("skill_name")
        logger.info(
            f"[MeshSkillSync] Remote peer '{data.get('source_device')}' announced skill: {skill_name}"
        )

    async def _on_skill_query(self, msg: VelvetMessage) -> None:
        """Respond to remote skill discovery requests if skill exists locally."""
        data = msg.payload
        skill_name = data.get("skill_name")
        reply_to = data.get("reply_to")

        if not skill_name or not reply_to:
            return

        skill = self.registry.get(skill_name)
        if skill:
            defn = skill.definition
            resp_payload = {
                "source_device": self.device_id,
                "skill_name": defn.name,
                "category": defn.category.value,
                "description": defn.description,
                "tool_schema": defn.to_tool_schema(),
            }
            await self.fabric.publish(reply_to, resp_payload)
            logger.debug(f"[MeshSkillSync] Replied with definition for skill '{skill_name}' to {reply_to}")
