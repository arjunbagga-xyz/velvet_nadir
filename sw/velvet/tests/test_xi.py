import pytest
import json
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

from velvet.shen.xi import (
    Xi, XiJournal, BreathTask, ComputeBudget, ConversationTurn
)
from velvet.shen.locus import LocusEngine, LocationUpdate, haversine_distance
from velvet.shen.triangulation import TriangulationTask
from velvet.config import get_config


# ============================================================================
# ConversationTurn & XiJournal Tests
# ============================================================================

class TestConversationTurn:
    """Test ConversationTurn serializability."""

    def test_create_turn(self):
        turn = ConversationTurn(
            user_input="What time is it?",
            response="It's 3pm.",
            skill_used="get_time",
            routed_to="po",
        )
        assert turn.user_input == "What time is it?"
        assert turn.routed_to == "po"

    def test_roundtrip(self):
        original = ConversationTurn(
            user_input="What's the weather?",
            response="Sunny, 25°C.",
            skill_used="weather",
            params={"city": "Bangalore"},
        )
        restored = ConversationTurn.from_dict(original.to_dict())
        assert restored.user_input == original.user_input
        assert restored.params == original.params


class TestXiJournal:
    """Test XiJournal JSONL file appending and processing flags."""

    @pytest.fixture
    def journal(self, tmp_path):
        return XiJournal(path=tmp_path / "test_journal.jsonl", max_processed=5)

    def test_append_creates_file(self, journal):
        turn = ConversationTurn(user_input="test", response="reply")
        journal.append(turn)
        assert journal.total_lines() == 1

    def test_read_unprocessed_all(self, journal):
        journal.append(ConversationTurn(user_input="q1", response="a1"))
        turns = journal.read_unprocessed()
        assert len(turns) == 1
        assert turns[0].user_input == "q1"


# ============================================================================
# ComputeBudget & Scheduler Tests
# ============================================================================

class DummyTask(BreathTask):
    def __init__(self, task_name="dummy", priority=5):
        self._name = task_name
        self._priority = priority
        self.executed = False
        self.received_batch = []

    def name(self) -> str:
        return self._name

    def budget(self) -> ComputeBudget:
        return ComputeBudget(priority=self._priority)

    async def run(self, batch):
        self.executed = True
        self.received_batch = batch


class TestComputeBudget:
    """Tests for BreathTask execution resource budgets."""

    def test_defaults(self):
        budget = ComputeBudget()
        assert budget.cpu_seconds == 1.0
        assert budget.gpu_needed is False
        assert budget.priority == 5

    def test_custom(self):
        budget = ComputeBudget(
            cpu_seconds=5.0,
            gpu_needed=True,
            gpu_vram_mb=2048,
            priority=1,
        )
        assert budget.gpu_needed is True
        assert budget.gpu_vram_mb == 2048


class TestXiScheduler:
    """Test Xi BreathTask scheduling and lifecycle loop."""

    @pytest.mark.asyncio
    async def test_scheduler_task_registration(self, tmp_path):
        journal = XiJournal(path=tmp_path / "test_journal.jsonl")
        xi = Xi(journal=journal)
        task = DummyTask()
        
        xi.register_task(task)
        assert "dummy" in xi.task_names
        
        xi.record(ConversationTurn(user_input="q1", response="a1"))
        await xi.breathe()
        assert task.executed is True
        assert len(task.received_batch) == 1


# ============================================================================
# Spatial Locus and Triangulation Tests
# ============================================================================

class TestLocusSpatialTracking:
    """Verify haversine computations and GPS geo-fence tracking."""

    @pytest.fixture
    def mock_locus(self):
        config = get_config()
        config.locus.enabled = True
        config.locus.seed_fences = [
            {"name": "home", "lat": 37.7749, "lon": -122.4194, "radius_meters": 100.0},
            {"name": "work", "lat": 37.3382, "lon": -121.8863, "radius_meters": 200.0}
        ]
        return LocusEngine(start_subscriber=False)

    def test_haversine_distance(self):
        # San Francisco to San Jose distance
        dist = haversine_distance(37.7749, -122.4194, 37.3382, -121.8863)
        assert 60000 < dist < 80000  # roughly 68 km

    @pytest.mark.asyncio
    async def test_locus_location_tracking(self, mock_locus):
        payload_sf = {
            "device_id": "phone-1",
            "lat": 37.7750, 
            "lon": -122.4195,
            "timestamp": "2023-01-01T12:00:00Z"
        }
        await mock_locus._handle_location(payload_sf)
        
        loc = mock_locus.get_device_location("phone-1")
        assert loc is not None
        assert loc.lat == 37.7750
        
        assert mock_locus.is_device_in_fence("phone-1", "home") is True
        assert mock_locus.is_device_in_fence("phone-1", "work") is False

    @pytest.mark.asyncio
    async def test_triangulation_task(self, mock_locus):
        task = TriangulationTask(locus=mock_locus)
        assert task.name() == "triangulation"
        
        # Test run propagates without errors
        await task.run([MagicMock()])
