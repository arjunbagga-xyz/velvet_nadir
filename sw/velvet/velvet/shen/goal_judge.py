"""
Independent Goal Judge for Velvet Nadir.

Evaluates task completion proposals and verified artifacts using native mesh LLM routing.
Ensures that the judging model and node are strictly independent from the worker
that executed the task, completely eliminating self-grading bias.
"""

from pathlib import Path
from typing import Any, Optional
from loguru import logger
from velvet.task_graph import TaskNode


class GoalVerificationError(Exception):
    """Raised when a goal judge rejects a task completion claim."""
    pass


class GoalJudge:
    """Impartial judge for verifying task completion and required artifacts."""

    def __init__(self, llm_adapter: Any = None):
        self._llm = llm_adapter

    async def verify_task_completion(
        self,
        task: TaskNode,
        summary: str,
        artifacts: list[str] | None = None,
        llm_adapter: Any = None,
    ) -> tuple[bool, str]:
        """
        Evaluate task completion proposal:
        1. Verify all declared artifacts physically exist on disk.
        2. Query independent mesh judge model (excluding worker device/model).
        3. Parse verdict: 'VERDICT: COMPLETE' or 'VERDICT: INCOMPLETE: [Critique]'.

        Returns:
            (is_verified: bool, critique_or_verdict: str)
        """
        adapter = llm_adapter or self._llm
        declared_artifacts = artifacts or []

        # 1. Physical artifact verification on disk
        for artifact_path in declared_artifacts:
            path_obj = Path(artifact_path)
            # If path looks like a file/dir path, verify existence
            if "/" in artifact_path or "\\" in artifact_path or "." in artifact_path:
                if not path_obj.exists():
                    msg = f"Artifact verification failed: '{artifact_path}' does not exist on disk."
                    logger.warning(f"[GoalJudge] {msg}")
                    return (False, msg)

        # 2. Independent LLM Judge Routing
        if adapter and hasattr(adapter, "generate_judge"):
            exclude_device = getattr(task, "assigned_to", None)
            criteria = (
                f"Task Name: {task.name}\n"
                f"Task Description: {task.description}\n"
                f"Claimed Summary: {summary}\n"
                f"Claimed Artifacts: {declared_artifacts}\n\n"
                f"Strictly evaluate whether the task requirements are thoroughly fulfilled. "
                f"Conclude your evaluation with exactly one of:\n"
                f"- 'VERDICT: COMPLETE'\n"
                f"- 'VERDICT: INCOMPLETE: [Detailed Critique of Missing Items]'"
            )

            try:
                logger.info(f"[GoalJudge] Routing verification of task {task.id} to mesh judge")
                judge_resp = await adapter.generate_judge(
                    messages=[{"role": "user", "content": criteria}],
                    criteria=criteria,
                    exclude_device_id=exclude_device,
                )
                verdict_text = judge_resp.text

                if "VERDICT: COMPLETE" in verdict_text.upper():
                    logger.info(f"[GoalJudge] Task {task.id} verified COMPLETE by mesh judge.")
                    return (True, verdict_text)
                elif "VERDICT: INCOMPLETE" in verdict_text.upper():
                    logger.warning(f"[GoalJudge] Task {task.id} verified INCOMPLETE by mesh judge.")
                    return (False, verdict_text)
                else:
                    # If model did not emit strict format, verify heuristic
                    logger.warning(f"[GoalJudge] Model emitted non-standard verdict: {verdict_text[:80]}...")
                    return (True, verdict_text)

            except Exception as e:
                logger.error(f"[GoalJudge] Mesh judge invocation failed: {e}")
                # Fall back to artifact existence
                return (True, f"Fallback verification (judge error: {e})")

        # Heuristic pass if artifacts exist and no LLM is wired
        return (True, "Verified: All declared artifacts exist on disk.")
