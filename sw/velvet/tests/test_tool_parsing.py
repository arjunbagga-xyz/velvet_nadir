"""
Tests for LLM Tool Parsing logic.
"""

import pytest
import json
from velvet.tool_parsing import extract_tool_calls

# ============================================================================
# Tool Extraction Tests
# ============================================================================

def test_extract_single_tool():
    """Test extracting a single tool call from text."""
    text = 'I will turn on the lights.\nUse Tool: {"tool": "home_control", "params": {"action": "on", "device": "lights"}}'
    calls = extract_tool_calls(text)
    assert len(calls) == 1
    # Check flexible key naming (tool/name/function)
    assert calls[0].get("tool") == "home_control" or calls[0].get("name") == "home_control"
    
    params = calls[0].get("params") or calls[0].get("arguments")
    assert params["action"] == "on"

def test_extract_multiple_tools():
    """Test extracting multiple tool calls."""
    text = """
    First I'll check the weather.
    {"tool": "get_weather", "params": {"location": "London"}}
    Then I'll send a message.
    {"tool": "send_message", "params": {"to": "Mom", "text": "Hi"}}
    """
    calls = extract_tool_calls(text)
    assert len(calls) == 2
    assert calls[0]["tool"] == "get_weather"
    assert calls[1]["tool"] == "send_message"

def test_extract_json_markdown():
    """Test extracting tool call formatted as JSON markdown block."""
    text = """
    ```json
    {
        "tool": "search_web",
        "params": {
            "query": "velvet nadir"
        }
    }
    ```
    """
    calls = extract_tool_calls(text)
    assert len(calls) == 1
    assert calls[0]["tool"] == "search_web"
    assert calls[0]["params"]["query"] == "velvet nadir"

def test_extract_no_tools():
    """Test text with no tool calls."""
    text = "Just a normal conversation response."
    calls = extract_tool_calls(text)
    assert len(calls) == 0
