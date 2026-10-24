import pytest
from datetime import datetime, timezone
from velvet.config import get_config, load_config
from velvet.context import init_context_manager, TrackType, EngagementLevel
from velvet.skills import SkillResult
from velvet.llm import LLMAdapter, LLMResponse, get_llm_adapter


class MockLLMAdapter(LLMAdapter):
    """Mock LLM adapter to verify prompt outputs during compression."""
    
    def __init__(self):
        self.last_messages = None
        self.called_count = 0

    async def generate(self, messages, tools=None, max_tokens=1024, temperature=0.7):
        self.last_messages = messages
        self.called_count += 1
        return LLMResponse(text="Mocked Summary Response")

    async def stream(self, messages, max_tokens=1024, temperature=0.7):
        raise NotImplementedError()


@pytest.fixture
def mock_llm(monkeypatch):
    """Fixture to inject MockLLMAdapter into get_llm_adapter."""
    mock = MockLLMAdapter()
    monkeypatch.setattr("velvet.llm.get_llm_adapter", lambda: mock)
    return mock


@pytest.mark.asyncio
async def test_context_compression_trigger_below_threshold(mock_llm):
    """Verify that compression does NOT trigger if total chars is below the threshold."""
    ctx_mgr = init_context_manager()
    ctx_mgr.working_memory.conversation_buffer = []
    
    # 1. Add small messages (total ~100 chars)
    ctx_mgr.add_conversation_message("user", "Hello")
    ctx_mgr.add_conversation_message("assistant", "Hi there!")
    
    await ctx_mgr.compress_context_if_needed()
    
    # Verify no LLM call and conversation remains intact
    assert mock_llm.called_count == 0
    assert len(ctx_mgr.working_memory.conversation_buffer) == 2


@pytest.mark.asyncio
async def test_context_compression_local_raw_execution(mock_llm, monkeypatch):
    """Verify that local/mesh adapter compresses context raw (no Mirage scrambling)."""
    # Force adapter to be local
    monkeypatch.setattr(get_config().llm, "adapter", "ollama")
    monkeypatch.setattr(get_config().llm, "manager_context_length", 30)  # low context triggers compression early
    
    ctx_mgr = init_context_manager()
    ctx_mgr.working_memory.conversation_buffer = []
    
    # Add messages exceeding threshold (30 * 0.5 * 4 = 60 chars)
    ctx_mgr.add_conversation_message("user", "My name is Bob. I live at 123 Main St. I am working on project delta.")
    ctx_mgr.add_conversation_message("assistant", "Noted, Bob. Let's start the engine.")
    ctx_mgr.add_conversation_message("user", "Turn 1")
    ctx_mgr.add_conversation_message("assistant", "Response 1")
    ctx_mgr.add_conversation_message("user", "Turn 2")
    ctx_mgr.add_conversation_message("assistant", "Response 2")
    
    await ctx_mgr.compress_context_if_needed()
    
    assert mock_llm.called_count == 1
    # Check that the raw text (containing Bob) was sent directly to the local model
    sent_prompt = mock_llm.last_messages[1]["content"]
    assert "Bob" in sent_prompt
    assert "123 Main St" in sent_prompt


@pytest.mark.asyncio
async def test_context_compression_cloud_scrambled_execution(mock_llm, monkeypatch):
    """Verify that cloud adapter scrambles PII before transmission and rehydrates after."""
    # Force adapter to be cloud
    monkeypatch.setattr(get_config().llm, "adapter", "google")
    monkeypatch.setattr(get_config().security, "allow_cloud_adapters", True)
    monkeypatch.setattr(get_config().llm, "manager_context_length", 30)
    
    # Make sure PROJECT and BUSINESS tracks are paused so Mirage is allowed
    ctx_mgr = init_context_manager()
    ctx_mgr.working_memory.conversation_buffer = []
    await ctx_mgr.set_engagement(EngagementLevel.PAUSED, TrackType.PROJECT)
    await ctx_mgr.set_engagement(EngagementLevel.PAUSED, TrackType.BUSINESS)
    
    ctx_mgr.add_conversation_message("user", "My number is 555-123-4567. My email is bob@email.com.")
    ctx_mgr.add_conversation_message("assistant", "Noted.")
    ctx_mgr.add_conversation_message("user", "Turn 1")
    ctx_mgr.add_conversation_message("assistant", "Response 1")
    ctx_mgr.add_conversation_message("user", "Turn 2")
    ctx_mgr.add_conversation_message("assistant", "Response 2")
    
    # Mock LLM to return scrambled name so we can verify rehydration
    # If the mock returns the synthetic email/phone, it should be rehydrated back
    async def mock_generate(messages, tools=None, max_tokens=1024, temperature=0.7):
        mock_llm.called_count += 1
        mock_llm.last_messages = messages
        # Return summary containing synthetic email and phone format 555-101-1001
        return LLMResponse(text="Summary: User email is elena@example.com and phone is 555-101-1001.")
        
    mock_llm.generate = mock_generate
    
    await ctx_mgr.compress_context_if_needed()
    
    assert mock_llm.called_count == 1
    sent_prompt = mock_llm.last_messages[1]["content"]
    
    # Verify email and phone were scrambled in the sent prompt
    assert "bob@email.com" not in sent_prompt
    assert "555-123-4567" not in sent_prompt
    
    # Verify rehydration: Synthetic fields were rehydrated back in the saved buffer summary
    saved_summary = ctx_mgr.working_memory.conversation_buffer[0]["content"]
    assert "bob@email.com" in saved_summary
    assert "555-123-4567" in saved_summary
    assert "elena@example.com" not in saved_summary


@pytest.mark.asyncio
async def test_context_compression_cloud_blocked_fallback_truncation(mock_llm, monkeypatch):
    """Verify that cloud compression falls back to local truncation if Mirage is blocked."""
    # Force cloud
    monkeypatch.setattr(get_config().llm, "adapter", "google")
    monkeypatch.setattr(get_config().security, "allow_cloud_adapters", True)
    monkeypatch.setattr(get_config().llm, "manager_context_length", 30)
    
    ctx_mgr = init_context_manager()
    ctx_mgr.working_memory.conversation_buffer = []
    
    # Activate PROJECT track to block Mirage
    await ctx_mgr.set_engagement(EngagementLevel.ACTIVE, TrackType.PROJECT)
    
    ctx_mgr.add_conversation_message("user", "My name is Bob. Paths: /usr/local/bin.")
    ctx_mgr.add_conversation_message("assistant", "Noted.")
    ctx_mgr.add_conversation_message("user", "Turn 1")
    ctx_mgr.add_conversation_message("assistant", "Response 1")
    ctx_mgr.add_conversation_message("user", "Turn 2")
    ctx_mgr.add_conversation_message("assistant", "Response 2")
    
    await ctx_mgr.compress_context_if_needed()
    
    # Verify cloud LLM was NOT called due to Mirage block, and instead local truncation fallback ran
    assert mock_llm.called_count == 0
    saved_summary = ctx_mgr.working_memory.conversation_buffer[0]["content"]
    assert "[Older history truncated to preserve privacy]" in saved_summary
