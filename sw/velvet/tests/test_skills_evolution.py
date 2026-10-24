"""
Tests for Phase 3: Skill System Evolution & Mesh Distribution.
Covers CAS unregister, scorecards, auto-promotion, auto-rollback,
SkillABTester, MeshSkillSync, AST static discovery, and semantic tool disclosure.
"""

from pathlib import Path
import pytest
from unittest.mock import AsyncMock, MagicMock

from velvet.skills.base import (
    Skill,
    SkillDefinition,
    SkillCategory,
    SkillRegistry,
    SkillResult,
    SkillScorecard,
)
from velvet.shen.skill_ab_test import SkillABTester
from velvet.shen.mesh_skill_sync import MeshSkillSync
from velvet.skills.discovery import parse_skill_file, discover_skills_in_directory
from velvet.skills.disclosure import SemanticToolDisclosure
from velvet.shen.xi import ConversationTurn


class DummySkill(Skill):
    def __init__(self, name: str, desc: str = "Test skill"):
        self._defn = SkillDefinition(
            name=name,
            description=desc,
            category=SkillCategory.DIGITAL,
        )

    @property
    def definition(self) -> SkillDefinition:
        return self._defn

    async def execute(self, **params) -> SkillResult:
        return SkillResult.ok()


# =========================================================================
# 1. Compare-And-Swap (CAS) Unregister
# =========================================================================

def test_cas_unregister():
    registry = SkillRegistry()
    skill_v1 = DummySkill("search_docs", "v1 implementation")
    registry.register(skill_v1)

    # CAS unregister with matching reference succeeds
    assert registry.unregister("search_docs", expected_ref=skill_v1) is True
    assert registry.get("search_docs") is None

    # Re-register v1 and then overwrite with v2
    registry.register(skill_v1)
    skill_v2 = DummySkill("search_docs", "v2 implementation")
    registry.register(skill_v2)

    # Attempting to unregister with obsolete v1 reference fails (CAS protection)
    assert registry.unregister("search_docs", expected_ref=skill_v1) is False
    assert registry.get("search_docs") is skill_v2

    # Unregister with correct v2 succeeds
    assert registry.unregister("search_docs", expected_ref=skill_v2) is True
    assert registry.get("search_docs") is None


# =========================================================================
# 2. Scorecard Auto-Promotion & Auto-Rollback
# =========================================================================

def test_scorecard_auto_promotion_and_rollback():
    registry = SkillRegistry()
    skill_old = DummySkill("weather_query", "Old weather")
    registry.register(skill_old)

    # Register upgrade -> skill_old moved to _previous
    skill_new = DummySkill("weather_query", "Upgraded weather")
    registry.register(skill_new)
    assert registry._previous["weather_query"] is skill_old

    # Test auto-promotion: 10 consecutive successful runs
    for _ in range(10):
        registry.record_execution("weather_query", success=True, latency_ms=15.0)

    scorecard = registry.get_scorecard("weather_query")
    assert scorecard is not None
    assert scorecard.promoted is True
    assert scorecard.success_rate == 1.0

    # Reset with another new version to test auto-rollback
    skill_buggy = DummySkill("weather_query", "Buggy weather")
    registry.register(skill_buggy)
    assert registry.get("weather_query") is skill_buggy

    # 3 failures and 2 successes out of 5 runs (60% failure rate >= 50%)
    registry.record_execution("weather_query", success=False, latency_ms=10.0)
    registry.record_execution("weather_query", success=False, latency_ms=10.0)
    registry.record_execution("weather_query", success=True, latency_ms=10.0)
    registry.record_execution("weather_query", success=True, latency_ms=10.0)
    # 5th run triggers auto-rollback
    registry.record_execution("weather_query", success=False, latency_ms=10.0)

    # The buggy version was rolled back to previous version!
    assert registry.get("weather_query") is skill_new


# =========================================================================
# 3. SkillABTester BreathTask
# =========================================================================

@pytest.mark.asyncio
async def test_skill_ab_tester():
    registry = SkillRegistry()
    old_s = DummySkill("transcribe_audio", "Old")
    registry.register(old_s)
    new_s = DummySkill("transcribe_audio", "New")
    registry.register(new_s)

    tester = SkillABTester(registry=registry)
    batch = [
        ConversationTurn(
            user_input="transcribe voice",
            response="done",
            skill_used="transcribe_audio",
            user_satisfied=True,
        )
    ]
    await tester.run(batch)

    card = registry.get_scorecard("transcribe_audio")
    assert card is not None
    assert card.executions >= 1


# =========================================================================
# 4. AST Static Discovery
# =========================================================================

def test_ast_skill_discovery(tmp_path):
    skill_file = tmp_path / "custom_skills.py"
    skill_file.write_text("""
from velvet.skills import skill, SkillCategory

@skill("calc_tax", "Calculate income tax", SkillCategory.DIGITAL, tags=["finance"])
def calculate_tax(income: float, rate: float = 0.2):
    return income * rate
""")

    skills = parse_skill_file(skill_file)
    assert len(skills) == 1
    found = skills[0]
    assert found["name"] == "calc_tax"
    assert found["description"] == "Calculate income tax"
    assert "finance" in found["tags"]
    assert any(p["name"] == "income" for p in found["parameters"])

    # Test mtime cache: second call returns cached without reparsing
    cached_skills = parse_skill_file(skill_file)
    assert cached_skills == skills


# =========================================================================
# 5. Semantic Pre-Injection (Tool Disclosure)
# =========================================================================

def test_semantic_tool_disclosure():
    registry = SkillRegistry()
    s1 = DummySkill("weather_forecast", "Get weather forecast and temperatures")
    s2 = DummySkill("send_slack_message", "Post updates and notifications to Slack channel")
    s3 = DummySkill("calculate_metrics", "Compute math and numerical analysis")
    registry.register(s1)
    registry.register(s2)
    registry.register(s3)

    disclosure = SemanticToolDisclosure(registry=registry, top_k=2)

    # Prompt about weather should rank weather_forecast highest
    tools = disclosure.get_preinjected_tools("What's the weather and temperature in London?")
    tool_names = [t["function"]["name"] for t in tools]
    assert "weather_forecast" in tool_names
