"""
Mixed-Batch Tool Execution Dispatcher for Velvet Nadir.

Executes batches of tool calls emitted in a single turn with isolation.
If one tool call has malformed arguments or fails validation, valid tool calls
continue execution while only the malformed call produces an error response.
"""

import asyncio
from typing import Any, Callable, Coroutine
from loguru import logger

from velvet.reliability.arg_coercion import coerce_tool_arguments
from velvet.reliability.tool_repair import repair_truncated_tool_call


async def execute_tool_batch(
    tool_calls: list[dict[str, Any]],
    tool_handler: Callable[[str, dict[str, Any]], Coroutine[Any, Any, Any]],
    get_schema: Callable[[str], dict[str, Any] | None] | None = None,
) -> list[dict[str, Any]]:
    """
    Execute a batch of tool calls with per-call isolation and argument repair.
    Supports both OpenAI tool_call schema and direct {'tool': ..., 'params': ...} schema.
    """
    results: list[dict[str, Any]] = []

    for call in tool_calls:
        call_id = call.get("id", "") or call.get("call_id", "")
        function_info = call.get("function", {})
        func_name = (
            call.get("tool")
            or call.get("name")
            or function_info.get("name", "")
        )

        if not func_name:
            results.append({
                "tool_call_id": call_id,
                "name": "",
                "tool": "",
                "content": "Missing tool name in call specification",
                "error": "Missing tool name in call specification",
                "status": "error",
                "success": False,
            })
            continue

        raw_args = (
            call.get("params")
            or call.get("arguments")
            or function_info.get("arguments", {})
        )

        # 1. Parse / repair arguments if string
        if isinstance(raw_args, str):
            parsed_args = repair_truncated_tool_call(raw_args)
        elif isinstance(raw_args, dict):
            parsed_args = raw_args
        else:
            parsed_args = {}

        # 2. Coerce arguments against tool schema if available
        if get_schema and func_name:
            schema = get_schema(func_name)
            if schema:
                parsed_args = coerce_tool_arguments(parsed_args, schema)

        # 3. Execute with per-tool isolation & intent logging
        intent_id = None
        _intent_logger = None
        try:
            from velvet.reliability.intent_logger import IntentLogger
            _intent_logger = IntentLogger()
            intent_id = await _intent_logger.log_intent(func_name, parsed_args)
        except Exception:
            pass

        try:
            logger.debug(f"[BatchExecutor] Executing tool {func_name} with args {parsed_args}")
            output = await tool_handler(func_name, parsed_args)
            content_str = str(output) if not isinstance(output, str) else output
            if _intent_logger and intent_id:
                await _intent_logger.mark_completed(intent_id, output=content_str)
            results.append({
                "tool_call_id": call_id,
                "name": func_name,
                "tool": func_name,
                "content": content_str,
                "status": "success",
                "success": True,
                "error": None,
            })
        except Exception as e:
            logger.error(f"[BatchExecutor] Tool {func_name} failed in batch: {e}")
            if _intent_logger and intent_id:
                await _intent_logger.mark_failed(intent_id, error=str(e))
            results.append({
                "tool_call_id": call_id,
                "name": func_name,
                "tool": func_name,
                "content": f"Error executing {func_name}: {e}",
                "error": f"Tool execution failed: {e}",
                "status": "error",
                "success": False,
            })

    return results


execute_mixed_batch = execute_tool_batch
