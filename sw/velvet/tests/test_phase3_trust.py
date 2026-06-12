"""
Tests for Phase 3: Trust + Agents + Affinity.
"""

import pytest
import time
from unittest.mock import MagicMock, AsyncMock, patch

from velvet.shen.xi import ConversationTurn


# ============================================================================
# TrustEngine Tests
# ============================================================================

class TestTrustEngine:
    """Test TrustEngine hot cache + Jing backing."""

    @pytest.fixture
    def engine(self):
        from velvet.shen.trust import TrustEngine
        return TrustEngine(jing=MagicMock())

    def test_unknown_domain_should_ask(self, engine):
        """Unknown domain → should ask."""
        assert engine.should_ask("purchases") is True

    @pytest.mark.asyncio
    async def test_record_then_check(self, engine):
        """After recording an approved decision, should not ask."""
        engine._jing.remember = AsyncMock()
        await engine.record_outcome("smart_home", "lights", approved=True)
        # First approval → confidence 0.5, still should ask
        assert engine.should_ask("smart_home", "lights") is True

        # Multiple approvals → confidence rises above 0.8
        for _ in range(5):
            await engine.record_outcome("smart_home", "lights", approved=True)
        assert engine.should_ask("smart_home", "lights") is False

    @pytest.mark.asyncio
    async def test_rejected_still_asks(self, engine):
        """After rejection, should still ask."""
        engine._jing.remember = AsyncMock()
        await engine.record_outcome("purchases", "buy", approved=False)
        assert engine.should_ask("purchases", "buy") is True

    @pytest.mark.asyncio
    async def test_confidence_decreases_on_reject(self, engine):
        """Rejecting should decrease confidence."""
        engine._jing.remember = AsyncMock()
        # Build up confidence
        for _ in range(5):
            await engine.record_outcome("smart_home", "lights", approved=True)
        # Now reject
        await engine.record_outcome("smart_home", "lights", approved=False)
        # Should ask again (confidence dropped)
        assert engine.should_ask("smart_home", "lights") is True

    def test_domain_level_fallback(self, engine):
        """Domain-level decision should work as fallback."""
        from velvet.shen.trust import TrustDecision
        engine._cache["smart_home"] = TrustDecision(
            domain="smart_home", context="", approved=True, confidence=0.9
        )
        assert engine.should_ask("smart_home", "unknown_context") is False

    def test_get_all_decisions(self, engine):
        """Should return all cached decisions."""
        from velvet.shen.trust import TrustDecision
        engine._cache["a"] = TrustDecision(domain="a", context="", approved=True)
        engine._cache["b"] = TrustDecision(domain="b", context="", approved=False)
        assert len(engine.get_all_decisions()) == 2

    def test_parse_trust_text(self):
        from velvet.shen.trust import TrustEngine
        text = "Trust decision: domain=smart_home, context=lights, approved=True, confidence=0.85"
        decision = TrustEngine._parse_trust_text(text)
        assert decision is not None
        assert decision.domain == "smart_home"
        assert decision.approved is True
        assert abs(decision.confidence - 0.85) < 0.01


# ============================================================================
# AgentOrchestrator Tests
# ============================================================================

class TestAgentOrchestrator:
    """Test agent hierarchy and communication rules."""

    @pytest.fixture
    def orch(self):
        from velvet.agents import AgentOrchestrator, AgentIdentity, AgentRole
        o = AgentOrchestrator()

        # Register hierarchy: Yi (orchestrator) → home-mgr (supervisor) → light-ctrl (worker)
        o.register_agent(AgentIdentity(
            agent_id="yi", agent_type="core",
            role=AgentRole.ORCHESTRATOR,
        ))
        o.register_agent(AgentIdentity(
            agent_id="home-mgr", agent_type="home_automation",
            role=AgentRole.SUPERVISOR, parent_id="yi",
        ))
        o.register_agent(AgentIdentity(
            agent_id="health-mgr", agent_type="health",
            role=AgentRole.SUPERVISOR, parent_id="yi",
        ))
        o.register_agent(AgentIdentity(
            agent_id="light-ctrl", agent_type="lights",
            role=AgentRole.WORKER, parent_id="home-mgr",
        ))
        o.register_agent(AgentIdentity(
            agent_id="thermostat", agent_type="hvac",
            role=AgentRole.WORKER, parent_id="home-mgr",
        ))
        return o

    def test_agent_count(self, orch):
        assert orch.agent_count == 5

    def test_orchestrator_can_reach_anyone(self, orch):
        """Orchestrator (Yi) can communicate with all agents."""
        assert orch.can_communicate("yi", "home-mgr") is True
        assert orch.can_communicate("yi", "light-ctrl") is True
        assert orch.can_communicate("yi", "thermostat") is True

    def test_worker_to_supervisor_twoway(self, orch):
        """Worker ↔ Supervisor should be two-way."""
        assert orch.can_communicate("light-ctrl", "home-mgr") is True
        assert orch.can_communicate("home-mgr", "light-ctrl") is True

    def test_worker_to_worker_blocked(self, orch):
        """Worker → Worker should be blocked."""
        assert orch.can_communicate("light-ctrl", "thermostat") is False

    def test_unknown_agent_blocked(self, orch):
        """Unknown agents can't communicate."""
        assert orch.can_communicate("light-ctrl", "nonexistent") is False

    def test_get_children(self, orch):
        children = orch.get_children("home-mgr")
        assert len(children) == 2
        assert any(c.agent_id == "light-ctrl" for c in children)

    def test_get_agents_by_role(self, orch):
        from velvet.agents import AgentRole
        workers = orch.get_agents_by_role(AgentRole.WORKER)
        assert len(workers) == 2

    def test_multi_device_agent(self, orch):
        """An agent can span multiple devices."""
        from velvet.agents import AgentIdentity, AgentRole
        orch.register_agent(AgentIdentity(
            agent_id="distributed-agent",
            agent_type="distributed",
            role=AgentRole.WORKER,
            device_ids=["desktop", "jetson", "phone"],
            parent_id="home-mgr",
        ))
        agent = orch.get_agent("distributed-agent")
        assert len(agent.device_ids) == 3


# ============================================================================
# ModelAffinityTracker Tests
# ============================================================================

class TestModelAffinityTracker:
    """Test model-task affinity tracking."""

    @pytest.fixture
    def tracker(self):
        from velvet.shen.affinity import ModelAffinityTracker
        return ModelAffinityTracker(jing=MagicMock())

    @pytest.mark.asyncio
    async def test_record_and_best(self, tracker):
        """Recording results should update best_model_for."""
        tracker._jing.remember = AsyncMock()
        await tracker.record_task_result("llama3.1:8b", "chat", quality=0.8, latency_ms=200)
        await tracker.record_task_result("gemma2:2b", "chat", quality=0.6, latency_ms=100)
        best = tracker.best_model_for("chat")
        assert best == "llama3.1:8b"

    @pytest.mark.asyncio
    async def test_no_data_returns_none(self, tracker):
        """No data → best_model_for returns None."""
        assert tracker.best_model_for("unknown_task") is None

    @pytest.mark.asyncio
    async def test_rankings(self, tracker):
        """Rankings should be sorted by quality descending."""
        tracker._jing.remember = AsyncMock()
        await tracker.record_task_result("model_a", "code", quality=0.9, latency_ms=500)
        await tracker.record_task_result("model_b", "code", quality=0.7, latency_ms=200)
        await tracker.record_task_result("model_c", "code", quality=0.5, latency_ms=100)

        rankings = tracker.get_rankings("code")
        assert len(rankings) == 3
        assert rankings[0][0] == "model_a"
        assert rankings[2][0] == "model_c"

    @pytest.mark.asyncio
    async def test_cache_bounded(self, tracker):
        """Cache should stay bounded at 100 per task type."""
        tracker._jing.remember = AsyncMock()
        for i in range(150):
            await tracker.record_task_result("model", "stress", quality=0.5, latency_ms=100)
        assert len(tracker._cache["stress"]) == 100

    def test_parse_affinity_text(self):
        from velvet.shen.affinity import ModelAffinityTracker
        text = "Model affinity: model=llama3.1:8b, task=chat, quality=0.85, latency=200ms, device=desktop"
        result = ModelAffinityTracker._parse_affinity_text(text)
        assert result is not None
        assert result.model == "llama3.1:8b"
        assert result.task_type == "chat"
        assert abs(result.quality - 0.85) < 0.01


# ============================================================================
# Inari Tests
# ============================================================================

class TestInari:
    """Test Inari trust cache BreathTask."""

    @pytest.mark.asyncio
    async def test_inari_name(self):
        from velvet.shen.inari import Inari
        inari = Inari()
        assert inari.name() == "inari"

    @pytest.mark.asyncio
    async def test_inari_refreshes_caches(self):
        from velvet.shen.inari import Inari
        mock_trust = MagicMock()
        mock_trust.refresh_cache = AsyncMock()
        mock_affinity = MagicMock()
        mock_affinity.refresh_cache = AsyncMock()

        inari = Inari(trust_engine=mock_trust, affinity_tracker=mock_affinity)
        await inari.run([])

        mock_trust.refresh_cache.assert_called_once()
        mock_affinity.refresh_cache.assert_called_once()

    @pytest.mark.asyncio
    async def test_inari_handles_missing_engines(self):
        from velvet.shen.inari import Inari
        inari = Inari()
        await inari.run([])  # Should not crash


# ============================================================================
# DeviceWatchdog Tests
# ============================================================================

class TestDeviceWatchdog:
    """Test DeviceWatchdog BreathTask."""

    @pytest.fixture
    def watchdog(self):
        from velvet.shen.device_watchdog import DeviceWatchdog
        from velvet.devices import Device, DeviceType, TrustLevel, DeviceStatus

        mock_jing = MagicMock()
        mock_jing.remember = AsyncMock()

        trusted = Device(
            device_id="desktop", name="Desktop",
            device_type=DeviceType.COMPUTE,
            initial_trust_level=TrustLevel.TRUSTED,
            status=DeviceStatus.ONLINE,
        )
        untrusted = Device(
            device_id="guest", name="Guest Camera",
            device_type=DeviceType.SENSOR,
            initial_trust_level=TrustLevel.UNTRUSTED,
            status=DeviceStatus.ONLINE,
        )

        mock_registry = MagicMock()
        mock_registry.get_all_devices.return_value = [trusted, untrusted]

        return DeviceWatchdog(jing=mock_jing, registry=mock_registry)

    @pytest.mark.asyncio
    async def test_watchdog_name(self, watchdog):
        assert watchdog.name() == "device_watchdog"

    @pytest.mark.asyncio
    async def test_watchdog_logs_health(self, watchdog):
        """Should log health for all devices."""
        await watchdog.run([])
        # Should have called remember for both devices
        assert watchdog._jing.remember.call_count >= 2

    @pytest.mark.asyncio
    async def test_watchdog_tracks_untrusted_count(self, watchdog):
        """Should track consecutive healthy checks for untrusted devices."""
        await watchdog.run([])
        assert watchdog._untrusted_healthy_count.get("guest", 0) == 1

    @pytest.mark.asyncio
    async def test_watchdog_suggests_promotion(self, watchdog):
        """After 10+ healthy checks, should suggest trust promotion."""
        watchdog._untrusted_healthy_count["guest"] = 9
        await watchdog.run([])
        # Should now be at 10, triggering a suggestion
        # Check that a trust suggestion was logged
        calls = watchdog._jing.remember.call_args_list
        suggestion_calls = [
            c for c in calls
            if "Trust suggestion" in str(c)
        ]
        assert len(suggestion_calls) >= 1
