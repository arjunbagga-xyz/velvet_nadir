"""
TaskGraph System for Velvet Nadir

Provides hierarchical goal-driven task management with dependencies,
ownership enforcement, blocker escalation, and multi-tier persistence
(Aether RAM -> Mnemosyne Vector -> Tartarus SQLite).
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
import sqlite3
import uuid
import json
from enum import Enum
from loguru import logger
import asyncio


class TaskState(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    BLOCKED_TRIAGE = "blocked_triage"


class BlockerTaxonomy(str, Enum):
    DEPENDENCY = "dependency"
    RESOURCE = "resource"
    APPROVAL = "approval"
    EXTERNAL = "external"
    NEEDS_INPUT = "needs_input"
    CAPABILITY = "capability"
    TRANSIENT = "transient"


@dataclass
class TaskNode:
    id: str
    name: str
    description: str
    state: TaskState = TaskState.PENDING
    assigned_to: Optional[str] = None  # Agent ID / Worker ID
    dependencies: List[str] = field(default_factory=list)  # Task IDs
    result: Any = None
    error: Optional[str] = None
    subtasks: List['TaskNode'] = field(default_factory=list)
    blocker_taxonomy: Optional[BlockerTaxonomy] = None
    verified: bool = False

    # --- Kanban & Governance Fields ---
    goal_mode: bool = False
    blocker_kind: Optional[str] = None
    blocker_history: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    completed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class TaskGraph:
    """
    Hierarchical TaskGraph with Kanban ownership rules, blocker escalation,
    and 3-tier persistence (Aether / Mnemosyne / Tartarus).
    """

    def __init__(self, db_path: str | Path | None = None):
        self.tasks: Dict[str, TaskNode] = {}
        self._db_path = Path(db_path) if db_path else Path.home() / ".velvet" / "task_archive.db"
        self._init_sqlite()

    def _init_sqlite(self) -> None:
        """Initialize Tartarus SQLite schema for cold task archival."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS task_archive (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    state TEXT NOT NULL,
                    assigned_to TEXT,
                    dependencies TEXT,
                    result TEXT,
                    error TEXT,
                    goal_mode INTEGER DEFAULT 0,
                    blocker_kind TEXT,
                    blocker_history TEXT,
                    artifacts TEXT,
                    verified INTEGER DEFAULT 0,
                    completed_at TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            conn.commit()

    def _persist_task(self, task: TaskNode) -> None:
        """Persist a single task node to SQLite cold archive."""
        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO task_archive (
                        id, name, description, state, assigned_to, dependencies,
                        result, error, goal_mode, blocker_kind, blocker_history,
                        artifacts, verified, completed_at, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    task.id,
                    task.name,
                    task.description,
                    task.state.value if isinstance(task.state, TaskState) else str(task.state),
                    task.assigned_to,
                    json.dumps(task.dependencies),
                    json.dumps(task.result) if task.result is not None else None,
                    task.error,
                    1 if task.goal_mode else 0,
                    task.blocker_kind,
                    json.dumps(task.blocker_history),
                    json.dumps(task.artifacts),
                    1 if task.verified else 0,
                    task.completed_at.isoformat() if task.completed_at else None,
                    task.created_at.isoformat() if task.created_at else datetime.now(timezone.utc).isoformat(),
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"[TaskGraph] Failed to persist task {task.id} to SQLite: {e}")

    def add_task(
        self,
        name: str,
        description: str,
        dependencies: List[str] | None = None,
        goal_mode: bool = False,
        assigned_to: Optional[str] = None,
    ) -> TaskNode:
        """Add a new task to the graph and Tartarus archive."""
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        task = TaskNode(
            id=task_id,
            name=name,
            description=description,
            dependencies=dependencies or [],
            goal_mode=goal_mode,
            assigned_to=assigned_to,
        )
        self.tasks[task_id] = task
        self._persist_task(task)
        logger.info(f"[TaskGraph] Added task {task_id}: {name} (goal_mode={goal_mode})")
        self._update_states()
        return task

    def add_subtask(
        self,
        parent_id: str,
        name: str,
        description: str,
        dependencies: List[str] | None = None,
        goal_mode: bool = False,
    ) -> TaskNode:
        """Add a subtask under a parent task."""
        parent = self.tasks.get(parent_id)
        if not parent:
            raise ValueError(f"Parent task {parent_id} not found")

        task = self.add_task(name, description, dependencies, goal_mode=goal_mode)
        parent.subtasks.append(task)
        if parent.state in (TaskState.BLOCKED, TaskState.BLOCKED_TRIAGE):
            task.state = parent.state
            task.blocker_taxonomy = parent.blocker_taxonomy
            task.blocker_kind = parent.blocker_kind
            self._persist_task(task)
        return task

    def assign_task(self, task_id: str, agent_id: str) -> None:
        """Assign task ownership to a specific agent/worker."""
        task = self.tasks.get(task_id)
        if task:
            task.assigned_to = agent_id
            self._persist_task(task)
            logger.info(f"[TaskGraph] Task {task_id} assigned to {agent_id}")

    def update_task_state(
        self,
        task_id: str,
        state: TaskState,
        result: Any = None,
        error: str | None = None,
        verified: bool = False,
        blocker_taxonomy: Optional[BlockerTaxonomy] = None,
        worker_id: Optional[str] = None,
    ) -> None:
        """
        Update task state with strict ownership verification.
        Rejects modifications if worker_id != task.assigned_to.
        """
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        # Ownership enforcement
        if worker_id and task.assigned_to and task.assigned_to != worker_id:
            raise PermissionError(
                f"Worker '{worker_id}' is not authorized to update task '{task_id}' "
                f"(assigned to '{task.assigned_to}')"
            )

        if state == TaskState.COMPLETED and not verified and not task.verified:
            raise ValueError(f"Task {task_id} cannot be marked COMPLETED without verification")

        task.state = state
        if verified:
            task.verified = verified
        if blocker_taxonomy:
            task.blocker_taxonomy = blocker_taxonomy
        if result is not None:
            task.result = result
        if error is not None:
            task.error = error
        if state == TaskState.COMPLETED and not task.completed_at:
            task.completed_at = datetime.now(timezone.utc)

        logger.info(f"[TaskGraph] Task {task_id} state updated to {state.value}")
        self._persist_task(task)
        self._update_states()

    def task_block(
        self,
        task_id: str,
        reason: str,
        kind: str = "dependency",
        worker_id: Optional[str] = None,
    ) -> TaskNode:
        """
        Register a blocker on a task.
        Appends to blocker_history and auto-escalates to BLOCKED_TRIAGE
        if repeated >= 3 times.
        """
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        if worker_id and task.assigned_to and task.assigned_to != worker_id:
            raise PermissionError(f"Worker '{worker_id}' not authorized to block task '{task_id}'")

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "kind": kind,
        }
        task.blocker_history.append(entry)
        task.blocker_kind = kind
        task.error = reason

        # Check escalation threshold: >= 3 occurrences of same kind or reason
        matching_count = sum(
            1 for b in task.blocker_history
            if b.get("kind") == kind or b.get("reason") == reason
        )

        if matching_count >= 3:
            task.state = TaskState.BLOCKED_TRIAGE
            logger.warning(
                f"[TaskGraph] Task {task_id} auto-escalated to BLOCKED_TRIAGE "
                f"({matching_count}x blocker on '{kind}': {reason})"
            )
        else:
            task.state = TaskState.BLOCKED

        self._persist_task(task)
        self._update_states()
        return task

    def task_complete(
        self,
        task_id: str,
        summary: str,
        artifacts: list[str] | None = None,
        worker_id: Optional[str] = None,
        verified: bool = True,
    ) -> TaskNode:
        """
        Mark task complete with summary and verified artifacts.
        Persists to Tartarus and writes warm embedding to Mnemosyne.
        """
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        if worker_id and task.assigned_to and task.assigned_to != worker_id:
            raise PermissionError(f"Worker '{worker_id}' not authorized to complete task '{task_id}'")

        task.result = summary
        task.artifacts = artifacts or []
        task.completed_at = datetime.now(timezone.utc)
        task.state = TaskState.COMPLETED

        # Verify declared physical artifacts if present
        if task.artifacts:
            for art in task.artifacts:
                if ("/" in art or "\\" in art or "." in art) and not Path(art).exists():
                    logger.debug(f"[TaskGraph] Declared artifact '{art}' not yet on disk")

        task.verified = verified

        self._persist_task(task)

        # Index into Mnemosyne (warm semantic memory in Jing) if running loop available
        try:
            loop = asyncio.get_running_loop()
            from velvet.shen.jing import Jing
            jing = Jing()
            meta = {
                "task_id": task.id,
                "task_name": task.name,
                "artifacts": task.artifacts,
                "category": "task_completed",
            }
            loop.create_task(jing.remember(f"Completed Task: {task.name}. {summary}", metadata=meta))
        except (RuntimeError, Exception) as e:
            logger.debug(f"[TaskGraph] Jing warm index skipped: {e}")

        self._update_states()
        return task

    def restore_on_boot(self) -> int:
        """
        Restore active tasks (pending, in_progress, blocked, blocked_triage)
        from Tartarus SQLite archive into Aether memory on node startup.
        """
        restored = 0
        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT * FROM task_archive
                    WHERE state IN ('pending', 'in_progress', 'blocked', 'blocked_triage')
                """)
                for row in cursor:
                    t_id = row["id"]
                    try:
                        state_val = TaskState(row["state"])
                    except ValueError:
                        state_val = TaskState.PENDING

                    deps = json.loads(row["dependencies"]) if row["dependencies"] else []
                    b_history = json.loads(row["blocker_history"]) if row["blocker_history"] else []
                    arts = json.loads(row["artifacts"]) if row["artifacts"] else []

                    c_at = None
                    if row["completed_at"]:
                        try:
                            c_at = datetime.fromisoformat(row["completed_at"])
                        except ValueError:
                            pass

                    created_at = datetime.now(timezone.utc)
                    if row["created_at"]:
                        try:
                            created_at = datetime.fromisoformat(row["created_at"])
                        except ValueError:
                            pass

                    node = TaskNode(
                        id=t_id,
                        name=row["name"],
                        description=row["description"],
                        state=state_val,
                        assigned_to=row["assigned_to"],
                        dependencies=deps,
                        result=row["result"],
                        error=row["error"],
                        goal_mode=bool(row["goal_mode"]),
                        blocker_kind=row["blocker_kind"],
                        blocker_history=b_history,
                        artifacts=arts,
                        verified=bool(row["verified"]),
                        completed_at=c_at,
                        created_at=created_at,
                    )
                    self.tasks[t_id] = node
                    restored += 1

            logger.info(f"[TaskGraph] Restored {restored} active tasks from Tartarus on boot.")
            self._update_states()
        except Exception as e:
            logger.error(f"[TaskGraph] Failed to restore tasks on boot: {e}")

        return restored

    def evict_stale(self, max_age_hours: int = 48) -> int:
        """
        Evict completed/failed tasks from hot Aether RAM if older than max_age_hours
        AND no pending/in_progress tasks depend on them.
        """
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=max_age_hours)
        evicted = 0

        # Collect dependencies of all active tasks
        active_deps: set[str] = set()
        for t in self.tasks.values():
            if t.state in (TaskState.PENDING, TaskState.IN_PROGRESS, TaskState.BLOCKED, TaskState.BLOCKED_TRIAGE):
                active_deps.update(t.dependencies)

        to_remove = []
        for t_id, task in self.tasks.items():
            if task.state in (TaskState.COMPLETED, TaskState.FAILED):
                timestamp = task.completed_at or task.created_at
                if timestamp and timestamp < cutoff:
                    if t_id not in active_deps:
                        to_remove.append(t_id)

        for t_id in to_remove:
            del self.tasks[t_id]
            evicted += 1

        logger.info(f"[TaskGraph] Evicted {evicted} stale tasks from Aether RAM.")
        return evicted

    def get_actionable_tasks(self, agent_id: Optional[str] = None) -> List[TaskNode]:
        """Return tasks that are ready to be worked on (dependencies met)."""
        actionable = []
        for task in self.tasks.values():
            if task.state == TaskState.PENDING:
                if agent_id and task.assigned_to and task.assigned_to != agent_id:
                    continue
                actionable.append(task)
        return actionable

    def _update_states(self) -> None:
        """Re-evaluate all task states based on dependencies."""
        changed = True
        while changed:
            changed = False
            for task in self.tasks.values():
                if task.state == TaskState.PENDING:
                    deps_met = True
                    for dep_id in task.dependencies:
                        dep_task = self.tasks.get(dep_id)
                        if not dep_task or dep_task.state != TaskState.COMPLETED:
                            deps_met = False
                            break

                    if not deps_met:
                        task.state = TaskState.BLOCKED
                        task.blocker_taxonomy = BlockerTaxonomy.DEPENDENCY
                        task.blocker_kind = "dependency"
                        changed = True

                elif task.state == TaskState.BLOCKED and (
                    task.blocker_taxonomy == BlockerTaxonomy.DEPENDENCY or task.blocker_kind == "dependency"
                ):
                    deps_met = True
                    for dep_id in task.dependencies:
                        dep_task = self.tasks.get(dep_id)
                        if not dep_task or dep_task.state != TaskState.COMPLETED:
                            deps_met = False
                            break

                    if deps_met:
                        task.state = TaskState.PENDING
                        task.blocker_taxonomy = None
                        task.blocker_kind = None
                        changed = True

                if task.subtasks and task.state in (TaskState.IN_PROGRESS, TaskState.PENDING):
                    all_completed = all(sub.state == TaskState.COMPLETED for sub in task.subtasks)
                    any_failed = any(sub.state == TaskState.FAILED for sub in task.subtasks)
                    if any_failed:
                        task.state = TaskState.FAILED
                        changed = True
                    elif all_completed:
                        if task.verified or all(sub.verified for sub in task.subtasks):
                            task.state = TaskState.COMPLETED
                            task.verified = True
                            if not task.completed_at:
                                task.completed_at = datetime.now(timezone.utc)
                            changed = True

    def save_snapshot(self) -> None:
        """Save active tasks to SQLite and Jing memory."""
        for task in self.tasks.values():
            self._persist_task(task)
        logger.info("[TaskGraph] Snapshot saved to Tartarus SQLite.")

    def load_snapshot(self) -> None:
        """Load active tasks from Tartarus SQLite."""
        self.restore_on_boot()
