"""
Pre-Execution Intent Logger for Velvet Nadir.

Logs tool invocation intents to memory/Jing BEFORE execution begins.
Upon recovery from a process crash or interruption, determines whether
uncompleted operations can be safely replayed (idempotent) or must be
parked for human operator review (side-effecting).
"""

import uuid
from datetime import datetime, timezone
from typing import Any
from loguru import logger


# Tools known to be strictly read-only and safe to replay automatically
IDEMPOTENT_TOOLS: set[str] = {
    "read_file",
    "view_file",
    "search_code",
    "get_status",
    "check_health",
    "list_dir",
    "get_temperature",
    "get_weather",
    "graph_query",
    "recall_memory",
}


class IntentLogger:
    """Tracks tool invocation lifecycle for crash resilience."""

    def __init__(self, memory_backend: Any = None):
        self._memory = memory_backend
        self._active_intents: dict[str, dict[str, Any]] = {}

    def should_replay(self, tool_name: str) -> bool:
        """Check if a tool is safe to automatically replay upon crash recovery."""
        return tool_name in IDEMPOTENT_TOOLS

    def is_parked(self, call_id: str) -> bool:
        """Check if an intent is parked for operator review."""
        record = self._active_intents.get(call_id, {})
        return record.get("status") == "parked_for_operator_review"

    async def log_intent(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        task_id: str = "",
        is_idempotent: bool | None = None,
    ) -> str:
        """Log an intended tool execution before calling the handler."""
        call_id = str(uuid.uuid4())
        idempotent = is_idempotent if is_idempotent is not None else (tool_name in IDEMPOTENT_TOOLS)

        record = {
            "call_id": call_id,
            "tool": tool_name,
            "tool_name": tool_name,
            "args": arguments,
            "arguments": arguments,
            "executed": False,
            "task_id": task_id,
            "idempotent": idempotent,
            "status": "in_progress",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self._active_intents[call_id] = record

        # Persist to Jing working memory if available
        if self._memory and hasattr(self._memory, "remember"):
            try:
                import inspect
                if inspect.iscoroutinefunction(self._memory.remember):
                    await self._memory.remember(f"[Intent] Pre-execution tool={tool_name} args={arguments}")
                else:
                    self._memory.remember(f"[Intent] Pre-execution tool={tool_name} args={arguments}")
            except Exception as e:
                logger.warning(f"[IntentLogger] Could not persist intent to memory: {e}")

        logger.debug(f"[IntentLogger] Logged intent {call_id}: {tool_name} (idempotent={idempotent})")
        return call_id

    async def mark_completed(self, call_id: str, result: Any = None, output: Any = None) -> None:
        """Mark a tool invocation as successfully executed."""
        if call_id in self._active_intents:
            self._active_intents[call_id]["executed"] = True
            self._active_intents[call_id]["status"] = "completed"
            self._active_intents[call_id]["output"] = output if output is not None else result
            logger.debug(f"[IntentLogger] Completed intent {call_id}")

    async def mark_failed(self, call_id: str, error: str) -> None:
        """Mark a tool invocation as failed."""
        if call_id in self._active_intents:
            self._active_intents[call_id]["executed"] = False
            self._active_intents[call_id]["status"] = "failed"
            self._active_intents[call_id]["error"] = error

    async def mark_parked(self, call_id: str, reason: str = "") -> None:
        """Mark a tool invocation as parked for operator review."""
        if call_id in self._active_intents:
            self._active_intents[call_id]["status"] = "parked_for_operator_review"
            self._active_intents[call_id]["park_reason"] = reason
            logger.info(f"[IntentLogger] Parked intent {call_id} for review: {reason}")

    def get_parked_intents(self) -> list[dict[str, Any]]:
        """Return all intents currently parked for operator review."""
        return [
            rec for rec in self._active_intents.values()
            if rec.get("status") == "parked_for_operator_review"
        ]

    def audit_uncompleted_intents(self) -> dict[str, list[dict[str, Any]]]:
        """
        Evaluate any uncompleted tool invocations after an interruption:
        - 'replay': Idempotent read operations that can safely retry.
        - 'parked': Side-effecting operations requiring operator clearance.
        """
        replay: list[dict[str, Any]] = []
        parked: list[dict[str, Any]] = []

        for record in self._active_intents.values():
            if not record.get("executed"):
                if record.get("idempotent"):
                    replay.append(record)
                else:
                    record["status"] = "parked_for_operator_review"
                    parked.append(record)

        return {"replay": replay, "parked": parked}
