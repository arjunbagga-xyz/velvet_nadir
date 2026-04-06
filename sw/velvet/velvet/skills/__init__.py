"""
Skill system for Velvet Nadir.

Skills are modular capabilities that can be discovered and invoked by the Gateway.
Inspired by Clawdbot's skill architecture but adapted for local, persistent operation.
"""

__all__ = [
    "SkillCategory",
    "AutonomyLevel",
    "SkillParameter",
    "SkillDefinition",
    "SkillResult",
    "Skill",
    "SkillRegistry",
    "get_skill_registry",
    "skill",
]

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable
import asyncio
from loguru import logger


class SkillCategory(Enum):
    """Categories of skills."""
    DIGITAL = "digital"       # Messaging, calendar, email, browser
    PERCEPTION = "perception" # Vision, audio, context analysis
    ROBOTICS = "robotics"     # Arm control, machinery, navigation
    SPECIALIST = "specialist" # Code, creative, research, domain-specific


class AutonomyLevel(Enum):
    """Autonomy levels for skill execution."""
    LEVEL_0 = 0  # Passive - observe only, never act
    LEVEL_1 = 1  # Informative - notify but don't act
    LEVEL_2 = 2  # Suggestive - propose actions, await approval (DEFAULT)
    LEVEL_3 = 3  # Autonomous - act within guardrails


@dataclass
class SkillParameter:
    """A parameter for a skill."""
    name: str
    param_type: str  # "string", "int", "float", "bool", "list", "dict"
    description: str
    required: bool = True
    default: Any = None


@dataclass
class SkillDefinition:
    """Metadata definition for a skill."""
    name: str
    description: str
    category: SkillCategory
    parameters: list[SkillParameter] = field(default_factory=list)
    autonomy_required: AutonomyLevel = AutonomyLevel.LEVEL_2
    tags: list[str] = field(default_factory=list)
    
    def to_tool_schema(self) -> dict:
        """Convert to OpenAI-style tool/function schema for LLM."""
        properties = {}
        required = []
        
        for param in self.parameters:
            prop_type = {
                "string": "string",
                "int": "integer",
                "float": "number",
                "bool": "boolean",
                "list": "array",
                "dict": "object",
            }.get(param.param_type, "string")
            
            properties[param.name] = {
                "type": prop_type,
                "description": param.description,
            }
            if param.required:
                required.append(param.name)
                
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }


@dataclass
class SkillResult:
    """Result of a skill execution."""
    success: bool
    data: Any = None
    error: str | None = None
    speak: str | None = None  # Optional TTS response
    display: dict | None = None  # Optional UI data
    
    @classmethod
    def ok(cls, data: Any = None, speak: str | None = None, display: dict | None = None):
        return cls(success=True, data=data, speak=speak, display=display)
    
    @classmethod
    def fail(cls, error: str):
        return cls(success=False, error=error)


class Skill(ABC):
    """
    Base class for all skills.
    
    Skills are discovered and registered with the SkillRegistry.
    The Gateway calls skills based on LLM routing decisions.
    """
    
    @property
    @abstractmethod
    def definition(self) -> SkillDefinition:
        """Return the skill's metadata definition."""
        pass
    
    @abstractmethod
    async def execute(self, **params) -> SkillResult:
        """Execute the skill with the given parameters."""
        pass
    
    async def validate_params(self, **params) -> tuple[bool, str | None]:
        """Validate parameters before execution. Override for custom validation."""
        for p in self.definition.parameters:
            if p.required and p.name not in params:
                return False, f"Missing required parameter: {p.name}"
        return True, None


class SkillRegistry:
    """
    Registry of all available skills.
    
    Skills register themselves here, and the Gateway queries the registry
    to find skills matching user intents.
    """
    
    def __init__(self):
        self._skills: dict[str, Skill] = {}
        self._by_category: dict[SkillCategory, list[str]] = {cat: [] for cat in SkillCategory}
        self._by_tag: dict[str, list[str]] = {}
        
    def register(self, skill: Skill) -> None:
        """Register a skill."""
        defn = skill.definition
        
        if defn.name in self._skills:
            logger.warning(f"Skill {defn.name} already registered, overwriting")
            
        self._skills[defn.name] = skill
        self._by_category[defn.category].append(defn.name)
        
        for tag in defn.tags:
            if tag not in self._by_tag:
                self._by_tag[tag] = []
            self._by_tag[tag].append(defn.name)
            
        logger.info(f"Registered skill: {defn.name} ({defn.category.value})")
        
    def get(self, name: str) -> Skill | None:
        """Get a skill by name."""
        return self._skills.get(name)
        
    def list_all(self) -> list[SkillDefinition]:
        """List all registered skill definitions."""
        return [s.definition for s in self._skills.values()]
        
    def list_by_category(self, category: SkillCategory) -> list[SkillDefinition]:
        """List skills in a category."""
        return [self._skills[name].definition for name in self._by_category.get(category, [])]
        
    def search(self, query: str) -> list[SkillDefinition]:
        """Search skills by name, description, or tags."""
        query = query.lower()
        results = []
        for skill in self._skills.values():
            defn = skill.definition
            if (query in defn.name.lower() or 
                query in defn.description.lower() or
                any(query in tag.lower() for tag in defn.tags)):
                results.append(defn)
        return results
        
    def get_tool_schemas(self, category: SkillCategory | None = None) -> list[dict]:
        """Get tool schemas for LLM function calling."""
        if category:
            skills = [self._skills[name] for name in self._by_category.get(category, [])]
        else:
            skills = list(self._skills.values())
        return [s.definition.to_tool_schema() for s in skills]


# Singleton registry
_registry: SkillRegistry | None = None


def get_skill_registry() -> SkillRegistry:
    """Get the global skill registry."""
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
    return _registry


def skill(
    name: str,
    description: str,
    category: SkillCategory,
    parameters: list[SkillParameter] | None = None,
    autonomy: AutonomyLevel = AutonomyLevel.LEVEL_2,
    tags: list[str] | None = None,
):
    """
    Decorator to register an async function as a skill.
    
    Usage:
        @skill(
            name="send_message",
            description="Send a message to a contact",
            category=SkillCategory.DIGITAL,
            parameters=[
                SkillParameter("recipient", "string", "Name or ID of recipient"),
                SkillParameter("message", "string", "Message content"),
            ],
            tags=["messaging", "communication"],
        )
        async def send_message(recipient: str, message: str) -> SkillResult:
            # Implementation
            return SkillResult.ok(speak="Message sent!")
    """
    def decorator(func: Callable[..., Awaitable[SkillResult]]):
        defn = SkillDefinition(
            name=name,
            description=description,
            category=category,
            parameters=parameters or [],
            autonomy_required=autonomy,
            tags=tags or [],
        )
        
        class FunctionSkill(Skill):
            @property
            def definition(self) -> SkillDefinition:
                return defn
                
            async def execute(self, **params) -> SkillResult:
                return await func(**params)
                
        # Register immediately
        get_skill_registry().register(FunctionSkill())
        
        return func
        
    return decorator
