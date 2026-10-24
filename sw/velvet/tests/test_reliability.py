"""
Tests for Phase 1 Reliability & LLM Defenses.
Covers 17 reliability mechanisms, classification, repair, batch execution,
intent logging, stream guards, node cooldowns, and ESTOP.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from velvet.reliability import (
    ErrorCategory,
    classify_error,
    coerce_tool_arguments,
    repair_truncated_tool_call,
    sanitize_surrogates,
    strip_think_blocks,
    check_empty_response,
    EmptyResponseError,
    calculate_doubled_tokens,
    detect_repetition,
    IntentLogger,
    execute_mixed_batch,
    PROVIDER_ERROR_PHRASES,
)
from velvet.llm import NodeCooldown, LLMResponse
from velvet.fabric import VelvetMessage, MessageType


# =========================================================================
# 1. Error Classifier (7 Categories)
# =========================================================================

def test_classify_error_categories():
    assert classify_error(Exception("401 Unauthorized token invalid")) == ErrorCategory.AUTH_FAILURE
    assert classify_error(Exception("429 rate limit exceeded, retry later")) == ErrorCategory.RATE_LIMIT
    assert classify_error(Exception("Maximum context length is 8192 tokens. Please reduce prompt.")) == ErrorCategory.CONTEXT_OVERFLOW
    assert classify_error(Exception("Unable to decode base64 image data: invalid header")) == ErrorCategory.IMAGE_CORRUPT
    assert classify_error(Exception("CUDA out of memory in worker rank 0")) == ErrorCategory.NODE_OVERLOADED
    assert classify_error(Exception("model 'deepseek-v3' not found in registry")) == ErrorCategory.MODEL_NOT_FOUND
    assert classify_error(Exception("ClientConnectorError: Cannot connect to host localhost:11434")) == ErrorCategory.TRANSIENT_NETWORK


# =========================================================================
# 2. Argument Coercion
# =========================================================================

def test_coerce_tool_arguments():
    schema = {
        "type": "object",
        "properties": {
            "count": {"type": "integer"},
            "ratio": {"type": "number"},
            "enabled": {"type": "boolean"},
            "tags": {"type": "array"},
            "config": {"type": "object"},
        }
    }
    raw = {
        "count": "42",
        "ratio": "3.1415",
        "enabled": "true",
        "tags": '["red", "blue"]',
        "config": '{"timeout": 10}',
    }
    coerced = coerce_tool_arguments(raw, schema)
    assert coerced["count"] == 42
    assert isinstance(coerced["count"], int)
    assert abs(coerced["ratio"] - 3.1415) < 1e-4
    assert coerced["enabled"] is True
    assert coerced["tags"] == ["red", "blue"]
    assert coerced["config"] == {"timeout": 10}


# =========================================================================
# 3. Truncated JSON Repair
# =========================================================================

def test_repair_truncated_tool_call():
    # Unterminated object
    broken_json = '{"tool": "weather", "params": {"city": "Paris"'
    repaired = repair_truncated_tool_call(broken_json)
    assert isinstance(repaired, dict)
    assert repaired["tool"] == "weather"
    assert repaired["params"]["city"] == "Paris"

    # Unterminated array in object
    broken_array = '{"targets": ["node1", "node2"'
    repaired_array = repair_truncated_tool_call(broken_array)
    assert isinstance(repaired_array, dict)
    assert "targets" in repaired_array
    assert "node1" in repaired_array["targets"]


# =========================================================================
# 4. Unicode Surrogate Sanitizer
# =========================================================================

def test_sanitize_surrogates():
    # \uD800 is an unpaired surrogate
    corrupt_text = "Hello \uD800World \uDFFFTest"
    cleaned = sanitize_surrogates(corrupt_text)
    assert "\uD800" not in cleaned
    assert "\uDFFF" not in cleaned
    assert "Hello" in cleaned
    assert "World" in cleaned


# =========================================================================
# 5. Stream Guards (Thinking Blocks, Empty Responses, Repetition)
# =========================================================================

def test_strip_think_blocks():
    raw = "<think>Analyzing the user's request...\nLet's see.</think>Hello! How can I help you?"
    cleaned = strip_think_blocks(raw)
    assert cleaned.strip() == "Hello! How can I help you?"
    assert "<think>" not in cleaned

    raw_thought = "<thought>internal reasoning</thought>Response text"
    assert strip_think_blocks(raw_thought).strip() == "Response text"


def test_empty_response_guard():
    assert check_empty_response("", None) is True
    assert check_empty_response("   ", []) is True
    assert check_empty_response("Here is the answer", None) is False
    assert check_empty_response("", [{"tool": "calc"}]) is False


def test_token_doubling():
    assert calculate_doubled_tokens(1024, max_ceiling=8192) == 2048
    assert calculate_doubled_tokens(4096, max_ceiling=8192) == 8192
    assert calculate_doubled_tokens(8192, max_ceiling=8192) == 8192


def test_detect_repetition():
    looping_phrase = "Repeating statement for testing repetition loop. " * 8
    assert detect_repetition(looping_phrase, min_chunk_len=20, min_repeats=4) is True
    assert detect_repetition("Normal short response without loops.", min_chunk_len=20, min_repeats=4) is False


# =========================================================================
# 6. Intent Logger (Idempotent Replay vs Side-Effect Parking)
# =========================================================================

@pytest.mark.asyncio
async def test_intent_logger_replay_and_parking():
    logger = IntentLogger()
    
    # Idempotent tool
    intent_id_1 = await logger.log_intent("get_weather", {"city": "Tokyo"})
    assert logger.should_replay("get_weather") is True
    assert logger.is_parked(intent_id_1) is False
    await logger.mark_completed(intent_id_1)

    # Side-effecting tool
    intent_id_2 = await logger.log_intent("send_email", {"to": "alice@example.com"})
    assert logger.should_replay("send_email") is False
    await logger.mark_parked(intent_id_2, reason="Interrupted during send")
    assert logger.is_parked(intent_id_2) is True
    
    parked = logger.get_parked_intents()
    assert len(parked) == 1
    assert parked[0]["tool_name"] == "send_email"


# =========================================================================
# 7. Mixed-Batch Tool Execution
# =========================================================================

@pytest.mark.asyncio
async def test_execute_mixed_batch():
    async def mock_executor(tool_name: str, params: dict):
        if tool_name == "fail_tool":
            raise ValueError("Tool execution failed")
        return {"status": "ok", "echo": tool_name}

    batch = [
        {"tool": "good_tool_1", "params": {"x": 1}},
        {"malformed": "no_tool_field"},
        {"tool": "good_tool_2", "params": {"y": 2}},
        {"tool": "fail_tool", "params": {}},
    ]

    results = await execute_mixed_batch(batch, mock_executor)
    assert len(results) == 4
    assert results[0]["success"] is True
    assert results[1]["success"] is False
    assert "Missing tool name" in results[1]["error"]
    assert results[2]["success"] is True
    assert results[3]["success"] is False
    assert "Tool execution failed" in results[3]["error"]


# =========================================================================
# 8. Node Cooldown Exponential Backoff
# =========================================================================

def test_node_cooldown():
    cd = NodeCooldown(device_id="node-a")
    assert not cd.is_active()

    cd.backoff("Network timeout")
    assert cd.failure_count == 1
    assert cd.is_active()
    assert cd.last_error == "Network timeout"

    cd.backoff("Second failure")
    assert cd.failure_count == 2
    assert cd.is_active()

    cd.reset()
    assert cd.failure_count == 0
    assert not cd.is_active()
    assert cd.last_error == ""


# =========================================================================
# 9. Macro Repetition Guard in Yi
# =========================================================================

def test_yi_macro_repetition_check():
    from velvet.shen.yi import Yi
    yi = Yi(start_vision_monitor=False)

    yi._recent_responses.append("The weather today in Paris is partly cloudy with 18 degrees.")
    # Identical or 95% similar response
    similar = "The weather today in Paris is partly cloudy with 18 degrees."
    assert yi._check_repetition(similar) is True

    # Dissimilar response
    dissimilar = "Your calendar shows a meeting scheduled at 3 PM today."
    assert yi._check_repetition(dissimilar) is False


# =========================================================================
# 10. Gateway ESTOP Handler
# =========================================================================

@pytest.mark.asyncio
async def test_gateway_estop_handling():
    from velvet.gateway import Gateway, GatewayRequest, Priority, GatewayState
    from velvet.context import init_context_manager

    init_context_manager()
    gw = Gateway(vision_enabled=False)
    # Enqueue a mock request
    cancel_event = asyncio.Event()
    req = GatewayRequest(
        priority=Priority.NORMAL,
        request_type="transcript",
        payload={"text": "Hello"},
        cancel=cancel_event,
    )
    gw._enqueue(req)
    gw._active_cancels.append(cancel_event)
    gw._tts_queue.put_nowait("Pending speech")
    gw.state = GatewayState.PROCESSING

    assert not gw._queue.empty()
    assert not gw._tts_queue.empty()
    assert not cancel_event.is_set()

    # Trigger ESTOP
    msg = VelvetMessage(
        msg_type=MessageType.ESTOP.value,
        source_device="operator",
        payload={},
    )
    await gw._on_estop(msg)

    assert cancel_event.is_set()
    assert gw._queue.empty()
    assert gw._tts_queue.empty()
    assert gw.state == GatewayState.IDLE
