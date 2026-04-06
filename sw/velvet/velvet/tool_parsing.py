"""
Tool call parsing for Velvet Nadir.

Extracts tool/function calls from LLM responses in multiple formats:
- Single JSON object: {"tool": "skill_name", "params": {...}}
- JSON array: [{"tool": "...", ...}, ...]
- Embedded in markdown code fences: ```json {"tool": ...} ```
- OpenAI-style: {"name": "...", "arguments": {...}}
"""

__all__ = [
    "extract_tool_calls",
    "find_json_objects",
    "is_tool_call",
    "extract_text_response",
]

import json
import re


def extract_tool_calls(response: str) -> list[dict]:
    """
    Extract tool calls from LLM response.

    Handles multiple formats that different LLMs produce.
    Returns a list of dicts, each with at least one of:
    "tool", "name", or "function" keys.
    """
    tool_calls: list[dict] = []

    # Try parsing entire response as JSON first
    try:
        data = json.loads(response.strip())
        if isinstance(data, list):
            return [d for d in data if is_tool_call(d)]
        elif is_tool_call(data):
            return [data]
    except json.JSONDecodeError:
        pass

    # Look for JSON blocks in markdown code fences
    json_blocks = re.findall(r'```(?:json)?\s*(\{[^`]+\})\s*```', response, re.DOTALL)
    for block in json_blocks:
        try:
            data = json.loads(block)
            if is_tool_call(data):
                tool_calls.append(data)
        except json.JSONDecodeError:
            pass

    if tool_calls:
        return tool_calls

    # Look for inline JSON objects with balanced braces
    for obj_str in find_json_objects(response):
        try:
            data = json.loads(obj_str)
            if is_tool_call(data):
                tool_calls.append(data)
        except json.JSONDecodeError:
            pass

    return tool_calls


def find_json_objects(text: str) -> list[str]:
    """Find JSON objects with balanced braces in text."""
    objects = []
    i = 0
    while i < len(text):
        if text[i] == '{':
            # Found start of JSON, find balanced end
            depth = 1
            start = i
            i += 1
            while i < len(text) and depth > 0:
                if text[i] == '{':
                    depth += 1
                elif text[i] == '}':
                    depth -= 1
                i += 1
            if depth == 0:
                obj_str = text[start:i]
                # Quick check if it might be a tool call
                if '"tool"' in obj_str or '"name"' in obj_str or '"function"' in obj_str:
                    objects.append(obj_str)
        else:
            i += 1
    return objects


def is_tool_call(data: dict) -> bool:
    """Check if a dict looks like a tool call."""
    if not isinstance(data, dict):
        return False
    return any(key in data for key in ("tool", "name", "function"))


def extract_text_response(response: str) -> str:
    """Extract plain text from response, removing tool call JSON."""
    # Remove JSON blocks
    text = re.sub(r'```(?:json)?\s*\{[^`]+\}\s*```', '', response)
    # Remove inline JSON that looks like tool calls
    text = re.sub(r'\{[^{}]*"(?:tool|name|function)"[^{}]*\}', '', text)
    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    return text
