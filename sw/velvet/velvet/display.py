"""
Display Bridge Server

Serves the static UI dashboard files and provides a WebSocket connection
for real-time bidirectional state syncing between the Velvet backend and the UI.
"""

import sys
import asyncio
import json
import ssl
from pathlib import Path
from loguru import logger

# Try importing aiohttp
try:
    import aiohttp
    from aiohttp import web, WSMsgType
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

from velvet.config import DisplayConfig
from velvet.fabric import CommunicationFabric, MessageType, VelvetMessage
from velvet.devices import HardwareRegistry
from velvet.context import ContextManager
from velvet.agents import AgentOrchestrator
from velvet.display_state import (
    serialize_device_for_ui,
    serialize_workspace_for_ui,
    serialize_agent_for_ui,
    serialize_log_event
)

# Optional: Jing memory system
try:
    from velvet.shen.jing import Jing
except ImportError:
    Jing = None


class DisplayBridge:
    """Manages the aiohttp web server and WebSocket connections to UI clients."""
    
    def __init__(self, config: DisplayConfig, fabric: CommunicationFabric,
                 registry: HardwareRegistry, context: ContextManager,
                 agents: AgentOrchestrator, locus=None, jing=None):
                 
        self.config = config
        self.fabric = fabric
        self.registry = registry
        self.context = context
        self.agents = agents
        self.locus = locus
        self.jing = jing  # Jing memory system (for KG snapshots + search)
        
        self.app = None
        self.runner = None
        self.site = None
        
        self.active_websockets: set[web.WebSocketResponse] = set()
        
        # Determine paths
        if self.config.dashboard_path:
            self.static_dir = Path(self.config.dashboard_path)
        else:
            # Default to sw/UI/app relative to sw/velvet/velvet
            base_dir = Path(__file__).resolve().parent.parent.parent
            self.static_dir = base_dir / "UI" / "app"
            
    async def start(self):
        """Start the display HTTP and WebSocket server."""
        if not self.config.enabled:
            return
            
        if not AIOHTTP_AVAILABLE:
            logger.error("aiohttp is required for the DisplayBridge. Run: pip install aiohttp")
            return
            
        if not self.static_dir.exists() or not self.static_dir.is_dir():
            logger.error(f"Dashboard static path not found: {self.static_dir}")
            return
            
        self.app = web.Application()
        
        # Setup routes
        self.app.router.add_get('/ws', self.websocket_handler)
        self.app.router.add_get('/api/skills/pending', self.get_pending_skills)
        self.app.router.add_post('/api/skills/pending/resolve', self.resolve_pending_skill)
        
        # Serve static files (fallback to index.html for root)
        self.app.router.add_get('/', self.index_handler)
        self.app.router.add_static('/', self.static_dir)

        # Setup SSL context for mTLS if required by system policy (deferred to a larger mesh security rollout)
        # For this sprint, we bind locally to the mesh interface.
        ssl_context = None

        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        
        try:
            self.site = web.TCPSite(self.runner, self.config.http_host, self.config.http_port, ssl_context=ssl_context)
            await self.site.start()
            logger.info(f"[DisplayBridge] Server listening on http://{self.config.http_host}:{self.config.http_port}/")
        except Exception as e:
            logger.error(f"[DisplayBridge] Failed to start server: {e}")
            return
            
        # Subscribe to Fabric events to push to UI
        await self.fabric.subscribe(MessageType.MESH_DEVICE_HEARTBEAT.value, self._handle_device_update)
        await self.fabric.subscribe(MessageType.TRANSCRIPT.value, self._handle_event)
        await self.fabric.subscribe(MessageType.WAKE_WORD.value, self._handle_event)
        await self.fabric.subscribe(MessageType.SKILL_REQUEST.value, self._handle_event)
        await self.fabric.subscribe(MessageType.DISPLAY_CHAT_OUT.value, self._handle_chat_out)
        
        # Add broad subscriptions for the Noise page
        await self.fabric.subscribe("sys/**", self._handle_event)
        await self.fabric.subscribe("action/**", self._handle_event)
        await self.fabric.subscribe("mesh/**", self._handle_event)
        await self.fabric.subscribe("audio/**", self._handle_event)
        await self.fabric.subscribe("vision/**", self._handle_event)
        await self.fabric.subscribe("skill/**", self._handle_event)
        await self.fabric.subscribe("context/**", self._handle_event)

    async def stop(self):
        """Stop the display server."""
        if not self.config.enabled or not self.runner:
            return
            
        logger.info("[DisplayBridge] Stopping server...")
        # Close all active websockets cleanly
        for ws in set(self.active_websockets):
            await ws.close(code=aiohttp.WSCloseCode.GOING_AWAY, message='Server shutdown')
            
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()

    # --- HTTP Handlers ---

    async def index_handler(self, request):
        """Serve the index.html file."""
        return web.FileResponse(self.static_dir / "index.html")

    async def websocket_handler(self, request):
        """Handle WebSocket connections from the UI dashboard."""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        self.active_websockets.add(ws)
        logger.info(f"[DisplayBridge] New WebSocket connection from {request.remote}")
        
        try:
            # 1. Send initial snapshot of the entire state
            snapshot = self._build_full_snapshot()
            await ws.send_json({"type": "snapshot", **snapshot})
            
            # 2. Listen for incoming messages from the UI
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        await self._handle_client_message(data, ws)
                    except json.JSONDecodeError:
                        logger.error("[DisplayBridge] Invalid JSON from client")
                    except Exception as e:
                        logger.error(f"[DisplayBridge] Error handling client msg: {e}")
                elif msg.type == WSMsgType.ERROR:
                    logger.error(f"[DisplayBridge] WebSocket connection closed with exception {ws.exception()}")
        finally:
            self.active_websockets.discard(ws)
            logger.info(f"[DisplayBridge] WebSocket connection closed from {request.remote}")
            
        return ws

    # --- Push to Clients ---

    async def push_to_all(self, msg_type: str, data: dict):
        """Push a JSON message to all connected websockets."""
        if not self.active_websockets:
            logger.info(f"[DisplayBridge] push_to_all failed: No active websockets for {msg_type}")
            return
            
        logger.info(f"[DisplayBridge] push_to_all: Pushing type '{msg_type}' to {len(self.active_websockets)} websockets. Data: {data}")
        payload = {"type": msg_type, **data}
        for ws in self.active_websockets:
            try:
                await ws.send_json(payload)
                logger.info(f"[DisplayBridge] Successfully sent '{msg_type}' to WS client")
            except Exception as e:
                logger.error(f"[DisplayBridge] Failed to send push message: {e}")

    def _build_full_snapshot(self) -> dict:
        """Build a complete state snapshot for newly connected clients."""
        devices = []
        for dev in self.registry.get_all_devices():
            devices.append(serialize_device_for_ui(dev, self.locus))
            
        # We need mock maps for agents/humans since those stores aren't fully populated yet
        agent_map = {a.agent_id: a for a in self.agents.get_all()} if hasattr(self.agents, "get_all") else {}
        dev_map = {d.device_id: d for d in self.registry.get_all_devices()}
            
        workspaces = []
        for ws in self.context.get_all_workspaces():
            workspaces.append(serialize_workspace_for_ui(ws, dev_map, agent_map, {}))
            
        agents = []
        for a in agent_map.values():
            agents.append(serialize_agent_for_ui(a))
        
        # Memory graph from Jing's MemPalace KnowledgeGraph
        memory_graph = {"nodes": [], "links": []}
        if self.jing and hasattr(self.jing, 'get_graph_snapshot'):
            try:
                memory_graph = self.jing.get_graph_snapshot()
            except Exception as e:
                logger.error(f"[DisplayBridge] Failed to get memory graph: {e}")
            
        return {
            "devices": devices,
            "workspaces": workspaces,
            "agents": agents,
            "events": [],
            "memory": memory_graph
        }

    # --- Fabric Event Handlers (Backend → UI) ---

    async def _handle_device_update(self, msg: VelvetMessage):
        """When a device heartbeats, send the updated device object to UI."""
        dev = self.registry.get_device(msg.source_device)
        if dev:
            await self.push_to_all("device.update", {"data": serialize_device_for_ui(dev, self.locus)})

    async def _handle_event(self, msg: VelvetMessage):
        """General system events for the Log view."""
        logger.info(f"[DisplayBridge] _handle_event called for msg_type={msg.msg_type}")
        msg_id = msg.correlation_id or f"ev-{int(msg.timestamp.timestamp()*1000)}"
        payload = msg.payload if isinstance(msg.payload, dict) else {"text": str(msg.payload)}
        log_ev = serialize_log_event(msg_id, msg.timestamp, msg.source_device, msg.msg_type, payload.get("text", str(msg.payload)))
        logger.info(f"[DisplayBridge] Serialized log event: {log_ev}")
        await self.push_to_all("event.log", {"data": log_ev})
        
    async def _handle_chat_out(self, msg: VelvetMessage):
        """When the Gateway responds, push text to the Agent Orb in the UI."""
        text = msg.payload.get("text", "")
        await self.push_to_all("chat.response", {"data": {"role": "agent", "text": text}})
        # Also let UI know it's speaking
        await self.push_to_all("gateway.state", {"state": "speaking"})

    # --- Client Event Handlers (UI → Backend) ---

    async def _handle_client_message(self, data: dict, ws: web.WebSocketResponse):
        """Handle incoming messages from the UI dashboard."""
        msg_type = data.get("type")
        
        if msg_type == "chat.send":
            text = data.get("text", "")
            logger.info(f"[DisplayBridge] UI sent chat: {text}")
            # Tell UI Gateway is processing
            await self.push_to_all("gateway.state", {"state": "processing"})
            # Push into Fabric for Gateway to pick up
            await self.fabric.publish(
                topic=MessageType.DISPLAY_CHAT_IN.value,
                payload={"text": text, "sender": "display_ui"}
            )
            
        elif msg_type == "workspace.create":
            ws_obj = await self.context.create_workspace(
                name=data.get("name", "New Workspace"),
                track_type=data.get("track_type", "CUSTOM"),
                subtype=data.get("subtype", "context")
            )
            await self.push_to_all("workspace.update", {"data": serialize_workspace_for_ui(ws_obj, {}, {}, {})})
            
        elif msg_type == "workspace.delete":
            ws_id = data.get("id")
            if ws_id:
                success = await self.context.delete_workspace(ws_id)
                if success:
                    await self.push_to_all("workspace.delete", {"id": ws_id})
                    
        elif msg_type == "agent.update":
            # agent mutation
            aid = data.get("agent_id")
            fields = data.get("fields", {})
            if aid and hasattr(self.agents, "update_agent_config"):
                self.agents.update_agent_config(aid, **fields)
                a = self.agents.get_agent(aid)
                if a:
                    await self.push_to_all("agent.update", {"data": serialize_agent_for_ui(a)})
                    
        elif msg_type == "jing.search":
            query = data.get("query", "")
            if query and self.jing:
                try:
                    results = await self.jing.recall(query, limit=10, deep=True)
                    graph_results = await self.jing.graph_query(query)
                    await ws.send_json({
                        "type": "jing.results",
                        "data": {
                            "query": query,
                            "memories": results,
                            "relations": graph_results
                        }
                    })
                except Exception as e:
                    logger.error(f"[DisplayBridge] Jing search failed: {e}")
                    await ws.send_json({
                        "type": "jing.results",
                        "data": {"query": query, "memories": [], "relations": [], "error": str(e)}
                    })

    async def get_pending_skills(self, request: web.Request) -> web.Response:
        """Get list of pending skills awaiting user approval."""
        from velvet.config import get_config
        import json
        cfg = get_config()
        pending_file = Path(cfg.storage.data_dir) / "pending_skills.json"
        
        if not pending_file.exists():
            return web.json_response([])
            
        try:
            pending = json.loads(pending_file.read_text())
            return web.json_response(list(pending.values()))
        except Exception as e:
            logger.error(f"[DisplayBridge] Failed to read pending skills: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def resolve_pending_skill(self, request: web.Request) -> web.Response:
        """Approve or reject a pending skill."""
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)
            
        skill_name = data.get("skill_name")
        approved = data.get("approved")
        
        if not skill_name or approved is None:
            return web.json_response({"error": "Missing skill_name or approved"}, status=400)
            
        # Try to find Saraswati task from Gateway
        try:
            from velvet.gateway import get_gateway
            gw = get_gateway()
            saraswati = gw.xi._tasks.get("saraswati")
        except Exception:
            saraswati = None
            
        if not saraswati:
            # Fallback direct implementation if Saraswati task is not running
            from velvet.config import get_config
            import json
            cfg = get_config()
            pending_file = Path(cfg.storage.data_dir) / "pending_skills.json"
            if pending_file.exists():
                try:
                    pending = json.loads(pending_file.read_text())
                    if skill_name in pending:
                        skill_data = pending.pop(skill_name)
                        pending_file.write_text(json.dumps(pending, indent=2))
                        if approved:
                            # Deploy it
                            from velvet.shen.saraswati import Vidya, GeneratedSkill
                            vidya = Vidya()
                            skill = GeneratedSkill(
                                name=skill_data["name"],
                                code=skill_data["code"],
                                description=skill_data.get("description", "")
                            )
                            success = vidya.deploy(skill)
                            return web.json_response({"success": success})
                        return web.json_response({"success": True})
                except Exception as e:
                    return web.json_response({"error": str(e)}, status=500)
            return web.json_response({"error": "Saraswati task or skill not found"}, status=404)
            
        # Call the helper method on Saraswati
        success = await saraswati.resolve_pending_skill(skill_name, approved)
        return web.json_response({"success": success})
