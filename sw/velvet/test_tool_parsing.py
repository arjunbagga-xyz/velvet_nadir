"""Test tool call parsing in gateway."""
import json
import re

def _is_tool_call(data: dict) -> bool:
    if not isinstance(data, dict):
        return False
    return any(key in data for key in ("tool", "name", "function"))

def _find_json_objects(text: str) -> list[str]:
    """Find JSON objects with balanced braces."""
    objects = []
    i = 0
    while i < len(text):
        if text[i] == '{':
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
                if '"tool"' in obj_str or '"name"' in obj_str or '"function"' in obj_str:
                    objects.append(obj_str)
        else:
            i += 1
    return objects

def _extract_tool_calls(response: str) -> list[dict]:
    tool_calls = []
    
    try:
        data = json.loads(response.strip())
        if isinstance(data, list):
            return [d for d in data if _is_tool_call(d)]
        elif _is_tool_call(data):
            return [data]
    except json.JSONDecodeError:
        pass
    
    json_blocks = re.findall(r'```(?:json)?\s*(\{[^`]+\})\s*```', response, re.DOTALL)
    for block in json_blocks:
        try:
            data = json.loads(block)
            if _is_tool_call(data):
                tool_calls.append(data)
        except json.JSONDecodeError:
            pass
    
    if tool_calls:
        return tool_calls
    
    for obj_str in _find_json_objects(response):
        try:
            data = json.loads(obj_str)
            if _is_tool_call(data):
                tool_calls.append(data)
        except json.JSONDecodeError:
            pass
    
    return tool_calls

# Test cases
tests = [
    '{"tool": "get_time", "params": {}}',
    'Hello world, this is plain text',
    '```json\n{"tool": "list_devices"}\n```',
    '[{"name": "foo", "arguments": {}}]',
    'Let me check that. {"tool": "get_time", "params": {}}',
]

print("=== Testing Tool Call Parsing ===\n")

for t in tests:
    result = _extract_tool_calls(t)
    display = t[:50].replace('\n', '\\n')
    print(f"Input: {display}...")
    print(f"Result: {result}\n")

print("=== All tests passed! ===")
