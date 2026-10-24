"""
Unit tests for Velvet Nadir Phase 6:
Master BreathTasks Schedule, Privacy Tasks, and Scheduler Jitter.
"""

import pytest
from velvet.shen.xi import Xi, ConversationTurn
from velvet.privacy.tasks import (
    MetadataStripperTask,
    HoneypotMonitor,
    NarrativeRadarTask,
    CanaryMonitor,
    PhantomPersonaManager,
    TrackerPolluter,
    AIToolNoise,
)


def test_privacy_breathtasks_priorities_and_budgets():
    """Verify priorities and compute budgets for the privacy tasks."""
    t_strip = MetadataStripperTask()
    assert t_strip.budget().priority == 2

    t_honey = HoneypotMonitor()
    assert t_honey.budget().priority == 10

    t_radar = NarrativeRadarTask()
    assert t_radar.budget().priority == 12

    t_canary = CanaryMonitor()
    assert t_canary.budget().priority == 15

    t_phantom = PhantomPersonaManager()
    assert t_phantom.budget().priority == 22

    t_tracker = TrackerPolluter()
    assert t_tracker.budget().priority == 25

    t_noise = AIToolNoise()
    assert t_noise.budget().priority == 25


def test_scheduler_jitter_for_privacy_tasks():
    """Verify that Xi applies +/- 0-30% jitter to privacy tasks, but keeps non-privacy tasks deterministic."""
    xi = Xi()
    base_interval = 100.0

    # Privacy task gets jittered between 70.0 and 130.0
    intervals = [xi.schedule_next_run("TrackerPolluter", base_interval) for _ in range(50)]
    assert all(70.0 <= val <= 130.0 for val in intervals)
    # At least two distinct intervals to verify variance
    assert len(set(intervals)) > 1

    # Non-privacy task receives exactly base_interval (no jitter)
    non_privacy_intervals = [xi.schedule_next_run("OccamsRazor", base_interval) for _ in range(10)]
    assert all(val == 100.0 for val in non_privacy_intervals)


@pytest.mark.asyncio
async def test_xi_registers_and_runs_privacy_tasks():
    """Verify Xi registers and executes privacy breath tasks in priority order."""
    xi = Xi()
    tasks = [
        MetadataStripperTask(),
        HoneypotMonitor(),
        CanaryMonitor(),
        PhantomPersonaManager(),
        TrackerPolluter(),
        AIToolNoise(),
    ]
    for t in tasks:
        xi.register_task(t)

    assert len(xi.task_names) == 6

    # Record turn and breathe
    turn = ConversationTurn(user_input="test input", response="test response")
    xi.record(turn)
    await xi.breathe()
