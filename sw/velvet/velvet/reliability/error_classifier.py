"""
7-Stage Error Classification Pipeline for Velvet Nadir.

Classifies raw provider exceptions and errors into structured ClassifiedError
instances with deterministic routing and recovery directives.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Any
import re


class ErrorCategory(str, Enum):
    AUTH_FAILURE = "auth_failure"
    RATE_LIMIT = "rate_limit"
    CONTEXT_OVERFLOW = "context_overflow"
    IMAGE_CORRUPT = "image_corrupt"
    NODE_OVERLOADED = "node_overloaded"
    MODEL_NOT_FOUND = "model_not_found"
    TRANSIENT_NETWORK = "transient_network"
    INTERNAL_PROVIDER_ERROR = "internal_provider_error"


@dataclass
class ClassifiedError:
    """Structured error containing recovery directives."""
    category: ErrorCategory
    retryable: bool
    should_fallback: bool
    should_compress: bool
    backoff_seconds: float
    user_message: str
    original_error: str


class ErrorClassifier:
    """Classifies exceptions from local and remote LLM providers."""

    # Stage regex patterns
    _AUTH_PATTERNS = [
        re.compile(r"auth(entication)?|unauthorized|401|403|api[ _]?key|forbidden", re.I),
    ]
    _RATE_LIMIT_PATTERNS = [
        re.compile(r"rate[ _]?limit|429|too many requests|quota|exceeded.*quota", re.I),
    ]
    _CONTEXT_PATTERNS = [
        re.compile(r"context[ _]?length|maximum context|token.*limit|reduce.*prompt|context_overflow|400.*tokens", re.I),
    ]
    _IMAGE_PATTERNS = [
        re.compile(r"image.*(corrupt|invalid|unsupported|decode)|vision.*error", re.I),
    ]
    _OVERLOAD_PATTERNS = [
        re.compile(r"overloaded|503|502|server.*busy|capacity|cuda.*out of memory|oom", re.I),
    ]
    _NOT_FOUND_PATTERNS = [
        re.compile(r"model.*not[ _]?found|404|unknown model|no such model", re.I),
    ]
    _NETWORK_PATTERNS = [
        re.compile(r"timeout|timed[ _]?out|connection|connect(or)?|refused|reset|network|dns|unreachable|socket", re.I),
    ]

    @classmethod
    def classify(cls, error: Exception | str) -> ClassifiedError:
        """Classify an exception or error string into a ClassifiedError."""
        err_str = str(error)

        # Stage 1: Auth Failure
        if any(p.search(err_str) for p in cls._AUTH_PATTERNS):
            return ClassifiedError(
                category=ErrorCategory.AUTH_FAILURE,
                retryable=False,
                should_fallback=True,
                should_compress=False,
                backoff_seconds=0.0,
                user_message="Provider authentication failed. Check credentials.",
                original_error=err_str,
            )

        # Stage 2: Rate Limit
        if any(p.search(err_str) for p in cls._RATE_LIMIT_PATTERNS):
            return ClassifiedError(
                category=ErrorCategory.RATE_LIMIT,
                retryable=True,
                should_fallback=True,
                should_compress=False,
                backoff_seconds=60.0,
                user_message="Rate limit hit on inference node. Cooling down.",
                original_error=err_str,
            )

        # Stage 3: Context Overflow
        if any(p.search(err_str) for p in cls._CONTEXT_PATTERNS):
            return ClassifiedError(
                category=ErrorCategory.CONTEXT_OVERFLOW,
                retryable=True,
                should_fallback=False,
                should_compress=True,
                backoff_seconds=0.0,
                user_message="Context limit reached. Compressing active working memory.",
                original_error=err_str,
            )

        # Stage 4: Image Corrupt
        if any(p.search(err_str) for p in cls._IMAGE_PATTERNS):
            return ClassifiedError(
                category=ErrorCategory.IMAGE_CORRUPT,
                retryable=False,
                should_fallback=False,
                should_compress=False,
                backoff_seconds=0.0,
                user_message="Attached media or image payload is corrupt or unreadable.",
                original_error=err_str,
            )

        # Stage 5: Node Overloaded
        if any(p.search(err_str) for p in cls._OVERLOAD_PATTERNS):
            return ClassifiedError(
                category=ErrorCategory.NODE_OVERLOADED,
                retryable=True,
                should_fallback=True,
                should_compress=False,
                backoff_seconds=15.0,
                user_message="Node is overloaded (OOM/capacity). Rerouting to peer.",
                original_error=err_str,
            )

        # Stage 6: Model Not Found
        if any(p.search(err_str) for p in cls._NOT_FOUND_PATTERNS):
            return ClassifiedError(
                category=ErrorCategory.MODEL_NOT_FOUND,
                retryable=False,
                should_fallback=True,
                should_compress=False,
                backoff_seconds=0.0,
                user_message="Requested model is not available on this node.",
                original_error=err_str,
            )

        # Stage 7: Transient Network
        if any(p.search(err_str) for p in cls._NETWORK_PATTERNS):
            return ClassifiedError(
                category=ErrorCategory.TRANSIENT_NETWORK,
                retryable=True,
                should_fallback=True,
                should_compress=False,
                backoff_seconds=2.0,
                user_message="Network timeout or disconnect. Retrying on next peer.",
                original_error=err_str,
            )

        # Default fallback: Internal Provider Error
        return ClassifiedError(
            category=ErrorCategory.INTERNAL_PROVIDER_ERROR,
            retryable=True,
            should_fallback=True,
            should_compress=False,
            backoff_seconds=5.0,
            user_message=f"Inference error: {err_str[:120]}",
            original_error=err_str,
        )


def classify_error(error: Exception | str) -> ErrorCategory:
    """Classify an exception or error string into an ErrorCategory enum."""
    return ErrorClassifier.classify(error).category

