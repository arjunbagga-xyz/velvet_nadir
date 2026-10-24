"""
Semantic Tool Disclosure & Pre-Injection for Velvet Nadir.

Computes semantic similarity between the user's prompt and registered tool descriptions
to pre-inject the top relevant tools (up to 12) plus core tools directly into the LLM context.
Eliminates Hermes-style multi-turn `tool_search` overhead while keeping context size bounded.
"""

import math
import re
from typing import Any, List
from loguru import logger

from velvet.skills.base import get_skill_registry, SkillRegistry, SkillDefinition

# Core tools that should always be present in context
CORE_TOOL_NAMES: set[str] = {
    "get_status",
    "task_complete",
    "task_block",
    "read_file",
}


class SemanticToolDisclosure:
    """
    Ranks available skills by relevance to the user's intent and provides
    the optimal subset of tool schemas for prompt pre-injection.
    """

    def __init__(self, registry: SkillRegistry | None = None, top_k: int = 12):
        self.registry = registry or get_skill_registry()
        self.top_k = top_k

    def get_preinjected_tools(self, user_prompt: str) -> list[dict[str, Any]]:
        """
        Return the top_k relevant tool schemas + all core tool schemas.
        """
        all_skills = self.registry.list_all()
        if not all_skills:
            return []

        # If total number of skills is <= top_k, return all
        if len(all_skills) <= self.top_k:
            return [s.to_tool_schema() for s in all_skills]

        scored_skills: list[tuple[float, SkillDefinition]] = []
        prompt_tokens = self._tokenize(user_prompt)

        for skill_defn in all_skills:
            # Core tools get maximum priority
            if skill_defn.name in CORE_TOOL_NAMES:
                scored_skills.append((100.0, skill_defn))
                continue

            # Compute term-overlap relevance score against name, description, tags
            text_corpus = f"{skill_defn.name} {skill_defn.description} {' '.join(skill_defn.tags)}"
            score = self._compute_relevance(prompt_tokens, text_corpus)
            scored_skills.append((score, skill_defn))

        # Sort descending by relevance score
        scored_skills.sort(key=lambda x: x[0], reverse=True)

        selected_definitions = [s for _, s in scored_skills[:self.top_k]]
        # Ensure any missing core tools are included
        selected_names = {s.name for s in selected_definitions}
        for _, s in scored_skills:
            if s.name in CORE_TOOL_NAMES and s.name not in selected_names:
                selected_definitions.append(s)

        logger.debug(
            f"[SemanticDisclosure] Pre-injected {len(selected_definitions)} tools for prompt: '{user_prompt[:40]}...'"
        )
        return [s.to_tool_schema() for s in selected_definitions]

    def _tokenize(self, text: str) -> set[str]:
        """Normalize and tokenize text into lowercase word set."""
        words = re.findall(r'[a-zA-Z0-9_\-]+', text.lower())
        return set(words)

    def _compute_relevance(self, query_tokens: set[str], doc_text: str) -> float:
        """Compute term frequency match score between query tokens and document."""
        doc_tokens = self._tokenize(doc_text)
        if not query_tokens or not doc_tokens:
            return 0.0

        matches = query_tokens.intersection(doc_tokens)
        if not matches:
            return 0.0

        # Term overlap ratio with word length weight
        score = sum(len(w) for w in matches) / (math.sqrt(len(doc_tokens)) + 1.0)
        return score
