import pytest
import asyncio
from velvet.config import get_config
from velvet.credentials import CredentialPool, get_credential_pool
from velvet.skills.cua_skill import CUASandboxSkill
from velvet.skills.base import get_skill_registry


@pytest.fixture
def pool():
    return CredentialPool()


def test_credential_rotation_and_cooldown(pool):
    """Verify that credentials rotate, and keys in cooldown are skipped."""
    keys = ["key_alpha", "key_beta", "key_gamma"]
    pool.add_keys("google", keys)
    
    # 1. Fetching keys repeatedly should rotate them
    assert pool.get_api_key("google") == "key_alpha"
    assert pool.get_api_key("google") == "key_beta"
    assert pool.get_api_key("google") == "key_gamma"
    assert pool.get_api_key("google") == "key_alpha"  # wraps around

    # 2. Put key_beta on cooldown
    pool.trigger_cooldown("google", "key_beta")
    
    # Next fetches should skip key_beta
    assert pool.get_api_key("google") == "key_gamma"
    assert pool.get_api_key("google") == "key_alpha"
    assert pool.get_api_key("google") == "key_gamma"  # key_beta skipped, wraps back to gamma


def test_local_model_fallback_adaptation(pool, monkeypatch):
    """Verify fallback updates adapter config and prunes context window limits."""
    # Mock config values
    monkeypatch.setattr(get_config().llm, "adapter", "google")
    monkeypatch.setattr(get_config().llm, "manager_context_length", 8192)
    
    pool.adapt_to_local_fallback()
    
    # Assert config transitioned to local Ollama and pruned context length to prevent VRAM overflow
    assert get_config().llm.adapter == "ollama"
    assert get_config().llm.manager_context_length == 2048


@pytest.mark.asyncio
async def test_cua_skill_execution():
    """Verify CUA sandbox skill executes OS actions and falls back to simulation."""
    skill = CUASandboxSkill()
    
    # Test screenshot simulation
    res_screenshot = await skill.execute({"action": "screenshot"})
    assert res_screenshot.success
    assert "screenshot_base64" in res_screenshot.data
    assert "[Simulation]" in res_screenshot.speak

    # Test execute_bash simulation
    res_bash = await skill.execute({"action": "execute_bash", "text": "echo hello"})
    assert res_bash.success
    assert res_bash.data["stdout"] == "Simulated output of: echo hello"
    
    # Verify skill registration in global registry
    registry = get_skill_registry()
    assert any(defn.name == "cua_sandbox" for defn in registry.list_all())
    
    await skill.cleanup()
