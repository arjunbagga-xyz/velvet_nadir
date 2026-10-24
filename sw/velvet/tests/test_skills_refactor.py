import os
import pytest
import textwrap
from velvet.config import get_config
from velvet.skills import (
    SkillCategory,
    AutonomyLevel,
    SkillParameter,
    SkillDefinition,
    SkillResult,
    Skill,
    get_skill_registry,
    MarkdownSkill,
    load_markdown_skills,
    Armature,
)


class DummyConfigSkill(Skill):
    """A dummy skill declaring config dependencies."""
    
    @property
    def definition(self) -> SkillDefinition:
        return SkillDefinition(
            name="dummy_config_skill",
            description="A test skill requiring config",
            category=SkillCategory.SPECIALIST,
            requires_config=["llm.model", "device_id"]
        )

    async def execute(self, **params) -> SkillResult:
        return SkillResult.ok(data=params)


class TestArmaturePreprocessor:
    """Tests for parameter interpolation and config injection via Armature."""

    def test_config_injection(self):
        """Verify that Armature injects config values into params."""
        skill = DummyConfigSkill()
        params = {"input_val": "test"}
        
        processed = Armature.preprocess(skill, params)
        
        # Verify flat keys are injected
        assert "config_llm_model" in processed
        assert "config_device_id" in processed
        
        # Verify config dict is injected
        assert "config" in processed
        assert processed["config"]["llm.model"] == get_config().llm.model
        assert processed["config"]["device_id"] == get_config().device_id

    def test_env_var_interpolation(self, monkeypatch):
        """Verify that Armature interpolates {{env.VAR}} template variables."""
        monkeypatch.setenv("TEST_VARIABLE_KEY", "env_resolved_value")
        
        skill = DummyConfigSkill()
        params = {
            "normal_param": "hello",
            "templated_param": "Value is {{env.TEST_VARIABLE_KEY}}",
            "nested_list": ["item", "Key: {{env.TEST_VARIABLE_KEY}}"],
            "nested_dict": {"k": "{{env.TEST_VARIABLE_KEY}}"}
        }
        
        processed = Armature.preprocess(skill, params)
        
        assert processed["templated_param"] == "Value is env_resolved_value"
        assert processed["nested_list"][1] == "Key: env_resolved_value"
        assert processed["nested_dict"]["k"] == "env_resolved_value"

    def test_device_id_interpolation(self):
        """Verify that Armature interpolates {{device.id}} templates."""
        skill = DummyConfigSkill()
        params = {"msg": "Device: {{device.id}}"}
        
        processed = Armature.preprocess(skill, params)
        assert processed["msg"] == f"Device: {get_config().device_id}"


class TestMarkdownSkillLoading:
    """Tests for loading and executing instructional Markdown skills."""

    def test_parse_valid_markdown_skill(self, tmp_path):
        """Verify that frontmatter and instructions parse correctly from SKILL.md."""
        skill_dir = tmp_path / "test_markdown_skill"
        skill_dir.mkdir()
        md_file = skill_dir / "SKILL.md"
        
        md_content = textwrap.dedent("""\
            ---
            name: custom_md_skill
            description: "A custom Markdown skill definition"
            category: specialist
            autonomy: LEVEL_3
            tags: test, docs
            parameters: target:string:The recipient target, channel:string:Message route
            requires_config: llm.model
            ---
            # Procedures
            1. First, check targets.
            2. Run execution pipeline.
            """)
        md_file.write_text(md_content, encoding="utf-8")
        
        md_skill = MarkdownSkill(str(md_file))
        defn = md_skill.definition
        
        assert defn.name == "custom_md_skill"
        assert defn.description == "A custom Markdown skill definition"
        assert defn.category == SkillCategory.SPECIALIST
        assert defn.autonomy_required == AutonomyLevel.LEVEL_3
        assert "test" in defn.tags
        assert "docs" in defn.tags
        assert len(defn.parameters) == 2
        assert defn.parameters[0].name == "target"
        assert defn.parameters[0].param_type == "string"
        assert defn.parameters[1].name == "channel"
        assert defn.requires_config == ["llm.model"]

    @pytest.mark.asyncio
    async def test_execute_markdown_skill(self, tmp_path):
        """Verify that executing a Markdown skill returns the instructions body."""
        skill_dir = tmp_path / "test_markdown_skill"
        skill_dir.mkdir()
        md_file = skill_dir / "SKILL.md"
        
        md_content = textwrap.dedent("""\
            ---
            name: simple_md
            category: digital
            ---
            Hello World Instructions
            """)
        md_file.write_text(md_content, encoding="utf-8")
        
        md_skill = MarkdownSkill(str(md_file))
        result = await md_skill.execute()
        
        assert result.success
        assert "Hello World Instructions" in result.data
