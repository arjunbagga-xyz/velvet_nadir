"""
Agent Hierarchy: Orchestrator → Supervisor → Worker.

Defines logical agent identities and directed communication channels.
Agents are NOT devices — they are logical roles that can span multiple
devices or share a single device.

Communication rules:
  - Worker ↔ Supervisor: Two-way (bidirectional)
  - Supervisor → Supervisor: One-way (broadcast)
  - Worker → Worker: Blocked (must go through supervisor)
  - Orchestrator → Any: Always allowed
"""

from __future__ import annotations

__all__ = [
    "AgentRole",
    "ChannelDirection",
    "AgentIdentity",
    "AgentChannel",
    "AgentOrchestrator",
]

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from loguru import logger


class AgentRole(Enum):
    """Role in the agent hierarchy."""
    ORCHESTRATOR = "orchestrator"  # Yi — top-level decision maker
    SUPERVISOR = "supervisor"      # Domain managers (home, health, etc.)
    WORKER = "worker"              # Task executors


class ChannelDirection(Enum):
    """Communication direction."""
    ONE_WAY = "one_way"            # from → to only
    TWO_WAY = "two_way"            # bidirectional


@dataclass
class AgentIdentity:
    """
    Logical identity of an agent (NOT a device).

    A device can host multiple agents. An agent can span multiple devices.
    """
    agent_id: str                           # Unique, e.g. "home-controller"
    agent_type: str                         # Logical type, e.g. "home_automation"
    role: AgentRole = AgentRole.WORKER
    device_ids: list[str] = field(default_factory=list)  # Hosting device(s)
    capabilities: list[str] = field(default_factory=list)
    parent_id: str | None = None            # Supervisor's agent_id
    custom_fields: dict = field(default_factory=dict)  # Extensible config (UI agent tab)
    
    # Runtime state (mutable)
    current_task: str = ""                    # "Orchestrating daily schedule"
    status: str = "idle"                      # "active" | "idle" | "error"
    
    @property
    def trust_level(self) -> str:
        """Agents inherit trust from their hierarchy position."""
        if self.role == AgentRole.ORCHESTRATOR:
            return "trusted"
        return "trusted"  # All registered agents are implicitly trusted



@dataclass
class AgentChannel:
    """
    A directed communication channel between two agents.

    Controls who can talk to whom and in which direction.
    """
    from_agent: str      # Source agent_id
    to_agent: str        # Destination agent_id
    direction: ChannelDirection = ChannelDirection.TWO_WAY
    allowed_msg_types: list[str] = field(default_factory=lambda: ["*"])


import asyncio
from velvet.task_graph import TaskGraph, TaskState

class AgentOrchestrator:
    """
    Manages agent registration, hierarchy, and communication rules.

    Enforces the directed communication pattern:
      Orchestrator → any
      Supervisor ↔ workers (of that supervisor)
      Supervisor → other supervisors (one-way)
      Worker → Worker: BLOCKED
    """

    def __init__(self):
        self._agents: dict[str, AgentIdentity] = {}
        self._channels: list[AgentChannel] = []
        self._active_tasks: dict[str, asyncio.Task] = {}
        self.task_graph = TaskGraph()
        self._register_default_shen_daemons()

    def _register_default_shen_daemons(self):
        """Register core Shen cognitive hierarchy daemons."""
        daemons = [
            AgentIdentity(agent_id="yi", agent_type="intent_router", role=AgentRole.ORCHESTRATOR, capabilities=["dispatch", "routing", "modality"]),
            AgentIdentity(agent_id="hun", agent_type="deep_reasoning", role=AgentRole.SUPERVISOR, parent_id="yi", capabilities=["reasoning", "tool_orchestration"]),
            AgentIdentity(agent_id="po", agent_type="reflex_engine", role=AgentRole.WORKER, parent_id="hun", capabilities=["fast_reflex", "vision"]),
            AgentIdentity(agent_id="jing", agent_type="memory_core", role=AgentRole.WORKER, parent_id="hun", capabilities=["memory_recall", "knowledge_graph"]),
            AgentIdentity(agent_id="xi", agent_type="background_scheduler", role=AgentRole.WORKER, parent_id="yi", capabilities=["breathe", "consolidation"]),
        ]
        for d in daemons:
            self.register_agent(d)

    def register_agent(self, identity: AgentIdentity):
        """Register an agent and auto-create hierarchy channels."""
        self._agents[identity.agent_id] = identity

        # Auto-create channels based on hierarchy
        if identity.parent_id and identity.parent_id in self._agents:
            parent = self._agents[identity.parent_id]

            # Worker ↔ Supervisor: Two-way
            if identity.role == AgentRole.WORKER and parent.role == AgentRole.SUPERVISOR:
                self._channels.append(AgentChannel(
                    from_agent=identity.agent_id,
                    to_agent=identity.parent_id,
                    direction=ChannelDirection.TWO_WAY,
                ))

            # Supervisor → Supervisor: One-way
            elif identity.role == AgentRole.SUPERVISOR and parent.role == AgentRole.SUPERVISOR:
                self._channels.append(AgentChannel(
                    from_agent=identity.parent_id,
                    to_agent=identity.agent_id,
                    direction=ChannelDirection.ONE_WAY,
                ))

        logger.info(
            f"[AgentOrchestrator] Registered {identity.role.value}: "
            f"{identity.agent_id} (parent={identity.parent_id})"
        )

    async def _run_worker_loop(self, agent_id: str):
        """Default execution task loop for a spawned dynamic worker agent."""
        logger.info(f"[AgentOrchestrator] Dynamic worker loop running for agent: {agent_id}")
        if hasattr(self, "_fabric") and self._fabric:
            topic = f"agent/{agent_id}/task_assigned"
            async def _on_task(payload: dict):
                task_id = payload.get('task_id', 'unknown')
                task_name = payload.get('name', 'unnamed')
                task_desc = payload.get('description', '')
                
                logger.info(f"[AgentOrchestrator] Worker {agent_id} executing assigned task: {task_name}")
                self.update_agent_task(agent_id, task=task_name, status="active")
                
                try:
                    from velvet.shen.hun import Hun
                    from velvet.gateway import get_gateway
                    gateway = get_gateway()
                    hun = Hun(llm_inference=gateway.llm_inference)
                    
                    self.update_graph_task_state(task_id, TaskState.IN_PROGRESS)
                    
                    # 1. Fetch Static Persona (Soul)
                    agent = self.get_agent(agent_id)
                    persona = agent.custom_fields.get("system_prompt", f"You are agent {agent_id}.") if agent else f"You are agent {agent_id}."
                    
                    # 2. Fetch Project Context
                    from velvet.context import get_context_manager, TrackType
                    ctx_mgr = get_context_manager()
                    project_context = ""
                    if TrackType.PROJECT in ctx_mgr.tracks:
                        project_context = f"Project Goal/Context: {ctx_mgr.tracks[TrackType.PROJECT].state}\n"
                    
                    # 3. Fetch Dynamic Memory (Jing)
                    past_memories_str = ""
                    try:
                        from velvet.shen.jing import Jing
                        jing = Jing()
                        memories = await jing.local_search(task_name, limit=5, filter={"agent_id": agent_id})
                        if memories:
                            past_memories_str = "Relevant Past Memories:\n- " + "\n- ".join(memories) + "\n"
                    except Exception as e:
                        logger.warning(f"[AgentOrchestrator] Failed to fetch memory for {agent_id}: {e}")
                    
                    context_str = f"{persona}\n\n{project_context}{past_memories_str}Your task is: {task_desc}"
                    result = await hun.reason(context=context_str, task=task_name)
                    
                    logger.info(f"[AgentOrchestrator] Worker {agent_id} finished task {task_name}")
                    self.update_graph_task_state(task_id, TaskState.COMPLETED, result=result)
                    self.update_agent_task(agent_id, task="idle", status="idle")
                except Exception as e:
                    logger.error(f"[AgentOrchestrator] Worker {agent_id} failed task {task_name}: {e}")
                    self.update_graph_task_state(task_id, TaskState.FAILED, error=str(e))
                    self.update_agent_task(agent_id, task="error", status="error")
                    
            await self._fabric.subscribe(topic, _on_task)

    def spawn_worker(
        self,
        agent_id: str,
        agent_type: str = "dynamic_worker",
        parent_id: str = "yi",
        capabilities: list[str] | None = None,
        custom_fields: dict | None = None,
        task_coro = None
    ) -> AgentIdentity:
        """
        Dynamically spawn an ad-hoc worker agent identity and active task loop.
        """
        caps = capabilities or ["task_execution"]
        parent = self._agents.get(parent_id)
        role = AgentRole.WORKER if (parent and parent.role != AgentRole.ORCHESTRATOR) else AgentRole.SUPERVISOR

        identity = AgentIdentity(
            agent_id=agent_id,
            agent_type=agent_type,
            role=role,
            parent_id=parent_id,
            capabilities=caps,
            status="active",
            custom_fields=custom_fields or {}
        )
        self.register_agent(identity)

        if task_coro is None:
            task_coro = self._run_worker_loop(agent_id)

        task = asyncio.create_task(task_coro)
        self._active_tasks[agent_id] = task
        logger.info(f"[AgentOrchestrator] Spawned active execution task loop for agent {agent_id}")

        return identity

    def kill_worker(self, agent_id: str) -> bool:
        """Terminate a dynamic worker and remove it from the roster."""
        if agent_id not in self._agents:
            return False
            
        task = self._active_tasks.get(agent_id)
        if task:
            task.cancel()
            del self._active_tasks[agent_id]
            
        del self._agents[agent_id]
        
        # Cleanup channels
        self._channels = [ch for ch in self._channels 
                          if ch.from_agent != agent_id and ch.to_agent != agent_id]
                          
        logger.info(f"[AgentOrchestrator] Killed worker {agent_id} and cleaned up channels")
        return True


    async def handle_delegation_request(self, from_agent_id: str, request_type: str, details: dict) -> dict:
        """
        Handle a delegation/budget request sent by a sub-agent to the CEO (Orchestrator).
        """
        sender = self.get_agent(from_agent_id)
        if not sender:
            return {"approved": False, "reason": f"Unknown agent '{from_agent_id}'"}

        logger.info(f"[AgentOrchestrator] CEO processing delegation request from {from_agent_id}: {request_type}")

        if request_type == "spawn_subagent":
            sub_id = details.get("sub_agent_id", f"{from_agent_id}_sub_{len(self._agents)}")
            sub_type = details.get("agent_type", "worker")
            sub_caps = details.get("capabilities", [])
            new_identity = self.spawn_worker(sub_id, agent_type=sub_type, parent_id=from_agent_id, capabilities=sub_caps)
            return {"approved": True, "spawned_agent_id": new_identity.agent_id}

        elif request_type == "budget_request":
            requested_amount = details.get("amount", 0)
            return {"approved": True, "granted_amount": requested_amount, "currency": "credits"}

    async def bind_fabric(self, fabric):
        """Bind Zenoh fabric subscriptions for CEO delegation and task assignments."""
        if not fabric:
            return
        self._fabric = fabric
        await fabric.subscribe("agent/ceo/delegation_request", self._handle_zenoh_delegation)
        await fabric.subscribe("agent/+/task_assigned", self._handle_zenoh_task_assigned)
        logger.info("[AgentOrchestrator] Wired Zenoh delegation and task assignment endpoints.")

    async def _handle_zenoh_delegation(self, payload: dict):
        from_id = payload.get("from_agent_id", "unknown")
        req_type = payload.get("request_type", "")
        details = payload.get("details", {})
        res = await self.handle_delegation_request(from_id, req_type, details)
        if self._fabric:
            await self._fabric.publish(f"agent/{from_id}/delegation_response", res)

    async def _handle_zenoh_task_assigned(self, payload: dict):
        logger.info(f"[AgentOrchestrator] Task assigned event received: {payload}")


    def can_communicate(self, from_id: str, to_id: str) -> bool:
        """
        Check if agent from_id can send messages to agent to_id.

        Rules:
          - Orchestrator can always communicate with anyone
          - Direct channel exists (TWO_WAY or ONE_WAY in correct direction)
          - Workers cannot talk to other workers
        """
        if from_id not in self._agents or to_id not in self._agents:
            return False

        from_agent = self._agents[from_id]
        to_agent = self._agents[to_id]

        # Orchestrator → anyone: always allowed
        if from_agent.role == AgentRole.ORCHESTRATOR:
            return True

        # Worker → Worker: blocked
        if from_agent.role == AgentRole.WORKER and to_agent.role == AgentRole.WORKER:
            return False

        # Check channels
        for ch in self._channels:
            if ch.direction == ChannelDirection.TWO_WAY:
                if (ch.from_agent == from_id and ch.to_agent == to_id) or \
                   (ch.from_agent == to_id and ch.to_agent == from_id):
                    return True
            elif ch.direction == ChannelDirection.ONE_WAY:
                if ch.from_agent == from_id and ch.to_agent == to_id:
                    return True

        return False

    def get_agent(self, agent_id: str) -> AgentIdentity | None:
        """Get an agent by ID."""
        return self._agents.get(agent_id)

    def get_agents_by_role(self, role: AgentRole) -> list[AgentIdentity]:
        """Get all agents with a specific role."""
        return [a for a in self._agents.values() if a.role == role]

    def get_all(self) -> list[AgentIdentity]:
        """Get all registered agent identities."""
        return list(self._agents.values())

    def get_children(self, parent_id: str) -> list[AgentIdentity]:
        """Get all agents whose parent is the given agent."""
        return [a for a in self._agents.values() if a.parent_id == parent_id]

    @property
    def agent_count(self) -> int:
        return len(self._agents)

    @property
    def channel_count(self) -> int:
        return len(self._channels)

    # --- TaskGraph and Runtime State Management ---
    def add_graph_task(self, name: str, description: str, dependencies: list[str] = None):
        """Add a task to the central TaskGraph."""
        return self.task_graph.add_task(name, description, dependencies)

    async def assign_graph_task(self, task_id: str, agent_id: str):
        """Assign a task in the graph and notify the agent via fabric."""
        self.task_graph.assign_task(task_id, agent_id)
        task = self.task_graph.tasks.get(task_id)
        if task and hasattr(self, "_fabric") and self._fabric:
            await self._fabric.publish(f"agent/{agent_id}/task_assigned", {
                "task_id": task_id,
                "name": task.name,
                "description": task.description
            })
            
    def update_graph_task_state(self, task_id: str, state: TaskState, result: Any = None, error: str = None):
        """Update the state of a task in the TaskGraph."""
        self.task_graph.update_task_state(task_id, state, result, error)

    # --- Configuration Mutation (UI / Bridge driven) ---
    def update_agent_task(self, agent_id: str, task: str, status: str = "active") -> bool:
        """Update an agent's current runtime task and status."""
        agent = self.get_agent(agent_id)
        if not agent:
            return False
        agent.current_task = task
        agent.status = status
        logger.debug(f"[AgentOrchestrator] Updated {agent_id} state: {status} | task: {task}")
        return True

    def update_agent_config(self, agent_id: str, **fields) -> bool:
        """Update an agent's configuration fields dynamically."""
        agent = self.get_agent(agent_id)
        if not agent:
            return False
            
        allowed_fields = {"agent_type", "role", "capabilities", "custom_fields"}
        for k, v in fields.items():
            if k in allowed_fields:
                if k == "role" and isinstance(v, str):
                    try:
                        agent.role = AgentRole(v)
                    except ValueError:
                        pass
                else:
                    setattr(agent, k, v)
                    
        logger.info(f"[AgentOrchestrator] Updated {agent_id} config: {list(fields.keys())}")
        return True

