import pytest
import warnings
from unittest.mock import MagicMock, AsyncMock, patch
from velvet.llm import LLMAdapterError, create_llm_adapter
from velvet.config import get_config, SecurityConfig

def test_deprecation_warning_allow_google_adapter():
    """Test that allow_google_adapter sets allow_cloud_adapters with a warning."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        
        cfg = SecurityConfig(allow_google_adapter=True)
        assert cfg.allow_cloud_adapters is True
        
        # Verify deprecation warning was emitted
        assert len(w) >= 1
        assert issubclass(w[-1].category, DeprecationWarning)
        assert "deprecated" in str(w[-1].message)

@pytest.mark.asyncio
async def test_universal_adapter_security_gate():
    """Test that UniversalCloudLLMAdapter blocks calls unless allow_cloud_adapters=True."""
    with patch("velvet.config.get_config") as mock_cfg:
        cfg = MagicMock()
        cfg.security.allow_cloud_adapters = False
        cfg.security.allow_google_adapter = False
        mock_cfg.return_value = cfg
        
        with pytest.raises(LLMAdapterError) as exc:
            create_llm_adapter("universal", provider="nvidia")
        assert "blocked by security policy" in str(exc.value)

@pytest.mark.asyncio
async def test_universal_adapter_nvidia_call():
    """Test standard OpenAI-compatible completions call for NVIDIA provider."""
    with patch("velvet.config.get_config") as mock_cfg:
        cfg = MagicMock()
        cfg.security.allow_cloud_adapters = True
        mock_cfg.return_value = cfg
        
        with patch.dict("os.environ", {"VELVET_LLM_NVIDIA_API_KEY": "test-nv-key"}):
            adapter = create_llm_adapter("universal", provider="nvidia", model="nv-model")
            assert adapter.provider == "nvidia"
            assert adapter.model == "nv-model"
            assert adapter.api_key == "test-nv-key"
            
            # Mock session post response
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.json = AsyncMock(return_value={
                "choices": [{
                    "message": {
                        "content": "Hello from NVIDIA",
                        "tool_calls": None
                    },
                    "finish_reason": "stop"
                }],
                "usage": {"total_tokens": 12}
            })
            
            mock_session = MagicMock()
            mock_session.post.return_value.__aenter__.return_value = mock_resp
            adapter._session = mock_session
            
            response = await adapter.generate([{"role": "user", "content": "hi"}])
            assert response.text == "Hello from NVIDIA"
            assert response.tokens_used == 12

@pytest.mark.asyncio
async def test_universal_adapter_google_delegation():
    """Test that google provider delegates to GoogleAIAdapter."""
    with patch("velvet.config.get_config") as mock_cfg:
        cfg = MagicMock()
        cfg.security.allow_cloud_adapters = True
        mock_cfg.return_value = cfg
        
        with patch("velvet.services.google_ai.GoogleAIAdapter") as mock_google:
            mock_inst = MagicMock()
            mock_google.return_value = mock_inst
            mock_inst.generate = AsyncMock(return_value="mock-response")
            
            with patch.dict("os.environ", {"VELVET_LLM_GOOGLE_API_KEY": "test-google-key"}):
                adapter = create_llm_adapter("universal", provider="google")
                assert adapter._delegate is not None
