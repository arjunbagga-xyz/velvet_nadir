"""
Argument Coercion Engine for Velvet Nadir.

Coerces LLM-emitted tool call arguments against target JSON schemas,
resolving common LLM type discrepancies (strings as numbers, booleans, or objects)
without dropping calls or losing data.
"""

import json
from typing import Any
from loguru import logger


def coerce_tool_arguments(args: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    """
    Cross-reference LLM-emitted arguments against the tool's JSON schema.
    Fix type mismatches non-destructively.
    """
    if not isinstance(args, dict):
        return args

    properties = schema.get("properties", {})
    coerced: dict[str, Any] = {}

    for key, value in args.items():
        expected = properties.get(key, {})
        expected_type = expected.get("type")

        if expected_type == "integer" and isinstance(value, str):
            coerced[key] = _coerce_number(value, integer_only=True)
        elif expected_type == "number" and isinstance(value, str):
            coerced[key] = _coerce_number(value, integer_only=False)
        elif expected_type == "boolean" and isinstance(value, str):
            coerced[key] = _coerce_boolean(value)
        elif expected_type == "array":
            coerced[key] = _coerce_array(value, expected.get("items", {}))
        elif expected_type == "object":
            coerced[key] = _coerce_object(value, expected)
        else:
            coerced[key] = value

    return coerced


def _coerce_number(value: str, integer_only: bool = False) -> int | float | str:
    """Coerce string to number. Preserves string on invalid or inf/nan numbers."""
    try:
        cleaned = value.strip().strip("'\"")
        n = float(cleaned)
        if n in (float("inf"), float("-inf")) or n != n:  # NaN check
            return value
        return int(n) if integer_only or n.is_integer() else n
    except (ValueError, TypeError):
        return value


def _coerce_boolean(value: str) -> bool | str:
    """Coerce string representation of boolean."""
    cleaned = value.strip().strip("'\"").lower()
    if cleaned in ("true", "1", "yes", "on", "y"):
        return True
    if cleaned in ("false", "0", "no", "off", "n"):
        return False
    return value


def _coerce_array(value: Any, items_schema: dict[str, Any]) -> list[Any] | Any:
    """Coerce JSON string or single scalar into array."""
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass
        # If comma-separated or scalar
        if "," in value and not value.startswith(("{", "[")):
            return [v.strip() for v in value.split(",")]
        return [value]
    return [value]


def _coerce_object(value: Any, schema: dict[str, Any]) -> dict[str, Any] | Any:
    """Coerce JSON string into object dictionary."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass
    return value
