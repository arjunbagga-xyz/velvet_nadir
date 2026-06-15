import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

from velvet.gateway import Gateway, AutonomyLevel, GatewayState, Priority, GatewayRequest
from velvet.context import ContextManager
from velvet.skills import skill, SkillCategory, SkillResult, get_skill_registry
from velvet.fabric import MessageType, VelvetMessage
from velvet.tool_parsing import extract_tool_calls


# ============================================================================
# Dummy Test Skills
# ============================================================================

@skill(
    name="dummy_skill",
    description="A simple skill for testing.",
    category=SkillCategory.SPECIALIST,
    tags=["test"]
)
async def dummy_skill(arg1: str) -> SkillResult:
    return SkillResult.ok(data={"arg1": arg1}, speak=f"Processed {arg1}")


# ============================================================================
# LLM Output Parsing Tests (Verifying Reality)
# ============================================================================

class TestLLMToolParsing:
    """Test extracting tool calls from realistic, raw LLM text responses."""

    def test_single_tool_call(self, realistic_llm_responses):
        text = realistic_llm_responses["single_tool"]
        calls = extract_tool_calls(text)
        assert len(calls) == 1
        assert calls[0].get("tool") == "get_time"

    def test_multiple_tool_calls(self, realistic_llm_responses):
        text = realistic_llm_responses["multi_tool"]
        calls = extract_tool_calls(text)
        assert len(calls) == 2
        assert calls[0].get("name") == "list_devices"
        assert calls[1].get("name") == "remember"
        assert calls[1].get("arguments")["key"] == "hobby"

    def test_markdown_json(self, realistic_llm_responses):
        text = realistic_llm_responses["markdown_json"]
        calls = extract_tool_calls(text)
        assert len(calls) == 1
        assert calls[0].get("tool") == "system_status"

    def test_malformed_json_returns_empty(self, realistic_llm_responses):
        text = realistic_llm_responses["malformed_json"]
        calls = extract_tool_calls(text)
        assert len(calls) == 0

    def test_plain_text(self, realistic_llm_responses):
        text = realistic_llm_responses["plain_text"]
        calls = extract_tool_calls(text)
        assert len(calls) == 0


# ============================================================================
# Gateway Orchestration and Dispatch Tests
# ============================================================================

class TestGatewayOrchestration:
    """Tests the Gateway priority queue and concurrent worker dispatch."""

    @pytest.mark.asyncio
    async def test_priority_queue_ordering(self, mock_fabric):
        """Gateway requests are ordered strictly by Priority value."""
        gw = Gateway(context_manager=ContextManager(), max_workers=0, vision_enabled=False)
        
        # Lower number = higher priority
        req_low = GatewayRequest(priority=Priority.LOW, request_type="transcript")
        req_high = GatewayRequest(priority=Priority.HIGH, request_type="wake")
        
        gw._enqueue(req_low)
        gw._enqueue(req_high)
        
        first = await gw._queue.get()
        second = await gw._queue.get()
        
        assert first.priority == Priority.HIGH
        assert second.priority == Priority.LOW

    @pytest.mark.asyncio
    async def test_gateway_skill_execution_flow(self, mock_fabric):
        """Test full flow: Fabric Request -> Gateway -> Skill -> Fabric Response."""
        # Setup Gateway
        mock_llm_func = AsyncMock(return_value="Plain conversational output.")
        gateway = Gateway(
            context_manager=ContextManager(),
            llm_inference=mock_llm_func,
            autonomy_level=AutonomyLevel.LEVEL_3,
            max_workers=1,
            vision_enabled=False
        )
        
        await gateway.start()
        try:
            # Subscribe a mock handler to listen for responses
            received_speak = []
            async def tts_handler(msg):
                received_speak.append(msg.payload["text"])
                # Instantly publish TTS_DONE so Gateway's _speak doesn't wait for 15s timeout
                await mock_fabric.publish(MessageType.TTS_DONE.value, {})
                
            await mock_fabric.subscribe(MessageType.TTS_SPEAK.value, tts_handler)
            
            # Publish incoming skill request through loopback fabric
            await mock_fabric.publish(
                MessageType.SKILL_REQUEST.value,
                {"skill": "dummy_skill", "params": {"arg1": "hello"}, "source": "test"}
            )
            
            # Wait for Loopback queue routing and worker processing
            await asyncio.sleep(0.3)
            
            # Gateway should have executed dummy_skill and spoken the result
            assert "Processed hello" in received_speak
        finally:
            await gateway.stop()


# ============================================================================
# Gateway Privacy Integration Tests (Sprint 17)
# ============================================================================

class TestGatewayPrivacy:
    """Tests for Gateway interaction with PrivacyClassifier and UniversalCloudLLMAdapter."""

    @pytest.mark.asyncio
    async def test_gateway_ingestion_classifies_input(self, mock_fabric):
        from velvet.gateway import Gateway
        from velvet.context import ContextManager
        from velvet.privacy import PrivacyLevel
        
        gw = Gateway(context_manager=ContextManager(), max_workers=0, vision_enabled=False)
        gw.yi = MagicMock()
        gw.yi.dispatch = AsyncMock(return_value="mock response")
        
        await gw._process_input("My SSN is 111-22-3333")
        assert gw.context.current_privacy_level == PrivacyLevel.SENSITIVE

    @pytest.mark.asyncio
    async def test_cloud_adapter_scrambles_personal_data(self):
        from velvet.services.universal_llm import UniversalCloudLLMAdapter
        from velvet.llm import LLMResponse
        
        mock_config = MagicMock()
        mock_config.security.allow_google_adapter = True
        
        with patch("velvet.config.get_config", return_value=mock_config), \
             patch("velvet.services.google_ai.GoogleAIAdapter") as MockGoogleAI:
            
            mock_google_inst = MagicMock()
            mock_google_inst.generate = AsyncMock(return_value=LLMResponse("I will call Dr. Elena Novak.", "stop"))
            MockGoogleAI.return_value = mock_google_inst
            
            adapter = UniversalCloudLLMAdapter(provider="google")
            
            messages = [{"role": "user", "content": "Call Dr. Amara Singh"}]
            response = await adapter.generate(messages)
            
            called_args = MockGoogleAI.return_value.generate.call_args[0][0]
            assert called_args[0]["content"] != "Call Dr. Amara Singh"
            
            assert "Dr. Amara Singh" in response.text

    @pytest.mark.asyncio
    async def test_cloud_adapter_rejects_restricted(self):
        from velvet.services.universal_llm import UniversalCloudLLMAdapter
        from velvet.privacy import PrivacyViolation
        
        mock_config = MagicMock()
        mock_config.security.allow_google_adapter = True
        
        with patch("velvet.config.get_config", return_value=mock_config), \
             patch("velvet.services.google_ai.GoogleAIAdapter"):
            adapter = UniversalCloudLLMAdapter(provider="google")
            messages = [{"role": "user", "content": "my password is supersecret"}]
            
            with pytest.raises(PrivacyViolation):
                await adapter.generate(messages)
