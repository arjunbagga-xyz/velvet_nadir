"""
Provider Phrase Banks for Velvet Nadir.

Matches provider-specific and non-standardized error strings across local engines
(vLLM, Ollama, llama.cpp) and cloud gateways (OpenRouter, Gemini, MiniMax, OpenAI).
"""

from typing import Any
from velvet.reliability.error_classifier import ErrorCategory


PROVIDER_PHRASE_BANK: dict[str, dict[str, Any]] = {
    # OpenRouter
    "credits_exhausted": {
        "category": ErrorCategory.AUTH_FAILURE,
        "hint": "OpenRouter account balance exhausted.",
        "retryable": False,
        "fallback": True,
    },
    "provider_data_policy": {
        "category": ErrorCategory.AUTH_FAILURE,
        "hint": "Model provider rejected prompt due to privacy/data policy.",
        "retryable": False,
        "fallback": True,
    },
    # vLLM / CUDA
    "cuda out of memory": {
        "category": ErrorCategory.NODE_OVERLOADED,
        "hint": "Local GPU VRAM exhausted.",
        "retryable": True,
        "fallback": True,
    },
    "context_length_exceeded": {
        "category": ErrorCategory.CONTEXT_OVERFLOW,
        "hint": "Prompt exceeded vLLM context window limits.",
        "retryable": True,
        "fallback": False,
    },
    "engine_dead": {
        "category": ErrorCategory.NODE_OVERLOADED,
        "hint": "Underlying vLLM inference engine crashed.",
        "retryable": True,
        "fallback": True,
    },
    "kv cache full": {
        "category": ErrorCategory.NODE_OVERLOADED,
        "hint": "vLLM PagedAttention KV cache exhausted.",
        "retryable": True,
        "fallback": True,
    },
    # Ollama
    "model not found": {
        "category": ErrorCategory.MODEL_NOT_FOUND,
        "hint": "Ollama model is not pulled on this node.",
        "retryable": False,
        "fallback": True,
    },
}


def match_provider_phrase(error_text: str) -> dict[str, Any] | None:
    """Check if the error text matches any known provider error phrases."""
    lower = error_text.lower()
    for phrase, metadata in PROVIDER_PHRASE_BANK.items():
        if phrase in lower:
            return metadata
    return None


PROVIDER_ERROR_PHRASES = PROVIDER_PHRASE_BANK

