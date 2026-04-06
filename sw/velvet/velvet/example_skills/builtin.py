"""
Built-in example skills for Velvet Nadir.

These demonstrate the skill system and provide basic functionality.
"""

from datetime import datetime
from ..skills import (
    skill,
    SkillCategory,
    SkillParameter,
    SkillResult,
    AutonomyLevel,
)


@skill(
    name="get_time",
    description="Get the current time and optionally the date",
    category=SkillCategory.DIGITAL,
    parameters=[
        SkillParameter("include_date", "bool", "Whether to include the date", required=False, default=False),
    ],
    autonomy=AutonomyLevel.LEVEL_0,  # Read-only, no action needed
    tags=["time", "date", "utility"],
)
async def get_time(include_date: bool = False) -> SkillResult:
    """Get current time."""
    now = datetime.now()
    
    if include_date:
        time_str = now.strftime("%A, %B %d, %Y at %I:%M %p")
    else:
        time_str = now.strftime("%I:%M %p")
        
    return SkillResult.ok(
        data={"time": time_str, "timestamp": now.isoformat()},
        speak=f"It's {time_str}",
    )


@skill(
    name="system_status",
    description="Get the current system status including active context tracks",
    category=SkillCategory.DIGITAL,
    parameters=[],
    autonomy=AutonomyLevel.LEVEL_0,
    tags=["system", "status", "debug"],
)
async def system_status() -> SkillResult:
    """Get system status."""
    from ..context import get_context_manager
    from ..gateway import get_gateway
    
    ctx_mgr = get_context_manager()
    gateway = get_gateway()
    
    ctx = await ctx_mgr.get_active_context()
    
    status = {
        "gateway_state": gateway.state.value,
        "engagement": ctx["global_engagement"],
        "active_tracks": list(ctx["tracks"].keys()),
        "conversation_length": ctx["working_memory"]["conversation_length"],
        "pending_actions": len(gateway.pending_actions),
    }
    
    speak_text = (
        f"System is {gateway.state.value}. "
        f"Engagement level is {ctx['global_engagement'].lower()}. "
        f"{len(ctx['tracks'])} context tracks are active."
    )
    
    return SkillResult.ok(data=status, speak=speak_text)


@skill(
    name="remember",
    description="Store a piece of information in memory",
    category=SkillCategory.DIGITAL,
    parameters=[
        SkillParameter("key", "string", "A short label for the memory"),
        SkillParameter("value", "string", "The information to remember"),
    ],
    autonomy=AutonomyLevel.LEVEL_1,  # Informative - just storing
    tags=["memory", "note", "remember"],
)
async def remember(key: str, value: str) -> SkillResult:
    """Store something in memory."""
    from ..context import get_context_manager, TrackType
    
    ctx_mgr = get_context_manager()
    await ctx_mgr.update_track(TrackType.PERSONAL, f"memory:{key}", value)
    
    # Check if persistent memory is available
    persistent = ctx_mgr._persistence is not None and ctx_mgr._persistence.is_ready()
    suffix = "" if persistent else " — but only until I restart"
    
    return SkillResult.ok(
        data={"key": key, "value": value, "persistent": persistent},
        speak=f"I'll remember that {key} is {value}{suffix}",
    )


@skill(
    name="recall",
    description="Recall a piece of information from memory",
    category=SkillCategory.DIGITAL,
    parameters=[
        SkillParameter("key", "string", "The label of the memory to recall"),
    ],
    autonomy=AutonomyLevel.LEVEL_0,
    tags=["memory", "note", "recall"],
)
async def recall(key: str) -> SkillResult:
    """Recall something from memory."""
    from ..context import get_context_manager, TrackType
    
    ctx_mgr = get_context_manager()
    track = ctx_mgr.tracks.get(TrackType.PERSONAL)
    
    if track:
        value = track.get(f"memory:{key}")
        if value:
            return SkillResult.ok(
                data={"key": key, "value": value},
                speak=f"{key} is {value}",
            )
            
    return SkillResult.ok(
        data={"key": key, "value": None},
        speak=f"I don't have anything stored for {key}",
    )


@skill(
    name="set_engagement",
    description="Set the system's engagement level",
    category=SkillCategory.DIGITAL,
    parameters=[
        SkillParameter(
            "level", "string", 
            "Engagement level: 'paused', 'monitoring', 'active', or 'focused'"
        ),
    ],
    autonomy=AutonomyLevel.LEVEL_2,  # Needs approval to change behavior
    tags=["system", "engagement", "mode"],
)
async def set_engagement(level: str) -> SkillResult:
    """Set engagement level."""
    from ..context import get_context_manager, EngagementLevel
    
    level_map = {
        "paused": EngagementLevel.PAUSED,
        "monitoring": EngagementLevel.MONITORING,
        "active": EngagementLevel.ACTIVE,
        "focused": EngagementLevel.FOCUSED,
    }
    
    if level.lower() not in level_map:
        return SkillResult.fail(f"Unknown level: {level}. Use: paused, monitoring, active, focused")
        
    ctx_mgr = get_context_manager()
    await ctx_mgr.set_engagement(level_map[level.lower()])
    
    return SkillResult.ok(
        data={"level": level},
        speak=f"Engagement set to {level}",
    )


@skill(
    name="list_skills",
    description="List all available skills",
    category=SkillCategory.DIGITAL,
    parameters=[
        SkillParameter("category", "string", "Filter by category (optional)", required=False),
    ],
    autonomy=AutonomyLevel.LEVEL_0,
    tags=["system", "help", "skills"],
)
async def list_skills(category: str | None = None) -> SkillResult:
    """List available skills."""
    from ..skills import get_skill_registry, SkillCategory
    
    registry = get_skill_registry()
    
    if category:
        try:
            cat = SkillCategory(category.lower())
            skills = registry.list_by_category(cat)
        except ValueError:
            return SkillResult.fail(f"Unknown category: {category}")
    else:
        skills = registry.list_all()
        
    skill_list = [
        {"name": s.name, "description": s.description, "category": s.category.value}
        for s in skills
    ]
    
    speak_text = f"I have {len(skills)} skills available. " + ", ".join(s.name for s in skills[:5])
    if len(skills) > 5:
        speak_text += f", and {len(skills) - 5} more"
        
    return SkillResult.ok(data={"skills": skill_list}, speak=speak_text)
