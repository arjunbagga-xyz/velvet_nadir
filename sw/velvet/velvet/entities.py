"""
Additional entities for the Velvet mesh.

Provides models for non-device entities that interact with or are tracked
by the system, such as humans and external APIs.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json

__all__ = [
    "HumanEntity",
    "ExternalEntity",
]

@dataclass
class HumanEntity:
    """A recognized person in the Velvet mesh."""
    human_id: str                         # "human_arjun"
    name: str                              # "Arjun"
    trust: str = "trusted"                 # "trusted" | "untrusted"
    status: str = "active"                 # "active" | "offline"
    current_task: str = ""                 # "Reviewing emails"
    communication_channels: list[dict] = field(default_factory=list)  # [{"type": "call", "address": "+123"}, ...]
    
    # Links to Xiang recognition data (if available)
    xiang_profile_id: str | None = None
    
    last_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "id": self.human_id,
            "name": self.name,
            "trust": self.trust,
            "status": self.status,
            "task": self.current_task,
            "communication_channels": self.communication_channels,
            "xiang_profile_id": self.xiang_profile_id,
            "last_seen": self.last_seen.isoformat(),
        }

@dataclass
class ExternalEntity:
    """An external service, webhook interface, or API boundary."""
    entity_id: str                         # "ext_openai"
    name: str                              # "OpenAI API"
    connection_type: str = "API"           # "API" | "webhook" | "mqtt"
    endpoint: str = ""
    auth_status: str = "none"              # "authenticated" | "expired" | "none"
    status: str = "offline"
    data_flow: str = "bidirectional"       # "inbound" | "outbound" | "bidirectional"
    last_communication: datetime | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.entity_id,
            "name": self.name,
            "connection_type": self.connection_type,
            "endpoint": self.endpoint,
            "auth_status": self.auth_status,
            "status": self.status,
            "data_flow": self.data_flow,
            "last_communication": self.last_communication.isoformat() if self.last_communication else None,
        }
