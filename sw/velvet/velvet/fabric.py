"""
Zenoh-based communication fabric for Velvet Nadir.

Provides pub/sub messaging and RPC between nodes in the mesh.
Uses MessagePack for efficient binary serialization.

Note: The Zenoh Python API is synchronous, so we wrap it for async use.
"""

__all__ = [
    "MessageType",
    "VelvetMessage",
    "Message",
    "MessageQueue",
    "CommunicationFabric",
    "ZenohFabric",
    "MockFabric",
    "FabricError",
    "get_fabric",
    "init_fabric",
]

import asyncio
import threading
from typing import Any, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import msgpack
from loguru import logger

from velvet.errors import FabricError

# Zenoh import (will fail gracefully if not installed)
try:
    import zenoh
    ZENOH_AVAILABLE = True
except ImportError:
    ZENOH_AVAILABLE = False
    zenoh = None  # type: ignore


class MessageType(Enum):
    """Standard message types in the Velvet mesh."""
    # System
    HEARTBEAT = "sys/heartbeat"
    DEVICE_ANNOUNCE = "sys/device/announce"
    DEVICE_LEAVE = "sys/device/leave"
    
    # Audio events
    WAKE_WORD = "audio/wake"
    SPEECH_END = "audio/speech/end"
    TRANSCRIPT = "audio/transcript"
    
    # Vision events
    VISION_EVENT = "vision/event"
    
    # Actions (active)
    TTS_SPEAK = "action/tts/speak"
    TTS_DONE = "action/tts/done"
    
    # Skills (routed through queue)
    SKILL_REQUEST = "skill/request"
    SKILL_RESPONSE = "skill/response"
    
    # Gateway control
    CANCEL_REQUEST = "gateway/cancel"
    
    # Mesh: Device Registry
    MESH_DEVICE_ANNOUNCE = "mesh/device/announce"
    MESH_DEVICE_HEARTBEAT = "mesh/device/heartbeat"
    MESH_DEVICE_LEAVE = "mesh/device/leave"
    
    # Mesh: Model Registry
    MESH_MODEL_ANNOUNCE = "mesh/model/announce"
    MESH_MODEL_UNLOAD = "mesh/model/unload"
    
    # Mesh: Inference Routing
    MESH_INFERENCE_REQUEST = "mesh/inference/request"
    MESH_INFERENCE_RESPONSE = "mesh/inference/response"
    MESH_INFERENCE_STREAM = "mesh/inference/stream"
    
    # ── Future Capabilities ──────────────────────────────────────────────
    # Variants below are NOT currently wired in code.  They exist as
    # placeholders for planned features or were superseded by more specific
    # topics.  Do NOT remove — see docs/notes.md Sprint 11 analysis.
    #
    # Deprecated (mesh routing uses device-specific topics instead):
    LLM_REQUEST = "llm/request"           # → velvet/mesh/llm/request/{device_id}
    LLM_RESPONSE = "llm/response"         # → velvet/mesh/llm/response/{request_id}
    LLM_STREAM = "llm/stream"             # streaming over mesh not yet built
    #
    # Placeholder — barge-in / VAD start event:
    SPEECH_START = "audio/speech/start"    # needed for future barge-in support
    #
    # Placeholder — distributed context sync:
    CONTEXT_UPDATE = "context/update"      # ContextManager is in-process today
    LOCATION_CHANGE = "context/location"   # planned for spatial awareness (see notes.md)
    ENGAGEMENT_CHANGE = "context/engagement"  # multi-device engagement sync
    #
    # Superseded — SKILL_REQUEST handles this today:
    ACTION_REQUEST = "action/request"      # → SKILL_REQUEST
    ACTION_COMPLETE = "action/complete"    # → SKILL_RESPONSE (also unused)
    #
    # Placeholder — distributed Reflex Engine (Po handles locally):
    REFLEX_TRIGGER = "reflex/trigger"
    REFLEX_RESPONSE = "reflex/response"


@dataclass
class VelvetMessage:
    """Standard message format for Velvet mesh communication."""
    msg_type: str
    payload: dict[str, Any]
    source_device: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: str | None = None
    
    def to_bytes(self) -> bytes:
        """Serialize to MessagePack bytes, with optional HMAC signature."""
        envelope = msgpack.packb({
            "type": self.msg_type,
            "payload": self.payload,
            "source": self.source_device,
            "ts": self.timestamp.isoformat(),
            "corr_id": self.correlation_id,
        })
        # Append HMAC if mesh_secret is configured
        try:
            from velvet.config import get_config
            secret = get_config().security.mesh_secret
            if secret:
                from velvet.security import sign_message
                sig = sign_message(envelope, secret)
                return envelope + sig  # 32 bytes appended
        except Exception:
            pass  # No config yet (startup) or no secret — send unsigned
        return envelope
    
    @classmethod
    def from_bytes(cls, data: bytes) -> "VelvetMessage":
        """Deserialize from MessagePack bytes, verifying HMAC if present."""
        raw = data
        # Verify HMAC if mesh_secret is configured
        try:
            from velvet.config import get_config
            secret = get_config().security.mesh_secret
            if secret and len(data) > 32:
                from velvet.security import verify_message, HMAC_SIGNATURE_SIZE
                payload_bytes = data[:-HMAC_SIGNATURE_SIZE]
                sig = data[-HMAC_SIGNATURE_SIZE:]
                if not verify_message(payload_bytes, sig, secret):
                    raise FabricError("Invalid HMAC signature — message dropped")
                raw = payload_bytes
        except FabricError:
            raise
        except Exception:
            pass  # No config or no secret — accept unsigned
        
        unpacked = msgpack.unpackb(raw, raw=False)
        return cls(
            msg_type=unpacked["type"],
            payload=unpacked["payload"],
            source_device=unpacked["source"],
            timestamp=datetime.fromisoformat(unpacked["ts"]),
            correlation_id=unpacked.get("corr_id"),
        )


# Type alias for message handlers
MessageHandler = Callable[[VelvetMessage], Awaitable[None]]


class ZenohFabric:
    """
    Zenoh-based communication fabric.
    
    Provides:
    - Pub/sub messaging on topics
    - Request/reply RPC pattern
    - Device discovery and heartbeats
    
    The Zenoh Python API is synchronous, so we run it in a background thread
    and bridge to asyncio for the rest of the application.
    """
    
    def __init__(self, device_id: str, mode: str = "peer"):
        self.device_id = device_id
        self.mode = mode
        self.session: Any = None  # zenoh.Session
        self._subscribers: dict[str, Any] = {}
        self._handlers: dict[str, list[MessageHandler]] = {}
        self._running = False
        self._heartbeat_task: asyncio.Task | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._use_real_zenoh = False
        
    async def start(self, connect: list[str] | None = None, listen: list[str] | None = None):
        """Start the Zenoh session."""
        self._loop = asyncio.get_running_loop()
        
        if not ZENOH_AVAILABLE:
            logger.warning("Zenoh not installed, running in mock mode")
            self._running = True
            return
        
        try:
            # Configure Zenoh
            config = zenoh.Config()
            
            # Set mode
            if self.mode == "peer":
                config.insert_json5("mode", '"peer"')
            elif self.mode == "client":
                config.insert_json5("mode", '"client"')
            elif self.mode == "router":
                config.insert_json5("mode", '"router"')
            
            # Configure endpoints
            if connect:
                endpoints_json = str(connect).replace("'", '"')
                config.insert_json5("connect/endpoints", endpoints_json)
            if listen:
                endpoints_json = str(listen).replace("'", '"')
                config.insert_json5("listen/endpoints", endpoints_json)
            
            # Open session (synchronous call, run in thread pool)
            self.session = await self._loop.run_in_executor(
                None, lambda: zenoh.open(config)
            )
            
            self._running = True
            self._use_real_zenoh = True
            
            # Inject TLS config if enabled
            from velvet.config import get_config
            zcfg = get_config().zenoh
            if zcfg.tls_enabled:
                # Switch endpoints from tcp:// to tls://
                if connect:
                    connect = [e.replace("tcp/", "tls/") for e in connect]
                if listen:
                    listen = [e.replace("tcp/", "tls/") for e in listen]
                
                tls_config = {}
                if zcfg.tls_root_ca:
                    tls_config["root_ca_certificate"] = zcfg.tls_root_ca
                if zcfg.tls_server_cert:
                    tls_config["listen_certificate"] = zcfg.tls_server_cert
                    tls_config["connect_certificate"] = zcfg.tls_server_cert
                if zcfg.tls_server_key:
                    tls_config["listen_private_key"] = zcfg.tls_server_key
                    tls_config["connect_private_key"] = zcfg.tls_server_key
                if zcfg.tls_mtls_enabled:
                    tls_config["enable_mtls"] = True
                if zcfg.tls_close_on_expiry:
                    tls_config["close_link_on_expiration"] = True
                
                if tls_config:
                    import json as _json
                    config.insert_json5("transport/link/tls", _json.dumps(tls_config))
                    logger.info("TLS transport configured for Zenoh")
            
            # Announce ourselves
            await self.publish(
                MessageType.DEVICE_ANNOUNCE.value,
                {"device_id": self.device_id, "capabilities": [], "mode": self.mode}
            )
            
            logger.info(f"Zenoh fabric started in {self.mode} mode (REAL)")
            logger.info(f"Session ID: {self.session.zid()}")
            
        except Exception as e:
            logger.error(f"Failed to start Zenoh: {e}")
            logger.warning("Falling back to mock mode")
            self._running = True
            self._use_real_zenoh = False
        
    async def stop(self):
        """Stop the Zenoh session."""
        self._running = False
        
        # Undeclare all Zenoh subscribers
        for key, sub in self._subscribers.items():
            try:
                if self._use_real_zenoh and sub:
                    await self._loop.run_in_executor(None, sub.undeclare)
            except Exception as e:
                logger.debug(f"Error undeclaring subscriber {key}: {e}")
        self._subscribers.clear()
        
        # Close session
        if self.session and self._use_real_zenoh:
            try:
                await self._loop.run_in_executor(None, self.session.close)
            except Exception as e:
                logger.debug(f"Error closing session: {e}")
        self.session = None
            
        logger.info("Zenoh fabric stopped")
        
    async def publish(self, topic: str, payload: dict[str, Any], correlation_id: str | None = None):
        """Publish a message to a topic."""
        msg = VelvetMessage(
            msg_type=topic,
            payload=payload,
            source_device=self.device_id,
            correlation_id=correlation_id,
        )
        
        key = f"velvet/{topic}"
        data = msg.to_bytes()
        
        if self._use_real_zenoh and self.session:
            # Real Zenoh publish (sync API, run in executor)
            try:
                await self._loop.run_in_executor(
                    None, lambda: self.session.put(key, data)
                )
            except Exception as e:
                logger.error(f"Zenoh publish error: {e}")
        
        # Always dispatch locally (for handlers on same node)
        await self._dispatch_local(topic, msg)
            
        logger.debug(f"Published to {key}")
        
    async def subscribe(self, topic_pattern: str, handler: MessageHandler):
        """Subscribe to a topic pattern.
        
        Registers the handler locally AND declares a Zenoh subscriber
        for cross-node messaging.
        """
        # Register handler locally
        if topic_pattern not in self._handlers:
            self._handlers[topic_pattern] = []
        self._handlers[topic_pattern].append(handler)
        
        # Declare Zenoh subscriber for cross-node messaging
        key = f"velvet/{topic_pattern}"
        
        if self._use_real_zenoh and self.session and key not in self._subscribers:
            try:
                def on_sample(sample):
                    """Callback from Zenoh (runs in Zenoh thread)."""
                    try:
                        payload_bytes = bytes(sample.payload)
                        msg = VelvetMessage.from_bytes(payload_bytes)
                        
                        # Schedule async handler on the event loop
                        if self._loop:
                            asyncio.run_coroutine_threadsafe(
                                self._dispatch_local(topic_pattern, msg),
                                self._loop
                            )
                    except Exception as e:
                        logger.error(f"Error in Zenoh callback: {e}")
                
                # Declare subscriber (sync API)
                sub = await self._loop.run_in_executor(
                    None, lambda: self.session.declare_subscriber(key, on_sample)
                )
                self._subscribers[key] = sub
                logger.debug(f"Subscribed to {key} (Zenoh + local)")
                
            except Exception as e:
                logger.error(f"Failed to subscribe to {key}: {e}")
        else:
            logger.debug(f"Subscribed to {key} (local only)")

    async def unsubscribe(self, topic_pattern: str, handler: MessageHandler):
        """Remove a handler and undeclare Zenoh subscriber if no handlers remain."""
        if topic_pattern in self._handlers:
            try:
                self._handlers[topic_pattern].remove(handler)
            except ValueError:
                pass
        
        # If no handlers remain for this topic, undeclare the Zenoh subscriber
        key = f"velvet/{topic_pattern}"
        remaining = self._handlers.get(topic_pattern, [])
        
        if not remaining and key in self._subscribers:
            try:
                sub = self._subscribers.pop(key)
                if self._use_real_zenoh and sub:
                    await self._loop.run_in_executor(None, sub.undeclare)
                logger.debug(f"Unsubscribed from {key} (Zenoh undeclared)")
            except Exception as e:
                logger.error(f"Error undeclaring subscriber {key}: {e}")
            
    async def _dispatch_local(self, pattern: str, msg: VelvetMessage):
        """Dispatch message to registered handlers."""
        handlers = self._handlers.get(pattern, [])
        for handler in handlers:
            try:
                await handler(msg)
            except Exception as e:
                logger.error(f"Handler error for {pattern}: {e}")
                
    def is_real_zenoh(self) -> bool:
        """Check if using real Zenoh or mock mode."""
        return self._use_real_zenoh
        
    async def get_peers(self) -> list[str]:
        """Get list of discovered peer ZIDs."""
        if not self._use_real_zenoh or not self.session:
            return []
        try:
            # This is a simplified version - full peer discovery requires scouting
            return [str(self.session.zid())]
        except Exception:
            return []


# Singleton fabric instance
_fabric: ZenohFabric | None = None


def get_fabric() -> ZenohFabric:
    """Get the global fabric instance."""
    if _fabric is None:
        raise FabricError("Fabric not initialized. Call init_fabric() first.")
    return _fabric


async def init_fabric(device_id: str, mode: str = "peer", **kwargs) -> ZenohFabric:
    """Initialize the global fabric instance."""
    global _fabric
    _fabric = ZenohFabric(device_id, mode)
    await _fabric.start(**kwargs)
    return _fabric
