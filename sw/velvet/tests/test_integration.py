"""
System Integration Tests.
"""

import pytest
import asyncio
from velvet.gateway import Gateway, AutonomyLevel
from velvet.context import ContextManager
from velvet.skills import skill, SkillCategory, SkillResult
from velvet.fabric import MessageType

# ============================================================================
# Test Skills
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
# Integration Tests
# ============================================================================

@pytest.mark.asyncio
async def test_gateway_skill_execution(mock_fabric, mock_llm):
    """Test full flow: Fabric Request -> Gateway -> Skill -> Fabric Response."""
    
    # Setup Gateway
    gateway = Gateway(
        context_manager=ContextManager(),
        llm_inference=mock_llm.generate,
        autonomy_level=AutonomyLevel.LEVEL_3,
        max_workers=1
    )
    
    # We need to manually wire the gateway to the mock fabric for this test
    # since we are not using start_velvet()
    # But Gateway uses get_fabric() internally which uses the singleton.
    # The 'mock_fabric' fixture might needed to be installed as the global singleton.
    
    # Hack: Install mock fabric as global singleton for this test
    import velvet.fabric
    original_fabric = velvet.fabric._fabric
    velvet.fabric._fabric = mock_fabric
    
    try:
        await gateway.start()
        
        # Simulate an incoming skill request
        # Gateway subscribes to SKILL_REQUEST
        # We find the handler and call it
        
        # 1. Verify Gateway subscribed
        mock_fabric.subscribe.assert_called()
        
        # Find the handler for SKILL_REQUEST
        skill_handler = None
        for call in mock_fabric.subscribe.call_args_list:
            if call[0][0] == MessageType.SKILL_REQUEST.value:
                skill_handler = call[0][1]
                break
        
        assert skill_handler is not None
        
        # 2. Simulate message
        msg_payload = {"skill": "dummy_skill", "params": {"arg1": "hello"}, "source": "test"}
        msg = type('obj', (object,), {
            "payload": msg_payload, 
            "msg_type": MessageType.SKILL_REQUEST.value,
            "source_device": "test_src"
        })
        
        # 3. Inject message
        await skill_handler(msg)
        
        # 4. Wait for processing (Gateway puts it in queue)
        await asyncio.sleep(0.1)
        
        # 5. Verify Response (TTS)
        # Gateway should publish TTS_SPEAK since skill returned 'speak'
        mock_fabric.publish.assert_called()
        
        # Find the TTS message
        tts_found = False
        for call in mock_fabric.publish.call_args_list:
            if call[0][0] == MessageType.TTS_SPEAK.value:
                payload = call[0][1]
                if payload["text"] == "Processed hello":
                    tts_found = True
                    break
        
        assert tts_found
        
    finally:
        await gateway.stop()
        velvet.fabric._fabric = original_fabric
