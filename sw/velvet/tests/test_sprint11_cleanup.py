"""
Verification tests for Sprint 11 Cleanup and new features.
"""
import pytest
import json
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
from velvet.config import load_config, VelvetConfig
from velvet.devices import DeviceScript
from velvet.errors import VelvetError, VelvetAdapterError, LLMAdapterError
from velvet.services.llm_service import LLMProvider, PolymathAdapterWrapper
from velvet.shen.saraswati import Saraswati, GeneratedSkill, WorkflowCandidate
from velvet.shen.polymath import LlamaCppBackend

# 1. DeviceScript Sandbox Tests
def test_devicescript_sandbox_blocks_evil():
    """Verify that DeviceScript blocks banned calls and allows safe code."""
    ds = DeviceScript(action="test", script="result = 2 + 2")
    
    # Safe code
    ds.validate_script()
    res = ds.run_sandboxed()
    assert res["success"] is True
    assert res["result"] == 4
    
    # Evil code: import subprocess
    ds.script = "import subprocess\nresult = subprocess.run(['ls'])"
    ds.is_sandboxed = False 
    success, messages = ds.validate_script()
    assert success is False
    assert any("Banned import" in m for m in messages)
    
    # Evil code: eval()
    ds.script = "result = eval('1+1')"
    ds.is_sandboxed = False
    success, messages = ds.validate_script()
    assert success is False
    assert any("Banned call" in m for m in messages)

# 2. Error Hierarchy Tests
def test_error_hierarchy():
    """Verify that the new error hierarchy is correctly structured."""
    err = LLMAdapterError("test error")
    assert isinstance(err, VelvetAdapterError)
    assert isinstance(err, VelvetError)
    
    # Test catchability
    try:
        raise LLMAdapterError("oops")
    except VelvetAdapterError as e:
        assert str(e) == "oops"

# 3. TOML Config Tests
def test_toml_config_loading(tmp_path):
    """Verify that load_config reads from velvet.toml."""
    toml_path = tmp_path / "velvet.toml"
    toml_path.write_text(textwrap.dedent('''
        [velvet]
        device_id = "toml-device"
        [velvet.llm]
        adapter = "vllm"
    '''))
    
    # Injected config path
    cfg = load_config(config_path=toml_path)
    assert cfg.device_id == "toml-device"
    assert cfg.llm.adapter == "vllm"

def test_toml_env_priority(tmp_path, monkeypatch):
    """Verify that Env Vars still override TOML values."""
    toml_path = tmp_path / "velvet.toml"
    toml_path.write_text('device_id = "toml-device"')
    
    monkeypatch.setenv("VELVET_DEVICE_ID", "env-device")
    
    cfg = load_config(config_path=toml_path)
    assert cfg.device_id == "env-device"

# 4. Polymath/LLMService Integration Tests
@pytest.mark.asyncio
async def test_llmservice_polymath_integration():
    """Verify LLMService uses Polymath to load high-perf backends."""
    # Mock dependencies in the llm_service module namespace
    with patch("velvet.services.llm_service.get_fabric") as mock_get_fabric, \
         patch("velvet.services.llm_service.get_registry") as mock_get_reg, \
         patch("velvet.services.llm_service.Polymath") as mock_poly_cls:
        
        # Use AsyncMock for fabric because 'subscribe' and 'publish' are awaited
        mock_fabric = AsyncMock() 
        mock_get_fabric.return_value = mock_fabric
        
        # Registry get_device is sync in current implementation
        mock_reg = MagicMock()
        mock_get_reg.return_value = mock_reg
        
        mock_poly = mock_poly_cls.return_value
        mock_poly.inference_backend = "llama.cpp"
        
        # create_backend returns a backend which has an async 'generate'
        mock_backend = AsyncMock()
        mock_poly.create_backend.return_value = mock_backend
        
        provider = LLMProvider()
        
        # Mock config to 'auto'
        provider.config.llm.adapter = "auto"
        provider.config.llm.model = "test-model"
        
        await provider.start()
        
        assert isinstance(provider.backend, PolymathAdapterWrapper)
        assert provider.backend._backend == mock_backend
        mock_poly.create_backend.assert_called_once_with("test-model")
        mock_fabric.subscribe.assert_called_once()

# 5. Saraswati Pending Queue Tests
@pytest.mark.asyncio
async def test_saraswati_approval_queue(tmp_path):
    """Verify skills are queued for approval in JSON and fabric notified."""
    # Mock config to use tmp_path
    with patch("velvet.config.get_config") as mock_get_cfg:
        mock_cfg = MagicMock()
        mock_cfg.storage.data_dir = tmp_path
        mock_get_cfg.return_value = mock_cfg
        
        # Setup Saraswati
        saraswati = Saraswati(skills_dir=tmp_path / "skills")
        
        # Test skill
        skill = GeneratedSkill(
            name="test_skill",
            description="A test skill",
            code="result = 0"
        )
        
        # Mock fabric
        with patch("velvet.fabric.get_fabric") as mock_get_fabric:
            mock_fabric = AsyncMock()
            mock_get_fabric.return_value = mock_fabric
            
            await saraswati._queue_for_approval(skill)
            
            # Verify file exists
            pending_file = tmp_path / "pending_skills.json"
            assert pending_file.exists()
            data = json.loads(pending_file.read_text())
            assert "test_skill" in data
            assert data["test_skill"]["description"] == "A test skill"
            
            # Verify notification (two calls: TTS notification and pending approval topic)
            assert mock_fabric.publish.call_count == 2
            
            call_args_1 = mock_fabric.publish.call_args_list[0][0]
            assert call_args_1[0] == "velvet/mesh/notify"
            assert "test_skill" in call_args_1[1]["text"]

            call_args_2 = mock_fabric.publish.call_args_list[1][0]
            assert call_args_2[0] == "skill/pending_approval"
            assert call_args_2[1]["skill_name"] == "test_skill"

# 6. __all__ Export Tests
def test_all_exports():
    """Spot check some __all__ exports."""
    import velvet
    assert "VelvetConfig" in velvet.config.__all__
    assert "MessageType" in velvet.fabric.__all__
    assert "LLMAdapterError" in velvet.llm.__all__
