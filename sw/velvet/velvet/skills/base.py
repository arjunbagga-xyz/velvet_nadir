"""
Base classes and definitions for the Velvet Skill system.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable
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
    is_stateful_bind: bool = False


@dataclass
class SkillDefinition:
    """Metadata definition for a skill."""
    name: str
    description: str
    category: SkillCategory
    parameters: list[SkillParameter] = field(default_factory=list)
    autonomy_required: AutonomyLevel = AutonomyLevel.LEVEL_2
    tags: list[str] = field(default_factory=list)
    requires_config: list[str] = field(default_factory=list)
    
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


@dataclass
class SkillScorecard:
    """Performance metrics and promotion state for a registered skill."""
    executions: int = 0
    successes: int = 0
    failures: int = 0
    total_latency_ms: float = 0.0
    promoted: bool = False

    @property
    def success_rate(self) -> float:
        if self.executions == 0:
            return 1.0
        return self.successes / self.executions

    @property
    def failure_rate(self) -> float:
        if self.executions == 0:
            return 0.0
        return self.failures / self.executions

    @property
    def avg_latency_ms(self) -> float:
        if self.executions == 0:
            return 0.0
        return self.total_latency_ms / self.executions

    def record(self, success: bool, latency_ms: float = 0.0) -> None:
        self.executions += 1
        if success:
            self.successes += 1
        else:
            self.failures += 1
        self.total_latency_ms += latency_ms


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
        self._previous: dict[str, Skill] = {}
        self._versions: dict[str, str] = {}
        self._scores: dict[str, SkillScorecard] = {}
        self.skill_score: dict[str, float] = {}
        self._last_used: dict[str, float] = {}
        self._source_device: dict[str, str] = {}

    def unregister(self, name: str, expected_ref: Skill | SkillDefinition | None = None) -> bool:
        """
        Unregister a skill with optional Compare-And-Swap (CAS) reference checking.
        Prevents removing a skill if a newer version has already overwritten it.
        """
        if name not in self._skills:
            return False

        if expected_ref is not None:
            current = self._skills[name]
            if current is not expected_ref and getattr(current, "definition", None) is not expected_ref:
                logger.debug(f"[SkillRegistry] CAS unregister mismatch for '{name}'. Slot was updated; no-op.")
                return False

        skill = self._skills.pop(name)
        if name in self._versions:
            del self._versions[name]

        # Clean category indices
        defn = skill.definition
        if defn.category in self._by_category and name in self._by_category[defn.category]:
            self._by_category[defn.category].remove(name)

        logger.info(f"[SkillRegistry] Unregistered skill: {name}")
        return True

    def record_execution(self, name: str, success: bool, latency_ms: float = 0.0) -> None:
        """
        Record a skill execution outcome in its scorecard.
        Enforces auto-promotion (>90% success after 10+ runs)
        and auto-rollback (>=50% failures after 5+ runs).
        """
        import time
        if name not in self._scores:
            self._scores[name] = SkillScorecard()
        card = self._scores[name]
        card.record(success, latency_ms)

        self._last_used[name] = time.time()
        self.skill_score[name] = card.success_rate

        # Auto-Promotion: >= 10 runs with > 90% success rate
        if not card.promoted and card.executions >= 10 and card.success_rate > 0.90:
            card.promoted = True
            logger.info(f"[SkillRegistry] Skill {name} PROMOTED to permanent (10+ runs, {card.success_rate:.1%} success).")

        # Auto-Rollback: >= 5 runs with >= 50% failure rate
        if card.executions >= 5 and card.failure_rate >= 0.50:
            if name in self._previous:
                logger.warning(
                    f"[SkillRegistry] Auto-rollback triggered for {name} ({card.failure_rate:.1%} failure rate >= 50%)."
                )
                self.rollback_skill(name)
                self._scores[name] = SkillScorecard()

    def get_scorecard(self, name: str) -> SkillScorecard | None:
        """Get the execution scorecard for a skill."""
        return self._scores.get(name)
        
    def register(self, skill: Skill, previous_hash: str | None = None, source_device: str = "local") -> str:
        """Register a skill. Returns the version hash. Uses CAS if previous_hash is provided."""
        defn = skill.definition
        
        import hashlib
        import time
        version_hash = hashlib.sha256(f"{defn.name}-{time.time()}".encode()).hexdigest()
        
        if defn.name in self._skills:
            current_hash = self._versions.get(defn.name)
            if previous_hash is not None and previous_hash != current_hash:
                raise ValueError(f"CAS failure: provided previous_hash {previous_hash} does not match current {current_hash}")
            logger.warning(f"Skill {defn.name} already registered, overwriting")
            self._previous[defn.name] = self._skills[defn.name]
            
        self._skills[defn.name] = skill
        self._versions[defn.name] = version_hash
        self._source_device[defn.name] = source_device
        self._scores[defn.name] = SkillScorecard()
        if defn.name not in self.skill_score:
            self.skill_score[defn.name] = 0.0
            
        if defn.name not in self._by_category[defn.category]:
            self._by_category[defn.category].append(defn.name)
        
        for tag in defn.tags:
            if tag not in self._by_tag:
                self._by_tag[tag] = []
            if defn.name not in self._by_tag[tag]:
                self._by_tag[tag].append(defn.name)
            
        logger.info(f"Registered skill: {defn.name} ({defn.category.value})")
        return version_hash

    def rollback_skill(self, name: str) -> bool:
        """Restore the previous version of a skill if one exists."""
        if name in self._previous:
            old_skill = self._previous.pop(name)
            self._skills[name] = old_skill
            import hashlib
            import time
            new_hash = hashlib.sha256(f"{name}-rollback-{time.time()}".encode()).hexdigest()
            self._versions[name] = new_hash
            logger.info(f"Rolled back skill: {name}")
            return True
        return False

    def get_skill_status(self, name: str) -> dict | None:
        """Return version, score, source_device, last_used for a given skill."""
        if name not in self._skills:
            return None
        return {
            "version": self._versions.get(name),
            "score": self.skill_score.get(name, 0.0),
            "source_device": self._source_device.get(name, "local"),
            "last_used": self._last_used.get(name),
            "has_previous": name in self._previous
        }
        
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
