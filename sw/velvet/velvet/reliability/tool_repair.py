"""
Tool Call Corruption Repair for Velvet Nadir.

Salvages truncated or malformed JSON payloads from streaming or context-limited
LLM output without dropping valid tool call intentions.
"""

import json
import re
from typing import Any
from loguru import logger


_TRAILING_COMMA_FIX = re.compile(r',\s*([\]\}])')
_OPEN_KEY_FIX = re.compile(r',\s*"[^"]*":?\s*$')


def repair_truncated_tool_call(raw_json: str) -> dict[str, Any] | None:
    """
    Attempt to salvage a truncated or corrupted JSON tool call arguments string.

    Strategies:
    1. Direct json.loads
    2. Strip open trailing keys or commas
    3. Balance unclosed brackets and braces
    4. Fall back to empty dict if unparseable
    """
    if not raw_json or not raw_json.strip():
        return {}

    cleaned = raw_json.strip()

    # Strategy 1: Direct parse
    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        pass

    # Strategy 2: Remove dangling incomplete keys (e.g., '{"a": 1, "b":')
    trimmed = _OPEN_KEY_FIX.sub("", cleaned)
    # Remove trailing commas
    trimmed = re.sub(r',\s*$', '', trimmed)

    # Strategy 3: Balance braces and brackets
    open_braces = trimmed.count('{') - trimmed.count('}')
    open_brackets = trimmed.count('[') - trimmed.count(']')

    # Only attempt if we actually have unclosed structures
    if open_braces > 0 or open_brackets > 0:
        repaired = trimmed + (']' * max(0, open_brackets)) + ('}' * max(0, open_braces))
        repaired = _TRAILING_COMMA_FIX.sub(r'\1', repaired)
        try:
            parsed = json.loads(repaired)
            if isinstance(parsed, dict):
                logger.debug(f"[ToolRepair] Successfully repaired truncated JSON: {cleaned} -> {repaired}")
                return parsed
        except json.JSONDecodeError:
            pass

    # Strategy 4: Fallback to empty arguments rather than dropping the call entirely
    logger.warning(f"[ToolRepair] Could not parse tool arguments; defaulting to empty dict. Raw: {cleaned[:100]}")
    return {}
