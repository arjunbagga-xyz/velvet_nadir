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

    # --- Runtime State and Configuration Mutation (UI / Bridge driven) ---
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
