"""
Model-Task Affinity Tracker.

The mesh learns which models perform best for specific task types
by recording outcomes (quality, latency) and ranking by average quality.

Data is persisted to Jing so the mesh remembers across restarts.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from loguru import logger


@dataclass
class TaskResult:
    """A recorded task execution result."""
    model: str            # e.g. "llama3.1:8b"
    task_type: str        # e.g. "fact_extraction", "code_gen", "chat"
    quality: float        # 0.0-1.0 subjective quality rating
    latency_ms: float     # Execution time in milliseconds
    timestamp: float = field(default_factory=time.time)
    device_id: str = ""   # Which device ran this


class ModelAffinityTracker:
    """
    Track which models are best for which task types.

    Hot cache for fast lookups, Jing backing for persistence.
    """

    def __init__(self, jing=None):
        self._jing = jing
        # Cache: task_type → [TaskResult, ...]
        self._cache: dict[str, list[TaskResult]] = {}

    async def record_task_result(
        self, model: str, task_type: str,
        quality: float, latency_ms: float, device_id: str = ""
    ):
        """
        Record a task execution result.

        Updates hot cache and persists to Jing.
        """
        result = TaskResult(
            model=model,
            task_type=task_type,
            quality=quality,
            latency_ms=latency_ms,
            device_id=device_id,
        )

        # Update cache
        self._cache.setdefault(task_type, []).append(result)

        # Keep cache bounded (last 100 per task type)
        if len(self._cache[task_type]) > 100:
            self._cache[task_type] = self._cache[task_type][-100:]

        # Persist to Jing
        jing = self._get_jing()
        if jing:
            try:
                text = (
                    f"Model affinity: model={model}, task={task_type}, "
                    f"quality={quality:.2f}, latency={latency_ms:.0f}ms, device={device_id}"
                )
                await jing.remember(text, role="system", metadata={
                    "source": "affinity_tracker",
                    "model": model,
                    "task_type": task_type,
                    "quality": quality,
                    "latency_ms": latency_ms,
                })
            except Exception as e:
                logger.error(f"[AffinityTracker] Failed to persist: {e}")

    def best_model_for(self, task_type: str) -> str | None:
        """
        Get the best model for a task type.

        Sync read from cache. Ranks by average quality score.
        Returns None if no data is available.
        """
        results = self._cache.get(task_type, [])
        if not results:
            return None

        # Group by model, compute average quality
        model_scores: dict[str, list[float]] = {}
        for r in results:
            model_scores.setdefault(r.model, []).append(r.quality)

        # Rank by average quality (descending)
        ranked = sorted(
            model_scores.items(),
            key=lambda x: sum(x[1]) / len(x[1]),
            reverse=True,
        )

        best_model = ranked[0][0]
        best_avg = sum(ranked[0][1]) / len(ranked[0][1])
        logger.debug(
            f"[AffinityTracker] Best model for '{task_type}': "
            f"{best_model} (avg quality={best_avg:.2f})"
        )
        return best_model

    def get_rankings(self, task_type: str) -> list[tuple[str, float]]:
        """
        Get all model rankings for a task type.

        Returns list of (model_name, avg_quality) sorted best first.
        """
        results = self._cache.get(task_type, [])
        if not results:
            return []

        model_scores: dict[str, list[float]] = {}
        for r in results:
            model_scores.setdefault(r.model, []).append(r.quality)

        return sorted(
            [(m, sum(q) / len(q)) for m, q in model_scores.items()],
            key=lambda x: x[1],
            reverse=True,
        )

    async def refresh_cache(self):
        """Refresh cache from Jing (called by Inari or at startup)."""
        jing = self._get_jing()
        if not jing:
            return

        try:
            results = await jing.recall("model affinity", limit=100, deep=True)
            loaded = 0
            for text in results:
                result = self._parse_affinity_text(text)
                if result:
                    self._cache.setdefault(result.task_type, []).append(result)
                    loaded += 1

            logger.info(f"[AffinityTracker] Cache refreshed: {loaded} results loaded")
        except Exception as e:
            logger.error(f"[AffinityTracker] Cache refresh failed: {e}")

    @staticmethod
    def _parse_affinity_text(text: str) -> TaskResult | None:
        """Parse a TaskResult from Jing memory text."""
        try:
            if "Model affinity:" not in text:
                return None
            parts = text.split("Model affinity:")[1].strip()
            pairs = {}
            for part in parts.split(", "):
                if "=" in part:
                    k, v = part.split("=", 1)
                    pairs[k.strip()] = v.strip()
            return TaskResult(
                model=pairs.get("model", ""),
                task_type=pairs.get("task", ""),
                quality=float(pairs.get("quality", "0.5")),
                latency_ms=float(pairs.get("latency", "0").replace("ms", "")),
                device_id=pairs.get("device", ""),
            )
        except Exception:
            return None

    def _get_jing(self):
        if self._jing is None:
            try:
                from velvet.shen.jing import Jing
                self._jing = Jing()
            except Exception:
                pass
        return self._jing
