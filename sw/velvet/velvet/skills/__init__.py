"""
Skill system for Velvet Nadir.

Skills are modular capabilities that can be discovered and invoked by the Gateway.
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
    "MarkdownSkill",
    "load_markdown_skills",
    "Armature",
]

# Core definitions from base module
from .base import (
    SkillCategory,
    AutonomyLevel,
    SkillParameter,
    SkillDefinition,
    SkillResult,
    Skill,
    SkillRegistry,
    get_skill_registry,
    skill,
)

# Parsers & Preprocessors
from .markdown import MarkdownSkill, load_markdown_skills
from .armature import Armature
