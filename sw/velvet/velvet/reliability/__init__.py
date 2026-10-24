"""
Velvet Reliability & Defenses Package.
"""

from .error_classifier import ErrorClassifier, ErrorCategory, ClassifiedError, classify_error
from .arg_coercion import coerce_tool_arguments
from .tool_repair import repair_truncated_tool_call
from .sanitizer import sanitize_unicode, sanitize_api_key, sanitize_surrogates
from .phrases import PROVIDER_PHRASE_BANK, PROVIDER_ERROR_PHRASES, match_provider_phrase
from .stream_guards import (
    EmptyResponseError,
    RepetitionTrapError,
    ThinkingExhaustedError,
    strip_think_blocks,
    check_empty_response,
    check_thinking_budget_exhaustion,
    calculate_token_doubling,
    calculate_doubled_tokens,
    detect_sliding_window_repetition,
    detect_repetition,
    inject_interrupt_scaffold,
)
from .intent_logger import IntentLogger, IDEMPOTENT_TOOLS
from .batch_executor import execute_tool_batch, execute_mixed_batch

__all__ = [
    "ErrorClassifier",
    "ErrorCategory",
    "ClassifiedError",
    "classify_error",
    "coerce_tool_arguments",
    "repair_truncated_tool_call",
    "sanitize_unicode",
    "sanitize_api_key",
    "sanitize_surrogates",
    "PROVIDER_PHRASE_BANK",
    "PROVIDER_ERROR_PHRASES",
    "match_provider_phrase",
    "EmptyResponseError",
    "RepetitionTrapError",
    "ThinkingExhaustedError",
    "strip_think_blocks",
    "check_empty_response",
    "check_thinking_budget_exhaustion",
    "calculate_token_doubling",
    "calculate_doubled_tokens",
    "detect_sliding_window_repetition",
    "detect_repetition",
    "inject_interrupt_scaffold",
    "IntentLogger",
    "IDEMPOTENT_TOOLS",
    "execute_tool_batch",
    "execute_mixed_batch",
]
