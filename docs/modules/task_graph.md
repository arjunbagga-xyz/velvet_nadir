# TaskGraph & Multi-Tier Persistence (`task_graph.py`)

## Overview
`velvet.task_graph` enforces strict Kanban execution governance across the mesh and manages 3-tier persistence.

## Architecture
- **States**: `BACKLOG`, `TODO`, `IN_PROGRESS`, `BLOCKED`, `BLOCKED_TRIAGE`, `REVIEW`, `DONE`, `FAILED`.
- **Ownership Enforcement**: Only the worker assigned to a task (`worker_id == task.assigned_to`) may transition or complete it.
- **Blocker Taxonomy & Escalation**: Classifies blockers as `NEEDS_INPUT`, `CAPABILITY`, or `TRANSIENT`. If a task is blocked $\ge 3$ consecutive times, it auto-escalates to `BLOCKED_TRIAGE`.
- **Multi-Tier Persistence**:
  1. **Aether (Hot Tier)**: In-memory DAG for microsecond routing.
  2. **Mnemosyne (Warm Tier)**: Vector embeddings for semantic search.
  3. **Tartarus (Cold Tier)**: SQLite database (`task_archive`) storing historical records and supporting cold boot restore (`restore_on_boot()`).
