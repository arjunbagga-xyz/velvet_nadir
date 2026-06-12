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
    SKILL_PENDING_APPROVAL = "skill/pending_approval"
    
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
    
    # Display Bridge
    DISPLAY_CHAT_IN = "display/chat/in"
    DISPLAY_CHAT_OUT = "display/chat/out"

    # Basilisk Protocol (Secure P2P RPC)
    BASILISK_RPC = "sys/basilisk/rpc"
    BASILISK_AUTH = "sys/basilisk/auth"

    # Vision person events
    PERSON_DETECTED = "vision/person/detected"
    PERSON_IDENTIFIED = "vision/person/identified"

    # Context / Spatial
    LOCATION_UPDATE = "context/location/update"
    SPATIAL_FENCE_EVENT = "context/spatial/fence"

    # Security
    TRUST_CHANGE_REQUEST = "security/trust/request"
    TRUST_CHANGE_VERIFIED = "security/trust/verified"
    
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


def match_pattern(pattern: str, topic: str) -> bool:
    """Check if a topic matches a Zenoh-style pattern (supporting * and **)."""
    import re
    # Convert Zenoh pattern to python regex
    # '**' matches any subpath (including '/')
    # '*' matches a single path component (excluding '/')
    regex_parts = []
    i = 0
    while i < len(pattern):
        if pattern[i:i+2] == '**':
            regex_parts.append('.*')
            i += 2
        elif pattern[i] == '*':
            regex_parts.append('[^/]*')
            i += 1
        elif pattern[i] in '.+^$()[]{}|\\':
            regex_parts.append('\\' + pattern[i])
            i += 1
        else:
            regex_parts.append(pattern[i])
            i += 1
    regex_str = '^' + ''.join(regex_parts) + '$'
    try:
        return bool(re.match(regex_str, topic))
    except Exception:
        return False


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
        self._queryables: dict[str, Any] = {}
        self._local_queryables: dict[str, Any] = {}
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
                        
                        # Avoid duplicate delivery of locally published messages
                        if msg.source_device == self.device_id:
                            return
                            
                        # Schedule async handler on the event loop
                        if self._loop:
                            asyncio.run_coroutine_threadsafe(
                                self._dispatch_local(msg.msg_type, msg),
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
            
    async def _dispatch_local(self, topic: str, msg: VelvetMessage):
        """Dispatch message to registered handlers matching the topic."""
        logger.info(f"[DispatchLocal] Dispatching topic: {topic} (Payload: {msg.payload}) to patterns: {list(self._handlers.keys())}")
        for pattern, handlers in list(self._handlers.items()):
            if pattern == topic or match_pattern(pattern, topic):
                logger.info(f"[DispatchLocal] Matched pattern '{pattern}' for topic '{topic}'")
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

    async def register_query_handler(self, topic: str, handler: Callable[[VelvetMessage], Awaitable[dict[str, Any] | None]]):
        """Register a handler for incoming P2P RPC queries (declare Zenoh Queryable)."""
        key = f"velvet/{topic}"
        self._local_queryables[topic] = handler
        
        if self._use_real_zenoh and self.session:
            try:
                def on_query(query):
                    """Callback from Zenoh (runs in Zenoh thread)."""
                    try:
                        import time
                        # Extract query payload
                        payload_bytes = bytes(query.value.payload) if query.value else b""
                        if payload_bytes:
                            msg = VelvetMessage.from_bytes(payload_bytes)
                        else:
                            msg = VelvetMessage(msg_type=topic, payload={}, source_device="")
                        
                        # Execute async handler on the event loop
                        async def run_and_reply():
                            try:
                                response_payload = await handler(msg)
                                if response_payload is None:
                                    response_payload = {}
                                response_msg = VelvetMessage(
                                    msg_type=f"{topic}/reply",
                                    payload=response_payload,
                                    source_device=self.device_id,
                                    correlation_id=msg.correlation_id
                                )
                                response_bytes = response_msg.to_bytes()
                                
                                # Send reply back via Zenoh query
                                sample = zenoh.Sample(key, response_bytes)
                                query.reply(sample)
                            except Exception as reply_err:
                                logger.error(f"Error executing query handler/reply: {reply_err}")
                                
                        if self._loop:
                            asyncio.run_coroutine_threadsafe(run_and_reply(), self._loop)
                            
                    except Exception as query_err:
                        logger.error(f"Error in on_query: {query_err}")
                        
                # Declare queryable in executor
                queryable = self._loop.call_soon_threadsafe(
                    lambda: self.session.declare_queryable(key, on_query)
                )
                self._queryables[key] = queryable
                logger.info(f"Registered secure RPC queryable for {key}")
                
            except Exception as e:
                logger.error(f"Failed to declare Zenoh queryable for {key}: {e}")
        else:
            logger.info(f"Registered local-only queryable for {topic}")

    async def request(self, topic: str, payload: dict[str, Any], timeout_sec: float = 5.0) -> list[VelvetMessage]:
        """Send a Point-to-Point secure query to a remote topic (The Basilisk Protocol)."""
        key = f"velvet/{topic}"
        msg = VelvetMessage(
            msg_type=topic,
            payload=payload,
            source_device=self.device_id
        )
        data = msg.to_bytes()
        responses = []
        
        if self._use_real_zenoh and self.session:
            try:
                import time
                # Send query and wait for replies
                # We use a Queue to collect replies in the Zenoh thread and read them in asyncio
                reply_queue = asyncio.Queue()
                
                def on_reply(reply):
                    try:
                        sample = reply.sample
                        reply_bytes = bytes(sample.payload)
                        reply_msg = VelvetMessage.from_bytes(reply_bytes)
                        if self._loop:
                            self._loop.call_soon_threadsafe(reply_queue.put_nowait, reply_msg)
                    except Exception as reply_err:
                        logger.error(f"Error in on_reply: {reply_err}")
                
                # Run Zenoh get in executor
                logger.debug(f"Sending Zenoh query for {key}")
                await self._loop.run_in_executor(
                    None, lambda: self.session.get(key, on_reply, value=data)
                )
                
                # Wait for replies with a timeout
                start_time = time.time()
                while time.time() - start_time < timeout_sec:
                    try:
                        # Wait for a reply from the queue
                        reply_msg = await asyncio.wait_for(reply_queue.get(), timeout=1.0)
                        responses.append(reply_msg)
                    except asyncio.TimeoutError:
                        break
                        
            except Exception as e:
                logger.error(f"Zenoh query request failed for {key}: {e}")
        else:
            # Mock / Local query fallback
            if topic in self._local_queryables:
                handler = self._local_queryables[topic]
                try:
                    resp_payload = await handler(msg)
                    if resp_payload is not None:
                        resp_msg = VelvetMessage(
                            msg_type=f"{topic}/reply",
                            payload=resp_payload,
                            source_device=self.device_id
                        )
                        responses.append(resp_msg)
                except Exception as local_err:
                    logger.error(f"Error running local mock queryable for {topic}: {local_err}")
                    
        return responses

# Alias for compatibility with DISPLAY Bridge
CommunicationFabric = ZenohFabric


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
