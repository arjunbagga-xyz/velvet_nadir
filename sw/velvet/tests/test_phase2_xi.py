"""
Tests for Phase 2: Xi Core + Fuxi + Agni.

Tests are designed to run WITHOUT Ollama or PowerMem — all external
dependencies are mocked.
"""

import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

from velvet.shen.xi import (
    Xi, XiJournal, BreathTask, ComputeBudget, ConversationTurn
)


# ============================================================================
# ConversationTurn Tests
# ============================================================================

class TestConversationTurn:
    """Test ConversationTurn dataclass."""

    def test_create_turn(self):
        turn = ConversationTurn(
            user_input="What time is it?",
            response="It's 3pm.",
            skill_used="get_time",
            routed_to="po",
        )
        assert turn.user_input == "What time is it?"
        assert turn.skill_used == "get_time"
        assert turn.routed_to == "po"

    def test_to_dict(self):
        turn = ConversationTurn(
            user_input="hello",
            response="Hi there!",
        )
        d = turn.to_dict()
        assert d["user_input"] == "hello"
        assert d["response"] == "Hi there!"
        assert "timestamp" in d

    def test_from_dict(self):
        data = {
            "user_input": "test",
            "response": "reply",
            "skill_used": "greet",
            "routed_to": "hun",
            "timestamp": "2026-01-01T00:00:00",
        }
        turn = ConversationTurn.from_dict(data)
        assert turn.user_input == "test"
        assert turn.skill_used == "greet"
        assert turn.routed_to == "hun"

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


# ============================================================================
# XiJournal Tests
# ============================================================================

class TestXiJournal:
    """Test XiJournal JSONL persistence."""

    @pytest.fixture
    def journal(self, tmp_path):
        return XiJournal(path=tmp_path / "test_journal.jsonl", max_processed=5)

    def test_append_creates_file(self, journal):
        turn = ConversationTurn(user_input="test", response="reply")
        journal.append(turn)
        assert journal.total_lines() == 1

    def test_append_multiple(self, journal):
        for i in range(5):
            journal.append(ConversationTurn(
                user_input=f"q{i}", response=f"a{i}"
            ))
        assert journal.total_lines() == 5

    def test_read_unprocessed_all(self, journal):
        journal.append(ConversationTurn(user_input="q1", response="a1"))
        journal.append(ConversationTurn(user_input="q2", response="a2"))
        turns = journal.read_unprocessed()
        assert len(turns) == 2
        assert turns[0].user_input == "q1"

    def test_mark_processed(self, journal):
        journal.append(ConversationTurn(user_input="q1", response="a1"))
        journal.append(ConversationTurn(user_input="q2", response="a2"))
        journal.mark_processed(1)
        turns = journal.read_unprocessed()
        assert len(turns) == 1
        assert turns[0].user_input == "q2"

    def test_compact_on_threshold(self, journal):
        """Journal should compact when processed count exceeds max_processed."""
        # max_processed = 5
        for i in range(10):
            journal.append(ConversationTurn(
                user_input=f"q{i}", response=f"a{i}"
            ))

        # Process 6 (exceeds threshold of 5)
        journal.mark_processed(6)
        # After compact, file should only have unprocessed lines
        assert journal.total_lines() == 4  # 10 - 6 = 4

    def test_read_empty_journal(self, journal):
        turns = journal.read_unprocessed()
        assert turns == []

    def test_total_lines_empty(self, journal):
        assert journal.total_lines() == 0


# ============================================================================
# ComputeBudget Tests
# ============================================================================

class TestComputeBudget:
    """Test ComputeBudget dataclass."""

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


# ============================================================================
# Xi (Scheduler) Tests
# ============================================================================

class DummyTask(BreathTask):
    """A test BreathTask that records its execution."""
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


class FailingTask(BreathTask):
    """A BreathTask that always fails."""
    def name(self): return "failing"
    def budget(self): return ComputeBudget()
    async def run(self, batch):
        raise RuntimeError("Task exploded!")


class TestXi:
    """Test Xi scheduler."""

    @pytest.fixture
    def xi(self, tmp_path):
        journal = XiJournal(path=tmp_path / "test_journal.jsonl")
        return Xi(journal=journal)

    def test_register_task(self, xi):
        task = DummyTask()
        xi.register_task(task)
        assert "dummy" in xi.task_names

    def test_record_turn(self, xi):
        turn = ConversationTurn(user_input="hi", response="hello")
        xi.record(turn)
        assert xi._journal.total_lines() == 1

    @pytest.mark.asyncio
    async def test_breathe_dispatches_tasks(self, xi):
        task = DummyTask()
        xi.register_task(task)
        xi.record(ConversationTurn(user_input="q1", response="a1"))
        xi.record(ConversationTurn(user_input="q2", response="a2"))

        await xi.breathe()

        assert task.executed is True
        assert len(task.received_batch) == 2

    @pytest.mark.asyncio
    async def test_breathe_empty_batch(self, xi):
        task = DummyTask()
        xi.register_task(task)
        await xi.breathe()
        assert task.executed is False

    @pytest.mark.asyncio
    async def test_breathe_priority_order(self, xi):
        """Tasks should execute in priority order (lowest number first)."""
        execution_order = []

        class OrderedTask(BreathTask):
            def __init__(self, task_name, priority):
                self._name = task_name
                self._priority = priority
            def name(self): return self._name
            def budget(self): return ComputeBudget(priority=self._priority)
            async def run(self, batch):
                execution_order.append(self._name)

        xi.register_task(OrderedTask("low", 10))
        xi.register_task(OrderedTask("high", 1))
        xi.register_task(OrderedTask("medium", 5))

        xi.record(ConversationTurn(user_input="q", response="a"))
        await xi.breathe()

        assert execution_order == ["high", "medium", "low"]

    @pytest.mark.asyncio
    async def test_breathe_marks_processed(self, xi):
        task = DummyTask()
        xi.register_task(task)
        xi.record(ConversationTurn(user_input="q", response="a"))
        await xi.breathe()

        # Second breathe should have no new turns
        task.executed = False
        await xi.breathe()
        assert task.executed is False

    @pytest.mark.asyncio
    async def test_failing_task_doesnt_crash_xi(self, xi):
        """A failing task should not prevent other tasks from running."""
        failing = FailingTask()
        good = DummyTask("good", priority=10)

        xi.register_task(failing)
        xi.register_task(good)
        xi.record(ConversationTurn(user_input="q", response="a"))

        await xi.breathe()  # Should not raise
        assert good.executed is True

    @pytest.mark.asyncio
    async def test_flush(self, xi):
        task = DummyTask()
        xi.register_task(task)
        xi.record(ConversationTurn(user_input="q", response="a"))
        await xi.flush()
        assert task.executed is True


# ============================================================================
# Fuxi Tests
# ============================================================================

class TestFuxi:
    """Test Fuxi consolidation BreathTask."""

    @pytest.fixture
    def fuxi(self):
        from velvet.shen.fuxi import Fuxi
        mock_jing = MagicMock()
        mock_jing.remember = AsyncMock()
        return Fuxi(jing=mock_jing)

    @pytest.mark.asyncio
    async def test_fuxi_name(self, fuxi):
        assert fuxi.name() == "fuxi"

    @pytest.mark.asyncio
    async def test_fuxi_budget(self, fuxi):
        budget = fuxi.budget()
        assert budget.priority == 3
        assert budget.gpu_needed is False

    @pytest.mark.asyncio
    async def test_fuxi_embeds_turns(self, fuxi):
        batch = [
            ConversationTurn(user_input="q1", response="a1", routed_to="hun"),
            ConversationTurn(user_input="q2", response="a2", routed_to="po"),
        ]
        await fuxi.run(batch)
        assert fuxi._jing.remember.call_count == 2

    @pytest.mark.asyncio
    async def test_fuxi_empty_batch(self, fuxi):
        await fuxi.run([])
        fuxi._jing.remember.assert_not_called()


# ============================================================================
# Agni Tests
# ============================================================================

class TestAgni:
    """Test Agni purification BreathTask."""

    @pytest.fixture
    def agni(self, tmp_path):
        from velvet.shen.agni import Agni
        from velvet.shen.tartarus import ColdStore

        mock_jing = MagicMock()
        mock_jing.get_memories_by_retention = AsyncMock(return_value=[])
        mock_jing.forget = AsyncMock()
        mock_jing.remember = AsyncMock()
        mock_jing.reinforce = AsyncMock()
        mock_jing.compact = AsyncMock()

        tartarus = ColdStore(str(tmp_path / "test_tartarus.db"))
        mock_jing._tartarus = tartarus

        return Agni(jing=mock_jing, tartarus=tartarus)

    @pytest.mark.asyncio
    async def test_agni_name(self, agni):
        assert agni.name() == "agni"

    @pytest.mark.asyncio
    async def test_agni_budget(self, agni):
        budget = agni.budget()
        assert budget.priority == 5
        assert budget.gpu_needed is False

    @pytest.mark.asyncio
    async def test_agni_runs_without_error(self, agni):
        """Agni should complete without errors even with empty memories."""
        await agni.run([])  # Empty batch is fine — Agni doesn't use the batch

    @pytest.mark.asyncio
    async def test_agni_archives_cold(self, agni):
        """Agni should archive low-retention, low-importance memories."""
        agni._jing.get_memories_by_retention = AsyncMock(return_value=[
            {"id": "mem1", "text": "Old memory", "retention": 0.05,
             "importance": 0.1, "role": "user", "metadata": {}},
        ])

        await agni.run([])

        # Should have archived to Tartarus
        assert agni._tartarus.count() == 1
        # Should have removed from Jing
        agni._jing.forget.assert_called_once_with("mem1")

    @pytest.mark.asyncio
    async def test_agni_promotes_hot(self, agni):
        """Agni should promote recently-accessed cold memories."""
        # Manually add a cold memory and mark it accessed
        agni._tartarus.store("cold1", "Important but cold", role="user")
        agni._tartarus.mark_accessed("cold1")

        await agni.run([])

        # Should have promoted back to Jing
        agni._jing.remember.assert_called()
        # Should have removed from Tartarus
        assert agni._tartarus.count() == 0
