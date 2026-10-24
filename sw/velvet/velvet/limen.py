"""
Limen Gateway (Threshold): Inter-Agent interop (A2A) and MCP integration.

Manages external tool registries, dynamic capability discovery,
and applies localized security/scrambling boundaries.
"""

__all__ = [
    "LimenGateway",
    "get_limen_gateway",
]

import asyncio
import os
import aiohttp
from loguru import logger
from typing import Any, Dict, List, Optional, Set
from velvet.config import get_config
from velvet.mirage import MirageProxy
from velvet.agents import AgentIdentity, AgentRole


class LimenGateway:
    """
    Limen Gateway.
    
    Exposes secure boundary controls for external agents (A2A) and MCP servers.
    Maintains a parallel tool registry for external/MCP integrations.
    """

    def __init__(self, agent_orchestrator=None):
        self.orchestrator = agent_orchestrator
        self.mcp_registry: Dict[str, Dict] = {}        # tool_name -> config details
        self.mcp_tool_schemas: Dict[str, Dict] = {}    # tool_name -> OpenAI-style tool schema
        self._local_servers: Set[str] = set()          # Names of local MCP servers (exempt from scrambling)
        self._session: Optional[aiohttp.ClientSession] = None

    async def _ensure_session(self):
        if self._session is None:
            self._session = aiohttp.ClientSession()

    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None

    def register_local_mcp(self, name: str, config: Dict[str, Any]) -> None:
        """Register a local MCP server (stdio or localhost). Exempt from scrambling."""
        self._local_servers.add(name)
        # Register the server config
        self.mcp_registry[name] = {
            "type": "local",
            "config": config,
            "status": "ready"
        }
        logger.info(f"[Limen] Registered local MCP server: {name} (scrambling exempt)")

    def register_remote_mcp(self, name: str, endpoint: str) -> None:
        """Register a remote/cloud MCP endpoint. Scrambled by default."""
        if name in self._local_servers:
            self._local_servers.remove(name)
        self.mcp_registry[name] = {
            "type": "remote",
            "endpoint": endpoint,
            "status": "ready"
        }
        logger.info(f"[Limen] Registered remote MCP server: {name} (scrambling active)")

    async def discover_capabilities(self, server_name: str) -> bool:
        """
        Query the external MCP server/agent for available tools.
        Dynamically imports schemas into the parallel tool registry.
        """
        server = self.mcp_registry.get(server_name)
        if not server:
            logger.warning(f"[Limen] Cannot discover capabilities for unknown server: {server_name}")
            return False

        try:
            await self._ensure_session()
            
            # Simple HTTP mock query for discovery
            # In production, this would execute the MCP protocol /tools/list handshakes
            if server["type"] == "remote":
                url = f"{server['endpoint']}/tools"
                async with self._session.get(url, timeout=5.0) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        tools = data.get("tools", [])
                        self._import_tool_schemas(server_name, tools)
                        return True
            else:
                # Local mock discovery (e.g. CLI tool config)
                mock_tools = [
                    {
                        "name": "execute_command",
                        "description": "Execute a shell command locally",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "command": {"type": "string", "description": "Command to run"}
                            },
                            "required": ["command"]
                        }
                    }
                ]
                self._import_tool_schemas(server_name, mock_tools)
                return True
        except Exception as e:
            logger.error(f"[Limen] Capability discovery failed for {server_name}: {e}")
            return False
            
        return False

    def _import_tool_schemas(self, server_name: str, tools: List[Dict]) -> None:
        """Import tools into the parallel registry schemas."""
        new_tools = []
        for t in tools:
            name = t.get("name")
            if not name:
                continue
            # Ensure unique tool naming to prevent collisions
            full_name = f"mcp_{server_name}_{name}"
            self.mcp_tool_schemas[full_name] = {
                "server_name": server_name,
                "schema": {
                    "type": "function",
                    "function": {
                        "name": full_name,
                        "description": t.get("description", ""),
                        "parameters": t.get("parameters", {"type": "object", "properties": {}})
                    }
                }
            }
            new_tools.append(full_name)
            logger.info(f"[Limen] Dynamically registered external tool: {full_name}")

        # Broadcast capabilities over Zenoh mesh
        if new_tools:
            try:
                from velvet.fabric import get_fabric
                fabric = get_fabric()
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(fabric.publish("velvet/mesh/mcp/announce", {
                        "server_name": server_name,
                        "tools": new_tools
                    }))
                else:
                    loop.run_until_complete(fabric.publish("velvet/mesh/mcp/announce", {
                        "server_name": server_name,
                        "tools": new_tools
                    }))
            except Exception as e:
                logger.debug(f"[Limen] Zenoh capabilities announcement skipped: {e}")

    async def execute_mcp_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an MCP tool.
        If the target server is Remote: scrambles outbound parameters and rehydrates responses.
        If the target server is Local: bypasses scrambling entirely.
        """
        tool_info = self.mcp_tool_schemas.get(tool_name)
        if not tool_info:
            return {"success": False, "error": f"Tool {tool_name} not found in parallel registry"}

        server_name = tool_info["server_name"]
        server = self.mcp_registry.get(server_name)
        is_local = server_name in self._local_servers

        # 1. Scramble parameters only if the destination server is remote
        smap = None
        exec_params = params.copy()
        if not is_local:
            logger.debug(f"[Limen] Scrambling parameters for remote tool execution: {tool_name}")
            proxy = MirageProxy()
            # Scramble all parameters collectively
            for k, v in list(exec_params.items()):
                if isinstance(v, str):
                    scrambled, smap = proxy.scramble(v, smap)
                    exec_params[k] = scrambled
        else:
            logger.debug(f"[Limen] Local MCP tool execution bypasses scrambling: {tool_name}")

        # 2. Execute
        result_data = {}
        try:
            await self._ensure_session()
            if is_local:
                # Simulate local execution (execution stays in boundary)
                result_data = {"status": "success", "result": f"Executed local tool {tool_name} with params {exec_params}"}
            else:
                # Simulate remote HTTP execution
                url = f"{server['endpoint']}/execute"
                payload = {"tool": tool_name.replace(f"mcp_{server_name}_", ""), "arguments": exec_params}
                async with self._session.post(url, json=payload, timeout=10.0) as resp:
                    if resp.status == 200:
                        result_data = await resp.json()
                    else:
                        result_data = {"status": "error", "result": f"Server returned error code {resp.status}"}
        except Exception as e:
            logger.error(f"[Limen] MCP tool execution failed: {e}")
            result_data = {"status": "error", "result": str(e)}

        # 3. Rehydrate responses only for remote calls
        if not is_local and smap is not None:
            logger.debug(f"[Limen] Rehydrating response from remote tool execution: {tool_name}")
            proxy = MirageProxy()
            if "result" in result_data and isinstance(result_data["result"], str):
                result_data["result"] = proxy.rehydrate(result_data["result"], smap)

        return result_data

    def register_external_agent(self, agent_id: str, capabilities: List[str]) -> None:
        """Register an external A2A agent under Worker role in the registry."""
        if not self.orchestrator:
            logger.warning("[Limen] No orchestrator attached, skipping A2A agent registration")
            return
            
        identity = AgentIdentity(
            agent_id=agent_id,
            agent_type="external_a2a_agent",
            role=AgentRole.WORKER,
            capabilities=capabilities,
            custom_fields={"external": True}
        )
        self.orchestrator.register_agent(identity)


# Singleton
_limen_gateway: Optional[LimenGateway] = None

def get_limen_gateway(orchestrator=None) -> LimenGateway:
    """Get global Limen gateway instance."""
    global _limen_gateway
    if _limen_gateway is None:
        _limen_gateway = LimenGateway(orchestrator)
    elif orchestrator and not _limen_gateway.orchestrator:
        _limen_gateway.orchestrator = orchestrator
    return _limen_gateway
