"""
Phase 8 Integration Tests:
Tests Markdown skill bundles loading, Armature preprocessor ({var}/{{var}} & $(cmd)),
CUA Dual-Target GUI Engine (sandbox vs host), Limen MCP routing, and CredentialPool integration.
"""

import os
import pytest
import asyncio
from unittest.mock import MagicMock, patch

from velvet.config import get_config
from velvet.skills.markdown import load_markdown_skills, MarkdownSkill
from velvet.skills.armature import Armature
from velvet.skills.cua_skill import CUASandboxSkill
from velvet.skills.base import get_skill_registry, SkillResult
from velvet.credentials import get_credential_pool
from velvet.gateway import Gateway
from velvet.limen import get_limen_gateway
from velvet.context import init_context_manager


@pytest.mark.asyncio
async def test_markdown_skill_bundles_loading(tmp_path):
    """Test that load_markdown_skills recursively discovers .md files in bundles/ subdirectory."""
    bundles_dir = tmp_path / "bundles"
    bundles_dir.mkdir()
    
    test_skill_path = bundles_dir / "test_bundle.md"
    test_skill_path.write_text(
        "---\n"
        "name: test_bundle\n"
        "description: A test bundle skill.\n"
        "category: DevOps\n"
        "autonomy_required: LEVEL_2\n"
        "parameters: action:string:The action to perform\n"
        "---\n\n"
        "# Test Bundle Instructions\n"
        "Execute action: {action}\n",
        encoding="utf-8"
    )
    
    load_markdown_skills(str(tmp_path))
    registry = get_skill_registry()
    definitions = registry.list_all()
    assert len(definitions) >= 1
    
    bundle_def = next((d for d in definitions if d.name == "test_bundle"), None)
    assert bundle_def is not None
    assert bundle_def.description == "A test bundle skill."
    assert len(bundle_def.parameters) == 1
    assert bundle_def.parameters[0].name == "action"


def test_armature_variable_interpolation(monkeypatch):
    """Test Armature interpolation for {var} and {{var}} syntax against env and config."""
    monkeypatch.setenv("TEST_VELVET_ENV", "secret_value_123")
    cfg = get_config()
    
    # Test {env.VAR} and {{env.VAR}}
    res1 = Armature._interpolate_string("Token is {env.TEST_VELVET_ENV} and {{env.TEST_VELVET_ENV}}", cfg)
    assert res1 == "Token is secret_value_123 and secret_value_123"
    
    # Test {device.id} and {{device.id}}
    res2 = Armature._interpolate_string("Device: {device.id} vs {{device_id}}", cfg)
    assert cfg.device_id in res2
    
    # Test fallback without prefix
    res3 = Armature._interpolate_string("User is {user} and env is {TEST_VELVET_ENV}", cfg)
    assert "User is user and env is secret_value_123" == res3


def test_armature_inline_shell_evaluation():
    """Test $(command) inline shell evaluation with allow_host_exec toggle."""
    cfg = get_config()
    
    # 1. Test default (allow_host_exec = False -> sandboxed simulation/fallback)
    if isinstance(cfg.security, dict):
        cfg.security["allow_host_exec"] = False
    else:
        cfg.security.allow_host_exec = False
        
    res_sandbox = Armature._interpolate_string("Output: $(echo hello)", cfg)
    assert "Simulated output of: echo hello" in res_sandbox or "hello" in res_sandbox
    
    # 2. Test allow_host_exec = True
    if isinstance(cfg.security, dict):
        cfg.security["allow_host_exec"] = True
    else:
        cfg.security.allow_host_exec = True
        
    res_host = Armature._interpolate_string("Output: $(echo host_exec_success)", cfg)
    assert "host_exec_success" in res_host
    
    # Reset config
    if isinstance(cfg.security, dict):
        cfg.security["allow_host_exec"] = False
    else:
        cfg.security.allow_host_exec = False


@pytest.mark.asyncio
async def test_cua_dual_target_gui_engine():
    """Test CUASandboxSkill with target='sandbox' vs target='host' and allow_host_gui flag."""
    skill = CUASandboxSkill()
    cfg = get_config()
    
    # 1. Sandbox target (default)
    res_sandbox = await skill.execute({"action": "screenshot", "target": "sandbox"})
    assert res_sandbox.success is True
    assert "screenshot_base64" in res_sandbox.data or res_sandbox.data.get("status") == "success"
    
    # 2. Host target when allow_host_gui = False -> should fail with warning
    if isinstance(cfg.security, dict):
        cfg.security["allow_host_gui"] = False
    else:
        cfg.security.allow_host_gui = False
        
    res_host_disabled = await skill.execute({"action": "screenshot", "target": "host"})
    assert res_host_disabled.success is False
    assert "Host GUI execution is disabled" in res_host_disabled.error
    
    # 3. Host target when allow_host_gui = True -> should succeed
    if isinstance(cfg.security, dict):
        cfg.security["allow_host_gui"] = True
    else:
        cfg.security.allow_host_gui = True
        
    res_host_enabled = await skill.execute({"action": "execute_bash", "text": "echo test_host_bash", "target": "host"})
    assert res_host_enabled.success is True
    assert res_host_enabled.data.get("target") == "host"
    assert "test_host_bash" in str(res_host_enabled.data)
    
    # Reset config
    if isinstance(cfg.security, dict):
        cfg.security["allow_host_gui"] = False
    else:
        cfg.security.allow_host_gui = False


@pytest.mark.asyncio
async def test_limen_mcp_routing_in_gateway():
    """Test that Gateway routes external tool calls to LimenGateway when skill is not native."""
    init_context_manager()
    gw = Gateway()
    limen = get_limen_gateway()
    
    # Mock an external MCP tool schema and executor in Limen
    limen.mcp_tool_schemas = [
        {
            "type": "function",
            "function": {
                "name": "external_mcp_tool",
                "description": "An external tool via MCP",
                "parameters": {"type": "object", "properties": {"arg1": {"type": "string"}}}
            }
        }
    ]
    
    async def mock_mcp_exec(tool_name, arguments):
        if tool_name == "external_mcp_tool":
            return {"status": "ok", "result": f"Executed MCP with {arguments.get('arg1')}"}
        raise ValueError("Unknown tool")
        
    with patch.object(limen, "execute_mcp_tool", side_effect=mock_mcp_exec) as mock_exec:
        res = await gw.execute_skill("external_mcp_tool", {"arg1": "val1"})
        assert res.success is True
        assert res.data == {"status": "ok", "result": "Executed MCP with val1"}
        mock_exec.assert_called_once_with("external_mcp_tool", {"arg1": "val1"})


def test_credential_pool_integration():
    """Test CredentialPool key lookup and cooldown trigger."""
    pool = get_credential_pool()
    
    # Add a mock key using add_keys
    pool.add_keys("test_provider", ["key_alpha_1", "key_beta_2"])
    
    key1 = pool.get_api_key("test_provider")
    assert key1 in ("key_alpha_1", "key_beta_2")
    
    # Trigger cooldown on key1
    pool.trigger_cooldown("test_provider", key1)
    
    # Second get should retrieve the alternative key
    key2 = pool.get_api_key("test_provider")
    assert key2 != key1 and key2 in ("key_alpha_1", "key_beta_2")
