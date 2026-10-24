"""
Markdown Skill Parser & Executor.

Supports loading instructional skills defined in SKILL.md format
containing YAML frontmatter and Markdown procedures.
"""

__all__ = [
    "MarkdownSkill",
    "load_markdown_skills",
]

import os
import re
from loguru import logger
from typing import Any
from .base import Skill, SkillDefinition, SkillCategory, SkillParameter, AutonomyLevel, SkillResult, get_skill_registry


class MarkdownSkill(Skill):
    """
    Skill defined in Markdown format (SKILL.md).
    
    Contains:
    - YAML Frontmatter (metadata: name, description, category, parameters)
    - Markdown body (L1 instructions for LLM injection)
    """

    def __init__(self, file_path: str):
        self.file_path = file_path
        self._definition = self._parse_file()

    @property
    def definition(self) -> SkillDefinition:
        return self._definition

    async def execute(self, **params) -> SkillResult:
        """
        Executing an instructional skill returns the parsed instruction text.
        Rendered via Armature for template & environment interpolation.
        """
        try:
            from velvet.config import get_config
            from velvet.skills.armature import Armature
            with open(self.file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Split frontmatter and markdown body
            parts = content.split("---")
            if len(parts) >= 3:
                body = "---".join(parts[2:]).strip()
            else:
                body = content.strip()
            
            rendered_body = Armature._interpolate_string(body, get_config())
            return SkillResult.ok(data=rendered_body, speak=f"Executing instructions for {self.definition.name}")
        except Exception as e:
            logger.error(f"[MarkdownSkill] Failed to execute {self.file_path}: {e}")
            return SkillResult.fail(str(e))

    def _parse_file(self) -> SkillDefinition:
        """Parse the SKILL.md frontmatter to construct a SkillDefinition."""
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Extract frontmatter
            parts = content.split("---")
            frontmatter_str = ""
            if len(parts) >= 3:
                frontmatter_str = parts[1].strip()
            
            # Simple key-value parser for basic YAML frontmatter
            metadata = {}
            for line in frontmatter_str.split("\n"):
                line = line.strip()
                if not line or line.startswith("#") or ":" not in line:
                    continue
                k, v = line.split(":", 1)
                metadata[k.strip()] = v.strip().strip('"').strip("'")
            
            # Parse parameters if specified as comma-separated or inline
            params = []
            param_str = metadata.get("parameters", "")
            if param_str:
                # Format: name:type:description, name2:type:description
                for p_item in param_str.split(","):
                    p_parts = p_item.strip().split(":")
                    if len(p_parts) >= 3:
                        params.append(SkillParameter(
                            name=p_parts[0].strip(),
                            param_type=p_parts[1].strip(),
                            description=p_parts[2].strip()
                        ))

            # Map category string to SkillCategory enum
            cat_str = metadata.get("category", "specialist").upper()
            try:
                category = SkillCategory[cat_str]
            except KeyError:
                category = SkillCategory.SPECIALIST

            # Map autonomy string to AutonomyLevel enum
            autonomy_str = metadata.get("autonomy", "LEVEL_2").upper()
            try:
                autonomy = AutonomyLevel[autonomy_str]
            except KeyError:
                autonomy = AutonomyLevel.LEVEL_2

            tags = [t.strip() for t in metadata.get("tags", "").split(",") if t.strip()]
            req_cfg = [c.strip() for c in metadata.get("requires_config", "").split(",") if c.strip()]

            fallback_name = os.path.splitext(os.path.basename(self.file_path))[0] if os.path.basename(self.file_path).upper() != "SKILL.MD" else os.path.basename(os.path.dirname(self.file_path))
            return SkillDefinition(
                name=metadata.get("name", fallback_name),
                description=metadata.get("description", "Instructional markdown skill"),
                category=category,
                parameters=params,
                autonomy_required=autonomy,
                tags=tags,
                requires_config=req_cfg
            )

        except Exception as e:
            logger.error(f"[MarkdownSkill] Error parsing frontmatter of {self.file_path}: {e}")
            # Fallback minimum definition
            fallback_name = os.path.splitext(os.path.basename(self.file_path))[0] if os.path.basename(self.file_path).upper() != "SKILL.MD" else os.path.basename(os.path.dirname(self.file_path))
            return SkillDefinition(
                name=fallback_name,
                description="Failed to parse metadata",
                category=SkillCategory.SPECIALIST
            )


def load_markdown_skills(directory_path: str) -> None:
    """Scan directory recursively for SKILL.md files and register them."""
    if not os.path.exists(directory_path):
        logger.warning(f"[MarkdownLoader] Directory does not exist: {directory_path}")
        return
        
    registry = get_skill_registry()
    count = 0
    
    for root, _, files in os.walk(directory_path):
        for file in files:
            if file.upper() == "SKILL.MD" or (os.path.basename(root).lower() == "bundles" and file.endswith(".md")):
                file_path = os.path.join(root, file)
                try:
                    md_skill = MarkdownSkill(file_path)
                    registry.register(md_skill)
                    count += 1
                except Exception as e:
                    logger.error(f"[MarkdownLoader] Failed to load {file_path}: {e}")
                    
    logger.info(f"[MarkdownLoader] Auto-discovered and registered {count} Markdown skill(s) from {directory_path}")
