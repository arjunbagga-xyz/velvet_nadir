"""
Context management system for Velvet Nadir.

Maintains parallel context tracks (Personal, Spatial, Project, Business, Agent)
with engagement levels and state persistence.
"""

__all__ = [
    "TrackType",
    "EngagementLevel",
    "ContextTrack",
    "WorkingMemory",
    "ContextManager",
    "get_context_manager",
    "init_context_manager",
    "init_context_manager_with_persistence",
]

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import asyncio
from loguru import logger


class EngagementLevel(Enum):
    """Current engagement level with the user."""
    PAUSED = 0       # System is paused/sleeping
    MONITORING = 1   # Background monitoring, no active interaction
    ACTIVE = 2       # Actively engaged, awaiting input  
    FOCUSED = 3      # Deep engagement, conversation in progress


class TrackType(Enum):
    """Types of context tracks."""
    PERSONAL = "personal"     # On-body/mobile context
    SPATIAL = "spatial"       # Location-based context
    PROJECT = "project"       # Active project/task context
    BUSINESS = "business"     # Work/business context
    AGENT = "agent"           # Background agent operations


@dataclass
class ContextTrack:
    """A single context track maintaining state for one domain."""
    track_type: TrackType
    engagement: EngagementLevel = EngagementLevel.MONITORING
    state: dict[str, Any] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def update(self, key: str, value: Any) -> None:
        """Update a state value."""
        self.state[key] = value
        self.last_updated = datetime.now(timezone.utc)
        
    def get(self, key: str, default: Any = None) -> Any:
        """Get a state value."""
        return self.state.get(key, default)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "type": self.track_type.value,
            "engagement": self.engagement.name,
            "state": self.state,
            "last_updated": self.last_updated.isoformat(),
        }


@dataclass
class ContextWorkspace:
    """A rich workspace container displayed in the mesh view.
    
    Two types:
    - Context: perpetual, always-on domain (e.g. Personal, Maintenance)
    - Project: goal-driven with progress tracking and an end state
    
    Wraps a ContextTrack and adds entity relationships, progress,
    artifacts, and hierarchy for the UI.
    """
    workspace_id: str                             # Unique, e.g. "ws_personal_001"
    name: str                                      # "Personal Context"
    track_type: TrackType                          # Links to existing track system
    subtype: str = "context"                       # "context" | "project"
    status: str = "active"                         # Derived from EngagementLevel
    progress: float = 0.0                          # 0-100, ONLY for project subtype
    
    # Hierarchy
    parent_id: str | None = None                   # Parent workspace ID (for nesting)
    
    # Entity references (by ID, not embedded)
    agent_ids: list[str] = field(default_factory=list)     # AgentIdentity refs
    human_ids: list[str] = field(default_factory=list)     # Human entity refs  
    device_ids: list[str] = field(default_factory=list)    # Device refs (replaces "hardware")
    robot_ids: list[str] = field(default_factory=list)     # Robot device refs
    
    artifacts: list[str] = field(default_factory=list)     # Artifact names/IDs
    
    # UI layout state (optional, persisted for consistent positioning)
    ui_position: dict = field(default_factory=dict)        # {"x": 200, "y": 300}
    
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    @property
    def is_project(self) -> bool:
        return self.subtype == "project"
    
    @property
    def is_complete(self) -> bool:
        return self.is_project and self.progress >= 100.0


@dataclass 
class WorkingMemory:
    """Short-term working memory for current session."""
    conversation_buffer: list[dict] = field(default_factory=list)
    recent_events: list[dict] = field(default_factory=list)
    pending_actions: list[dict] = field(default_factory=list)
    max_conversation_turns: int = 20
    max_events: int = 50
    
    def add_message(self, role: str, content: str, **metadata) -> None:
        """Add a message to the conversation buffer."""
        self.conversation_buffer.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **metadata,
        })
        # Trim to max length
        if len(self.conversation_buffer) > self.max_conversation_turns:
            self.conversation_buffer = self.conversation_buffer[-self.max_conversation_turns:]
            
    def add_event(self, event_type: str, data: dict) -> None:
        """Add an event to recent events."""
        self.recent_events.append({
            "type": event_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        if len(self.recent_events) > self.max_events:
            self.recent_events = self.recent_events[-self.max_events:]
            
    def get_context_for_llm(self) -> list[dict]:
        """Get conversation history formatted for LLM."""
        return [
            {"role": msg["role"], "content": msg["content"]}
            for msg in self.conversation_buffer
        ]


class ContextManager:
    """
    Central context manager maintaining all tracks and memory.
    
    Provides:
    - Parallel context tracks (Personal, Spatial, Project, Business, Agent)
    - Working memory for current session
    - Context summarization for LLM input
    - Persistence via SQLite store
    """
    
    def __init__(self, enabled_tracks: list[str] | None = None):
        self.tracks: dict[TrackType, ContextTrack] = {}
        self.workspaces: dict[str, ContextWorkspace] = {}
        self.working_memory = WorkingMemory()
        self.global_engagement = EngagementLevel.MONITORING
        self._lock = asyncio.Lock()
        self._persistence = None  # Will be set by init if available
        
        # Initialize enabled tracks
        enabled = enabled_tracks or [t.value for t in TrackType]
        for track_type in TrackType:
            if track_type.value in enabled:
                self.tracks[track_type] = ContextTrack(track_type=track_type)
                
        # Initialize default workspaces
        self._init_default_workspaces()
                
        logger.info(f"Context manager initialized with tracks: {list(self.tracks.keys())}")
        
    def _init_default_workspaces(self):
        """Initialize the default user workspaces."""
        if TrackType.PERSONAL in self.tracks:
            ws_personal = ContextWorkspace(
                workspace_id="ws_personal_default",
                name="Personal",
                track_type=TrackType.PERSONAL,
                subtype="context"
            )
            self.workspaces[ws_personal.workspace_id] = ws_personal
            
        if TrackType.AGENT in self.tracks:  # Using AGENT track for Maintenance as closest fit
            ws_maint = ContextWorkspace(
                workspace_id="ws_maintenance_default",
                name="System Maintenance",
                track_type=TrackType.AGENT,
                subtype="context"
            )
            self.workspaces[ws_maint.workspace_id] = ws_maint
        
    def set_persistence(self, memory):
        """Set the persistence backend (PersistentMemory instance)."""
        self._persistence = memory
        
    def set_locus_engine(self, locus):
        """Attach the Locus spatial engine."""
        self._locus = locus
        
    def get_location(self, device_id: str) -> dict | None:
        """Get the current spatial location and geofence state of a device."""
        if not hasattr(self, "_locus") or not self._locus:
            return None
        loc = self._locus.get_device_location(device_id)
        if not loc:
            return None
        fences = self._locus.get_current_fences(loc.lat, loc.lon)
        return {
            "lat": loc.lat,
            "lon": loc.lon,
            "accuracy": loc.accuracy_meters,
            "fences": fences
        }
        
    def merge_tracks(self) -> None:
        """Phase 3: Merge overlapping spatial/personal context tracks."""
        # Stub for context track merging
        pass
        
    async def load_from_storage(self) -> bool:
        """Load context tracks from persistent storage."""
        if not self._persistence:
            return False
            
        try:
            stored = await self._persistence.store.load_all_tracks()
            
            async with self._lock:
                for track_type_str, data in stored.items():
                    try:
                        track_type = TrackType(track_type_str)
                        if track_type in self.tracks:
                            self.tracks[track_type].state = data.get("state", {})
                            self.tracks[track_type].engagement = EngagementLevel[data.get("engagement", "MONITORING")]
                            logger.debug(f"Loaded track: {track_type_str}")
                    except (KeyError, ValueError) as e:
                        logger.warning(f"Could not load track {track_type_str}: {e}")
                        
            logger.info(f"Loaded {len(stored)} context tracks from storage")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load context from storage: {e}")
            return False
            
    async def save_to_storage(self) -> bool:
        """Save all context tracks to persistent storage."""
        if not self._persistence:
            return False
            
        try:
            async with self._lock:
                for track_type, track in self.tracks.items():
                    await self._persistence.store.save_track(
                        track_type.value,
                        track.state,
                        track.engagement.name,
                    )
                    
            logger.debug("Saved context tracks to storage")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save context to storage: {e}")
            return False
        
    async def update_track(self, track_type: TrackType, key: str, value: Any) -> None:
        """Update a value in a specific track."""
        async with self._lock:
            if track_type in self.tracks:
                self.tracks[track_type].update(key, value)
                logger.debug(f"Updated {track_type.value}.{key} = {value}")
                
        # Auto-save if persistence is enabled
        if self._persistence:
            await self.save_to_storage()
                
    async def set_engagement(self, level: EngagementLevel, track: TrackType | None = None) -> None:
        """Set engagement level globally or for a specific track."""
        async with self._lock:
            if track:
                if track in self.tracks:
                    self.tracks[track].engagement = level
            else:
                self.global_engagement = level
                # Propagate to all tracks
                for t in self.tracks.values():
                    t.engagement = level
            logger.info(f"Engagement set to {level.name}")
            
    async def get_active_context(self) -> dict[str, Any]:
        """Get combined context from all active tracks."""
        async with self._lock:
            context = {
                "global_engagement": self.global_engagement.name,
                "tracks": {},
                "working_memory": {
                    "conversation_length": len(self.working_memory.conversation_buffer),
                    "recent_events_count": len(self.working_memory.recent_events),
                    "pending_actions_count": len(self.working_memory.pending_actions),
                },
            }
            
            for track_type, track in self.tracks.items():
                if track.engagement != EngagementLevel.PAUSED:
                    context["tracks"][track_type.value] = track.to_dict()
                    
            return context
            
    # --- Workspace CRUD (UI / Network Bridge driven) ---
    
    async def create_workspace(self, name: str, track_type: TrackType, subtype: str = "context", parent_id: str | None = None) -> ContextWorkspace:
        """Create a new custom workspace container. (User-initiated only)."""
        import uuid
        ws_id = f"ws_custom_{uuid.uuid4().hex[:8]}"
        ws = ContextWorkspace(
            workspace_id=ws_id,
            name=name,
            track_type=track_type,
            subtype=subtype,
            parent_id=parent_id
        )
        async with self._lock:
            self.workspaces[ws_id] = ws
        logger.info(f"Created custom workspace: {name} ({subtype})")
        return ws
        
    async def delete_workspace(self, workspace_id: str) -> bool:
        """Delete a custom workspace. Cannot delete default workspaces."""
        if workspace_id in ("ws_personal_default", "ws_maintenance_default"):
            logger.warning(f"Attempted to delete protected default workspace: {workspace_id}")
            return False
            
        async with self._lock:
            if workspace_id in self.workspaces:
                del self.workspaces[workspace_id]
                logger.info(f"Deleted workspace: {workspace_id}")
                return True
        return False
        
    def get_workspace(self, workspace_id: str) -> ContextWorkspace | None:
        """Get a workspace by ID."""
        return self.workspaces.get(workspace_id)
        
    def get_all_workspaces(self) -> list[ContextWorkspace]:
        """Get all active workspaces."""
        return list(self.workspaces.values())
            
    async def build_llm_context(self, max_tokens: int = 2000) -> str:
        """Build a context summary string for LLM consumption."""
        ctx = await self.get_active_context()
        
        parts = []
        parts.append(f"## Current Context (Engagement: {ctx['global_engagement']})")
        parts.append("")
        
        for track_name, track_data in ctx["tracks"].items():
            parts.append(f"### {track_name.title()} Track")
            state = track_data.get("state", {})
            for key, value in state.items():
                parts.append(f"- {key}: {value}")
            parts.append("")
            
        # Add recent events summary
        if self.working_memory.recent_events:
            parts.append("### Recent Events")
            for event in self.working_memory.recent_events[-5:]:
                parts.append(f"- [{event['type']}] {event['data']}")
            parts.append("")
            
        result = "\n".join(parts)
        
        # Truncate if too long (rough estimate)
        if len(result) > max_tokens * 4:  # ~4 chars per token
            result = result[:max_tokens * 4] + "\n... (truncated)"
            
        return result
        
    def add_conversation_message(self, role: str, content: str, **metadata) -> None:
        """Add a message to working memory (synchronous for convenience)."""
        self.working_memory.add_message(role, content, **metadata)
        
    def add_event(self, event_type: str, data: dict) -> None:
        """Add an event to working memory (synchronous for convenience)."""
        self.working_memory.add_event(event_type, data)


# Singleton instance
_context_manager: ContextManager | None = None


def get_context_manager() -> ContextManager:
    """Get the global context manager instance."""
    if _context_manager is None:
        raise RuntimeError("Context manager not initialized. Call init_context_manager() first.")
    return _context_manager


def init_context_manager(enabled_tracks: list[str] | None = None) -> ContextManager:
    """Initialize the global context manager."""
    global _context_manager
    _context_manager = ContextManager(enabled_tracks)
    return _context_manager


async def init_context_manager_with_persistence(
    enabled_tracks: list[str] | None = None,
    memory = None,
) -> ContextManager:
    """Initialize the context manager with persistence support."""
    global _context_manager
    _context_manager = ContextManager(enabled_tracks)
    
    if memory:
        _context_manager.set_persistence(memory)
        await _context_manager.load_from_storage()
        
    return _context_manager
