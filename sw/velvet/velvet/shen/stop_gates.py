"""
StopGateEngine: Kanban Completion Cage & Synthetic Turn Nudge for Velvet Nadir.

Prevents agents from hallucinating task completion or exiting active tasks
via plain-text conversational replies without explicit tool invocation
(task_complete or task_block).
"""

from typing import Any, Optional
from loguru import logger
from velvet.task_graph import TaskNode, TaskState


class StopGateEngine:
    """
    Enforces that workers with active in-progress tasks MUST invoke
    task_complete or task_block to exit the execution loop.
    """

    def __init__(self):
        pass

    def intercept_turn(
        self,
        response: Any,
        active_task: Optional[TaskNode] = None,
    ) -> tuple[bool, Optional[str]]:
        """
        Evaluate if the worker's turn attempt is valid.

        Returns:
            (intercepted: bool, synthetic_nudge: str | None)
            - If intercepted is True, the caller MUST suppress user delivery
              and reinject synthetic_nudge into the conversation context.
            - If intercepted is False, the turn proceeds normally.
        """
        if active_task is None:
            return (False, None)

        # Only enforce on tasks actively marked IN_PROGRESS
        if active_task.state != TaskState.IN_PROGRESS:
            return (False, None)

        has_tool_calls = False

        # Extract tool calls from various response types
        if hasattr(response, "tool_calls"):
            has_tool_calls = bool(response.tool_calls)
        elif isinstance(response, dict):
            has_tool_calls = bool(response.get("tool_calls"))
        elif isinstance(response, str):
            try:
                from velvet.tool_parsing import extract_tool_calls
                calls = extract_tool_calls(response)
                has_tool_calls = bool(calls and len(calls) > 0)
            except Exception:
                has_tool_calls = False

        if not has_tool_calls:
            # Intercept! Plain text response while task is IN_PROGRESS
            logger.warning(
                f"[StopGateEngine] Intercepted unauthorized plain-text exit on task {active_task.id} ('{active_task.name}')"
            )
            nudge = (
                f"[System Notice] You have an active task ('{active_task.name}' id={active_task.id}). "
                f"A plain-text reply is NOT completion. "
                f"Call task_complete(summary=..., artifacts=[...]) or task_block(reason=..., kind=...). "
                f"Do this NOW."
            )
            return (True, nudge)

        return (False, None)
