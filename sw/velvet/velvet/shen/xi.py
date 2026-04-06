"""
Xi (息): The Breath / Background Task Manager.

Xi manages background cognitive tasks that run between conversations.
Think of it as the "maintenance breathing" of the system — consolidation,
cleanup, trust evolution, and other long-running housekeeping.

Architecture:
  - BreathTask ABC: interface for all background tasks
  - ComputeBudget: resource limits for each task
  - XiJournal: append-only JSONL log of conversation turns
  - Xi: scheduler that dispatches BreathTasks based on compute budget
  
Tasks run at conversation boundaries (when the user stops talking),
and are mesh-distributed — Xi can route heavy tasks to other nodes.
"""

from __future__ import annotations

import asyncio
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from loguru import logger


# ============================================================================
# Compute Budget
# ============================================================================

@dataclass
class ComputeBudget:
    """Resource limits for a BreathTask."""
    cpu_seconds: float = 1.0       # Max CPU time
    gpu_needed: bool = False       # Does this task need GPU?
    gpu_vram_mb: int = 0           # GPU VRAM needed
    ram_mb: int = 64               # RAM needed
    network_io: bool = False       # Does this need network?
    priority: int = 5              # 1=critical, 10=idle


# ============================================================================
# Conversation Turn
# ============================================================================

@dataclass
class ConversationTurn:
    """A single exchange in a conversation."""
    user_input: str
    response: str
    skill_used: str | None = None
    params: dict = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    user_satisfied: bool | None = None  # None = unknown
    routed_to: str = ""                 # "po" or "hun"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> ConversationTurn:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ============================================================================
# BreathTask ABC
# ============================================================================

class BreathTask(ABC):
    """
    Abstract base class for background tasks managed by Xi.

    Each task declares a compute budget and implements a run() method
    that receives a batch of recent conversation turns.
    """

    @abstractmethod
    def name(self) -> str:
        """Unique name for this task."""
        ...

    @abstractmethod
    def budget(self) -> ComputeBudget:
        """Declare the compute resources this task needs."""
        ...

    @abstractmethod
    async def run(self, batch: list[ConversationTurn]) -> None:
        """
        Execute the background task.

        Args:
            batch: Recent conversation turns since last run.
        """
        ...


# ============================================================================
# Xi Journal
# ============================================================================

class XiJournal:
    """
    Append-only JSONL log of conversation turns.

    Each line is a JSON-serialized ConversationTurn. The journal tracks
    which entries have been processed by Xi, so tasks only see new data.
    """

    def __init__(self, path: str | Path | None = None, max_processed: int = 1000):
        if path is None:
            from velvet.config import get_config
            path = get_config().xi.journal_path
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._max_processed = max_processed
        self._processed_count = 0

    def append(self, turn: ConversationTurn):
        """Append a conversation turn to the journal."""
        try:
            with open(self._path, "a", encoding="utf-8") as f:
                line = json.dumps(turn.to_dict(), ensure_ascii=False)
                f.write(line + "\n")
        except Exception as e:
            logger.error(f"[XiJournal] Append failed: {e}")

    def read_unprocessed(self) -> list[ConversationTurn]:
        """Read all unprocessed turns from the journal."""
        if not self._path.exists():
            return []

        try:
            with open(self._path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Skip already-processed lines
            unprocessed = lines[self._processed_count:]
            turns = []
            for line in unprocessed:
                line = line.strip()
                if line:
                    try:
                        data = json.loads(line)
                        turns.append(ConversationTurn.from_dict(data))
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.warning(f"[XiJournal] Skipping malformed line: {e}")
            return turns
        except Exception as e:
            logger.error(f"[XiJournal] Read failed: {e}")
            return []

    def mark_processed(self, count: int):
        """Mark N entries as processed."""
        self._processed_count += count

        # Compact if we've accumulated too many processed entries
        if self._processed_count > self._max_processed:
            self._compact()

    def _compact(self):
        """Remove processed entries from the journal file."""
        if not self._path.exists():
            return

        try:
            with open(self._path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Keep only unprocessed lines
            remaining = lines[self._processed_count:]
            with open(self._path, "w", encoding="utf-8") as f:
                f.writelines(remaining)

            logger.info(
                f"[XiJournal] Compacted: removed {self._processed_count} processed entries, "
                f"{len(remaining)} remaining"
            )
            self._processed_count = 0
        except Exception as e:
            logger.error(f"[XiJournal] Compact failed: {e}")

    def total_lines(self) -> int:
        """Count total lines in the journal."""
        if not self._path.exists():
            return 0
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                return sum(1 for _ in f)
        except Exception:
            return 0


# ============================================================================
# Xi — The Breath
# ============================================================================

class Xi:
    """
    Xi (息): The Breath / Background Task Manager.

    Manages background cognitive tasks that run between conversations.
    Each task declares a ComputeBudget; Xi schedules them based on
    available resources and priority.
    """

    def __init__(self, journal: XiJournal | None = None):
        self._tasks: dict[str, BreathTask] = {}
        self._journal = journal or XiJournal()
        self._running = False
        self._breathe_lock = asyncio.Lock()

    def register_task(self, task: BreathTask):
        """Register a BreathTask with Xi."""
        self._tasks[task.name()] = task
        logger.info(f"[Xi] Registered BreathTask: {task.name()}")

    def record(self, turn: ConversationTurn):
        """Record a conversation turn to the journal."""
        self._journal.append(turn)

    async def breathe(self):
        """
        Execute all registered BreathTasks with the current batch.

        Called at conversation boundaries (when user stops talking).
        Tasks run in priority order, sequentially (to respect compute budget).
        """
        async with self._breathe_lock:
            batch = self._journal.read_unprocessed()
            if not batch:
                logger.debug("[Xi] No new turns to process")
                return

            logger.info(f"[Xi] Breathing... {len(batch)} turns, {len(self._tasks)} tasks")

            # Sort tasks by priority (lowest number = highest priority)
            sorted_tasks = sorted(
                self._tasks.values(),
                key=lambda t: t.budget().priority
            )

            for task in sorted_tasks:
                try:
                    start = time.monotonic()
                    await task.run(batch)
                    elapsed = time.monotonic() - start
                    logger.info(
                        f"[Xi] Task '{task.name()}' completed in {elapsed:.2f}s"
                    )
                except Exception as e:
                    logger.error(f"[Xi] Task '{task.name()}' failed: {e}")

            # Mark all turns as processed
            self._journal.mark_processed(len(batch))

    async def flush(self):
        """
        Final breathe before shutdown.

        Processes any remaining unprocessed turns.
        """
        logger.info("[Xi] Flushing (final breathe before shutdown)...")
        await self.breathe()

    @property
    def task_names(self) -> list[str]:
        """List registered task names."""
        return list(self._tasks.keys())
