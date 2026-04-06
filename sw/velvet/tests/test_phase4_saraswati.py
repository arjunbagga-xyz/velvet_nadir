"""
Tests for Phase 4: Saraswati Skill Learning Pipeline.

Tests Vidya AST validation, Shruti parsing, Smriti code extraction,
and the end-to-end Saraswati BreathTask.
"""

import pytest
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

from velvet.shen.xi import ConversationTurn
from velvet.shen.saraswati import (
    Saraswati, Shruti, Smriti, Vidya,
    WorkflowCandidate, GeneratedSkill,
    BANNED_CALLS, BANNED_IMPORTS, ALLOWED_IMPORTS,
)


# ============================================================================
# Vidya (AST Validation) Tests
# ============================================================================

class TestVidya:
    """Test Vidya AST validation and deployment."""

    @pytest.fixture
    def vidya(self, tmp_path):
        return Vidya(skills_dir=tmp_path / "skills")

    def _make_skill(self, name: str, code: str) -> GeneratedSkill:
        return GeneratedSkill(name=name, code=code, description="test")

    def test_valid_skill_passes(self, vidya):
        """A clean skill using only allowed imports should pass."""
        code = textwrap.dedent('''
            from velvet.skills import skill, SkillCategory, SkillResult

            @skill(
                name="greet",
                description="Say hello",
                category=SkillCategory.DIGITAL,
            )
            async def greet(**params):
                return SkillResult.ok(speak="Hello!")
        ''').strip()

        is_safe, violations = vidya.validate(self._make_skill("greet", code))
        assert is_safe is True
        assert violations == []

    def test_banned_eval_rejected(self, vidya):
        """Code using eval() should be rejected."""
        code = 'result = eval("1+1")'
        is_safe, violations = vidya.validate(self._make_skill("bad", code))
        assert is_safe is False
        assert any("eval" in v for v in violations)

    def test_banned_exec_rejected(self, vidya):
        """Code using exec() should be rejected."""
        code = 'exec("import os")'
        is_safe, violations = vidya.validate(self._make_skill("bad", code))
        assert is_safe is False
        assert any("exec" in v for v in violations)

    def test_banned_subprocess_rejected(self, vidya):
        """Code importing subprocess should be rejected."""
        code = 'import subprocess\nsubprocess.run(["ls"])'
        is_safe, violations = vidya.validate(self._make_skill("bad", code))
        assert is_safe is False
        assert any("subprocess" in v for v in violations)

    def test_banned_requests_rejected(self, vidya):
        """Code importing requests should be rejected."""
        code = 'import requests\nrequests.get("http://evil.com")'
        is_safe, violations = vidya.validate(self._make_skill("bad", code))
        assert is_safe is False
        assert any("requests" in v for v in violations)

    def test_syntax_error_rejected(self, vidya):
        """Code with syntax errors should be rejected."""
        code = 'def foo(:\n    pass'
        is_safe, violations = vidya.validate(self._make_skill("bad", code))
        assert is_safe is False
        assert any("Syntax error" in v for v in violations)

    def test_allowed_stdlib_imports(self, vidya):
        """Allowed stdlib imports should pass."""
        code = textwrap.dedent('''
            import datetime
            import json
            import re
            from pathlib import Path
        ''').strip()
        is_safe, violations = vidya.validate(self._make_skill("ok", code))
        assert is_safe is True

    def test_banned_from_import(self, vidya):
        """from <banned> import ... should be rejected."""
        code = 'from urllib.request import urlopen'
        is_safe, violations = vidya.validate(self._make_skill("bad", code))
        assert is_safe is False

    def test_deploy_creates_file(self, vidya):
        """Deploy should create a .py file in skills dir."""
        code = textwrap.dedent('''
            from velvet.skills import skill, SkillCategory, SkillResult

            @skill(
                name="test_deploy",
                description="Test",
                category=SkillCategory.DIGITAL,
            )
            async def test_deploy(**params):
                return SkillResult.ok(speak="deployed!")
        ''').strip()

        skill = self._make_skill("test_deploy", code)
        result = vidya.deploy(skill)
        assert result is True
        file_path = vidya._skills_dir / "test_deploy.py"
        assert file_path.exists()
        assert "test_deploy" in file_path.read_text()

    def test_multiple_violations(self, vidya):
        """Code with multiple violations should report all of them."""
        code = textwrap.dedent('''
            import subprocess
            import requests
            result = eval("bad")
            exec("worse")
        ''').strip()
        is_safe, violations = vidya.validate(self._make_skill("bad", code))
        assert is_safe is False
        assert len(violations) >= 3


# ============================================================================
# Shruti (Pattern Parsing) Tests
# ============================================================================

class TestShruti:
    """Test Shruti pattern observation and parsing."""

    @pytest.fixture
    def shruti(self):
        return Shruti()

    def test_parse_valid_json(self, shruti):
        """Should parse valid JSON candidates."""
        response = '''[
            {
                "description": "Check the weather",
                "trigger_phrases": ["what's the weather", "weather report"],
                "steps": ["get location", "fetch weather API"],
                "skill_name": "check_weather",
                "frequency": 5,
                "confidence": 0.9
            }
        ]'''
        candidates = shruti._parse_candidates(response)
        assert len(candidates) == 1
        assert candidates[0].skill_name == "check_weather"
        assert candidates[0].frequency == 5

    def test_parse_markdown_wrapped(self, shruti):
        """Should handle LLM responses wrapped in markdown code blocks."""
        response = '```json\n[{"description": "test", "trigger_phrases": [], "steps": [], "skill_name": "test", "frequency": 1, "confidence": 0.5}]\n```'
        candidates = shruti._parse_candidates(response)
        assert len(candidates) == 1

    def test_parse_empty_array(self, shruti):
        """Empty array should return empty list."""
        candidates = shruti._parse_candidates("[]")
        assert candidates == []

    def test_parse_invalid_json(self, shruti):
        """Invalid JSON should return empty list."""
        candidates = shruti._parse_candidates("not json at all")
        assert candidates == []

    @pytest.mark.asyncio
    async def test_observe_small_batch_skipped(self, shruti):
        """Shruti should skip batches with fewer than 3 turns."""
        batch = [ConversationTurn(user_input="hi", response="hello")]
        candidates = await shruti.observe(batch)
        assert candidates == []


# ============================================================================
# Smriti (Code Extraction) Tests
# ============================================================================

class TestSmriti:
    """Test Smriti code generation and extraction."""

    @pytest.fixture
    def smriti(self):
        return Smriti()

    def test_extract_code_from_markdown(self, smriti):
        """Should extract Python code from markdown blocks."""
        response = '''Here is the code:

```python
from velvet.skills import skill, SkillCategory, SkillResult

@skill(name="test", description="Test", category=SkillCategory.DIGITAL)
async def test(**params):
    return SkillResult.ok()
```

That should work!'''
        code = smriti._extract_code(response)
        assert "@skill" in code
        assert "SkillResult" in code

    def test_extract_raw_code(self, smriti):
        """Should handle raw code without markdown wrapping."""
        response = 'from velvet.skills import skill\n\n@skill(name="raw")\nasync def raw():\n    pass'
        code = smriti._extract_code(response)
        assert "@skill" in code

    def test_extract_empty_response(self, smriti):
        """Empty response should return empty string."""
        code = smriti._extract_code("No code here, just text.")
        assert code == ""


# ============================================================================
# Saraswati (Orchestrator) Tests
# ============================================================================

class TestSaraswati:
    """Test Saraswati BreathTask orchestrator."""

    @pytest.fixture
    def saraswati(self, tmp_path):
        return Saraswati(skills_dir=tmp_path / "skills")

    def test_name(self, saraswati):
        assert saraswati.name() == "saraswati"

    def test_budget(self, saraswati):
        budget = saraswati.budget()
        assert budget.priority == 9
        assert budget.cpu_seconds == 5.0

    @pytest.mark.asyncio
    async def test_small_batch_skipped(self, saraswati):
        """Saraswati should skip batches smaller than 3 turns."""
        batch = [ConversationTurn(user_input="hi", response="hello")]
        await saraswati.run(batch)  # Should not crash

    @pytest.mark.asyncio
    async def test_full_pipeline_mocked(self, saraswati):
        """Test end-to-end pipeline with mocked Shruti and Smriti."""
        # Mock Shruti to return a candidate
        candidate = WorkflowCandidate(
            description="Check weather",
            trigger_phrases=["weather"],
            steps=["get weather"],
            skill_name="check_weather",
            frequency=5,
            confidence=0.9,
        )
        saraswati._shruti.observe = AsyncMock(return_value=[candidate])

        # Mock Smriti to return valid code
        valid_code = textwrap.dedent('''
            from velvet.skills import skill, SkillCategory, SkillResult

            @skill(
                name="check_weather",
                description="Check weather",
                category=SkillCategory.DIGITAL,
            )
            async def check_weather(**params):
                return SkillResult.ok(speak="Sunny!")
        ''').strip()

        skill = GeneratedSkill(
            name="check_weather",
            code=valid_code,
            description="Check weather",
        )
        saraswati._smriti.codify = AsyncMock(return_value=skill)

        batch = [
            ConversationTurn(user_input=f"q{i}", response=f"a{i}")
            for i in range(5)
        ]
        await saraswati.run(batch)

        # Should have attempted to codify the candidate
        saraswati._smriti.codify.assert_called_once()

        # Should have deployed the skill
        skill_file = saraswati._vidya._skills_dir / "check_weather.py"
        assert skill_file.exists()

    @pytest.mark.asyncio
    async def test_unsafe_skill_rejected(self, saraswati):
        """Pipeline should reject unsafe generated skills."""
        candidate = WorkflowCandidate(
            description="Hack stuff",
            trigger_phrases=["hack"],
            steps=["hack"],
            skill_name="hacker",
            frequency=5,
            confidence=0.9,
        )
        saraswati._shruti.observe = AsyncMock(return_value=[candidate])

        unsafe_code = 'import subprocess\nsubprocess.run(["rm", "-rf", "/"])'
        skill = GeneratedSkill(name="hacker", code=unsafe_code, description="bad")
        saraswati._smriti.codify = AsyncMock(return_value=skill)

        batch = [
            ConversationTurn(user_input=f"q{i}", response=f"a{i}")
            for i in range(5)
        ]
        await saraswati.run(batch)

        # Should NOT have deployed
        skill_file = saraswati._vidya._skills_dir / "hacker.py"
        assert not skill_file.exists()


# ============================================================================
# Constants Tests
# ============================================================================

class TestSafetyConstants:
    """Test that safety constants are properly defined."""

    def test_banned_calls_complete(self):
        assert "eval" in BANNED_CALLS
        assert "exec" in BANNED_CALLS
        assert "__import__" in BANNED_CALLS

    def test_banned_imports_complete(self):
        assert "subprocess" in BANNED_IMPORTS
        assert "requests" in BANNED_IMPORTS
        assert "socket" in BANNED_IMPORTS

    def test_allowed_imports_include_velvet(self):
        assert "velvet.skills" in ALLOWED_IMPORTS
        assert "datetime" in ALLOWED_IMPORTS
        assert "json" in ALLOWED_IMPORTS
