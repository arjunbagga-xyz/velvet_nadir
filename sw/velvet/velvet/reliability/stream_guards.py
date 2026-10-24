"""
Stream and Token Guards for Velvet Nadir.

Provides real-time monitors for empty responses, thinking-block scrubbing,
token doubling on truncation, thinking-budget exhaustion, sliding-window repetition,
and interrupt scaffolding.
"""

import re
from typing import Any
from loguru import logger


class EmptyResponseError(Exception):
    """Raised when an inference adapter returns an empty payload."""
    pass


class RepetitionTrapError(Exception):
    """Raised when model enters an infinite repetitive generation loop."""
    pass


class ThinkingExhaustedError(Exception):
    """Raised when model consumes 100% of tokens in thinking tags without terminal output."""
    pass


def strip_think_blocks(text: str) -> str:
    """
    Remove <think>, <reasoning>, and <thought> blocks from text.
    Handles orphan trailing opening tags from interrupted streams.
    """
    if not text:
        return ""
    # Strip complete closed blocks
    cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r'<reasoning>.*?</reasoning>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r'<thought>.*?</thought>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)

    # Strip orphan unclosed blocks
    cleaned = re.sub(r'<think>.*$', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r'<reasoning>.*$', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r'<thought>.*$', '', cleaned, flags=re.DOTALL | re.IGNORECASE)

    return cleaned.strip()


def check_empty_response(text: str, tool_calls: list[Any] | None = None, raise_error: bool = False) -> bool:
    """
    Validate whether the model emitted an empty response (no text and no tool calls).
    Returns True if empty, False if response has content. If raise_error is True, raises EmptyResponseError.
    """
    has_text = bool(text and text.strip())
    has_tools = bool(tool_calls and len(tool_calls) > 0)
    is_empty = not has_text and not has_tools
    if is_empty and raise_error:
        raise EmptyResponseError("LLM emitted empty response with zero tool calls.")
    return is_empty


def check_thinking_budget_exhaustion(raw_text: str, finish_reason: str) -> bool:
    """
    Returns True if model exhausted token budget inside thinking tags
    without producing user-facing output.
    """
    if "<think>" in raw_text.lower() and finish_reason == "length":
        cleaned = strip_think_blocks(raw_text)
        if not cleaned.strip():
            logger.warning("[StreamGuards] Thinking budget exhausted without final response.")
            return True
    return False


def calculate_doubled_tokens(current_max_tokens: int, max_ceiling: int = 32768) -> int:
    """Double token budget exponentially up to max_ceiling."""
    doubled = current_max_tokens * 2
    return min(doubled, max_ceiling)


calculate_token_doubling = calculate_doubled_tokens


def detect_repetition(
    text: str,
    min_chunk_len: int = 400,
    min_repeats: int = 5,
) -> bool:
    """
    Detects if any text fragment of length >= min_chunk_len
    repeats >= min_repeats times in the output.
    """
    if len(text) < min_chunk_len * 2:
        return False

    tail = text[-2000:] if len(text) > 2000 else text

    for start in range(len(tail) - min_chunk_len):
        fragment = tail[start:start + min_chunk_len]
        count = tail.count(fragment)
        if count >= min_repeats:
            logger.error(f"[StreamGuards] Repetition trap detected: {count}x repetition of {min_chunk_len}b fragment.")
            return True

    return False


detect_sliding_window_repetition = detect_repetition



def inject_interrupt_scaffold(messages: list[dict[str, Any]], turn_index: int = 0) -> list[dict[str, Any]]:
    """
    Injects a clean synthetic closing scaffold into messages when
    an in-flight generation is aborted mid-stream.
    """
    scaffold = {
        "role": "assistant",
        "content": f"[Interrupted by operator at turn {turn_index}]",
    }
    return list(messages) + [scaffold]
