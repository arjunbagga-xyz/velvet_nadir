"""
Tests for Phase 2: Task Execution Governance & Multi-Tier Persistence.
Covers TaskGraph Kanban rules, ownership enforcement, blocker escalation,
StopGateEngine synthetic turn nudge, GoalJudge verification, and Tartarus persistence.
"""

import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pytest
from unittest.mock import AsyncMock, MagicMock

from velvet.task_graph import TaskGraph, TaskNode, TaskState, BlockerTaxonomy
from velvet.shen.stop_gates import StopGateEngine
from velvet.shen.goal_judge import GoalJudge, GoalVerificationError
from velvet.llm import LLMResponse


# =========================================================================
# 1. TaskGraph Ownership Enforcement
# =========================================================================

def test_task_ownership_enforcement(tmp_path):
    db_file = tmp_path / "test_tasks.db"
    graph = TaskGraph(db_path=db_file)

    task = graph.add_task("Build feature", "Build login feature", assigned_to="worker_alpha")
    assert task.assigned_to == "worker_alpha"

    # Authorized worker update succeeds
    graph.update_task_state(task.id, TaskState.IN_PROGRESS, worker_id="worker_alpha")
    assert task.state == TaskState.IN_PROGRESS

    # Unauthorized worker update raises PermissionError
    with pytest.raises(PermissionError) as exc_info:
        graph.update_task_state(task.id, TaskState.FAILED, worker_id="worker_beta")
    assert "Worker 'worker_beta' is not authorized" in str(exc_info.value)


# =========================================================================
# 2. Blocker Escalation Rule (>= 3 times -> BLOCKED_TRIAGE)
# =========================================================================

def test_blocker_escalation_rule(tmp_path):
    db_file = tmp_path / "test_tasks.db"
    graph = TaskGraph(db_path=db_file)

    task = graph.add_task("Deploy service", "Deploy container to production", assigned_to="worker_1")
    graph.update_task_state(task.id, TaskState.IN_PROGRESS, worker_id="worker_1")

    # Block 1
    graph.task_block(task.id, reason="Missing docker registry key", kind="credential", worker_id="worker_1")
    assert task.state == TaskState.BLOCKED
    assert len(task.blocker_history) == 1

    # Block 2
    graph.task_block(task.id, reason="Missing docker registry key", kind="credential", worker_id="worker_1")
    assert task.state == TaskState.BLOCKED
    assert len(task.blocker_history) == 2

    # Block 3 -> Auto-escalate to BLOCKED_TRIAGE
    graph.task_block(task.id, reason="Missing docker registry key", kind="credential", worker_id="worker_1")
    assert task.state == TaskState.BLOCKED_TRIAGE
    assert len(task.blocker_history) == 3


# =========================================================================
# 3. Task Completion & Multi-Tier Persistence
# =========================================================================

def test_task_completion_and_restore(tmp_path):
    db_file = tmp_path / "test_tasks.db"
    graph = TaskGraph(db_path=db_file)

    task = graph.add_task("Audit log analysis", "Scan logs for anomalies", assigned_to="worker_sec")
    graph.update_task_state(task.id, TaskState.IN_PROGRESS, worker_id="worker_sec")

    # Complete task
    completed = graph.task_complete(
        task.id,
        summary="Analysis complete. Zero critical anomalies found.",
        artifacts=["/tmp/audit.json"],
        worker_id="worker_sec",
    )
    assert completed.state == TaskState.COMPLETED
    assert completed.completed_at is not None
    assert "/tmp/audit.json" in completed.artifacts

    # Create new task in progress
    active_task = graph.add_task("Background watch", "Monitoring network", assigned_to="worker_sec")
    graph.update_task_state(active_task.id, TaskState.IN_PROGRESS, worker_id="worker_sec")

    # Simulate node boot: restore active tasks from SQLite
    new_graph = TaskGraph(db_path=db_file)
    restored_count = new_graph.restore_on_boot()
    assert restored_count >= 1
    assert active_task.id in new_graph.tasks
    assert new_graph.tasks[active_task.id].state == TaskState.IN_PROGRESS
    # Completed task is not restored into hot Aether memory
    assert task.id not in new_graph.tasks


# =========================================================================
# 4. Evict Stale Tasks from Hot Aether Memory
# =========================================================================

def test_evict_stale_tasks(tmp_path):
    db_file = tmp_path / "test_tasks.db"
    graph = TaskGraph(db_path=db_file)

    old_task = graph.add_task("Old task", "Completed 3 days ago")
    graph.update_task_state(old_task.id, TaskState.IN_PROGRESS)
    graph.task_complete(old_task.id, summary="Done")
    # Manually backdate completion
    old_task.completed_at = datetime.now(timezone.utc) - timedelta(hours=72)

    fresh_task = graph.add_task("Fresh task", "Completed 1 hour ago")
    graph.update_task_state(fresh_task.id, TaskState.IN_PROGRESS)
    graph.task_complete(fresh_task.id, summary="Done")

    evicted = graph.evict_stale(max_age_hours=48)
    assert evicted == 1
    assert old_task.id not in graph.tasks
    assert fresh_task.id in graph.tasks


# =========================================================================
# 5. StopGateEngine Synthetic Turn Nudge
# =========================================================================

def test_stop_gate_plain_text_interception():
    engine = StopGateEngine()
    active_task = TaskNode(
        id="task_123",
        name="Update Database Schema",
        description="Run migrations",
        state=TaskState.IN_PROGRESS,
    )

    # 1. Plain text reply while task is IN_PROGRESS -> Intercept!
    plain_resp = LLMResponse(text="I have finished updating the schema for you.")
    intercepted, nudge = engine.intercept_turn(plain_resp, active_task)
    assert intercepted is True
    assert nudge is not None
    assert "A plain-text reply is NOT completion" in nudge
    assert "task_complete" in nudge

    # 2. Response with tool call -> Proceed normally
    tool_resp = LLMResponse(
        text="",
        tool_calls=[{"function": {"name": "task_complete", "arguments": "{}"}}],
    )
    intercepted_tool, nudge_tool = engine.intercept_turn(tool_resp, active_task)
    assert intercepted_tool is False
    assert nudge_tool is None

    # 3. No active task -> Proceed normally
    intercepted_none, _ = engine.intercept_turn(plain_resp, None)
    assert intercepted_none is False

    # 4. Task is PENDING (not IN_PROGRESS) -> Proceed normally
    active_task.state = TaskState.PENDING
    intercepted_pending, _ = engine.intercept_turn(plain_resp, active_task)
    assert intercepted_pending is False


# =========================================================================
# 6. GoalJudge Verification
# =========================================================================

@pytest.mark.asyncio
async def test_goal_judge_artifact_and_verdict(tmp_path):
    artifact_file = tmp_path / "report.pdf"
    artifact_file.write_text("Mock report content")

    task = TaskNode(
        id="task_audit",
        name="Audit Report",
        description="Generate audit report",
        state=TaskState.IN_PROGRESS,
        assigned_to="worker_alpha",
    )

    judge = GoalJudge()

    # Artifact exists on disk -> Passes
    ok, message = await judge.verify_task_completion(
        task=task,
        summary="Report generated successfully",
        artifacts=[str(artifact_file)],
    )
    assert ok is True

    # Artifact does not exist on disk -> Rejects
    missing_file = tmp_path / "non_existent.pdf"
    bad_ok, bad_message = await judge.verify_task_completion(
        task=task,
        summary="Report generated successfully",
        artifacts=[str(missing_file)],
    )
    assert bad_ok is False
    assert "does not exist on disk" in bad_message

    # Test independent LLM judge routing
    mock_adapter = MagicMock()
    mock_adapter.generate_judge = AsyncMock(
        return_value=LLMResponse(text="VERDICT: COMPLETE. Requirements verified.")
    )
    llm_ok, llm_verdict = await judge.verify_task_completion(
        task=task,
        summary="Completed successfully",
        artifacts=[str(artifact_file)],
        llm_adapter=mock_adapter,
    )
    assert llm_ok is True
    assert "VERDICT: COMPLETE" in llm_verdict
    mock_adapter.generate_judge.assert_awaited_once()
