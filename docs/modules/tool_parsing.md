# Tool Parsing & Reliability (`tool_parsing.py`, `velvet.reliability`)

## Overview
Hardened extraction and parsing pipeline ensuring malformed or truncated model outputs do not crash agent turns.

## Capabilities
- **Truncated JSON Repair (`tool_repair.py`)**: Balances unclosed brackets/braces and closes unterminated strings.
- **Argument Coercion (`arg_coercion.py`)**: Auto-casts string booleans (`"true"` $\to$ `True`), numeric strings (`"42"` $\to$ `42`), and JSON-wrapped strings into target types.
- **7-Stage Error Classification (`error_classifier.py`)**: Categorizes exceptions into `TRANSIENT`, `RATE_LIMIT`, `CONTEXT_LENGTH`, `AUTH`, `NOT_FOUND`, `BAD_REQUEST`, or `FATAL`.
- **Pre-Execution Intent Logging (`intent_logger.py`)**: Distinguishes idempotent replays from side-effecting tools requiring human review.
