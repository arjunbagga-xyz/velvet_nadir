"""
Tests for Phase 1: Jing Memory + Tartarus Cold Store + PrivacyGuard.

Tests are designed to run WITHOUT Ollama or PowerMem — all external
dependencies are mocked.
"""

import pytest
import sqlite3
import json
import tempfile
import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch


# ============================================================================
# Tartarus (ColdStore) Tests — No mocking needed, pure SQLite
# ============================================================================

class TestTartarusColdStore:
    """Test the Tartarus cold storage (SQLite FTS5)."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self, tmp_path):
        """Create a temp ColdStore for each test."""
        from velvet.shen.tartarus import ColdStore
        self.db_path = tmp_path / "test_tartarus.db"
        self.store = ColdStore(str(self.db_path))
        yield
        self.store.close()

    def test_store_and_count(self):
        """Storing a memory should increase count."""
        assert self.store.count() == 0
        self.store.store("mem1", "The user likes dark mode", role="user")
        assert self.store.count() == 1

    def test_store_multiple(self):
        """Store multiple memories."""
        self.store.store("mem1", "User prefers Python for coding")
        self.store.store("mem2", "User lives in Bangalore")
        self.store.store("mem3", "User has a cat named Luna")
        assert self.store.count() == 3

    def test_fts5_search(self):
        """FTS5 search should find memories by keyword."""
        self.store.store("mem1", "User prefers Python for coding")
        self.store.store("mem2", "User lives in Bangalore")
        self.store.store("mem3", "User has a cat named Luna")

        results = self.store.search(["Python"], limit=5)
        assert len(results) >= 1
        assert any("Python" in r["text"] for r in results)

    def test_fts5_search_multiple_keywords(self):
        """FTS5 OR search with multiple keywords."""
        self.store.store("mem1", "User prefers Python for coding")
        self.store.store("mem2", "The sky is blue today")
        self.store.store("mem3", "Python is great for machine learning")

        results = self.store.search(["Python", "coding"], limit=5)
        assert len(results) >= 1

    def test_search_no_results(self):
        """Search for nonexistent term should return empty."""
        self.store.store("mem1", "User likes cats")
        results = self.store.search(["blockchain"], limit=5)
        assert len(results) == 0

    def test_search_empty_keywords(self):
        """Empty keywords should return empty."""
        results = self.store.search([], limit=5)
        assert len(results) == 0

    def test_mark_accessed(self):
        """Marking access should update last_accessed and access_count."""
        self.store.store("mem1", "User likes dark mode")
        self.store.mark_accessed("mem1")

        recently = self.store.get_recently_accessed(days=7)
        assert len(recently) == 1
        assert recently[0]["id"] == "mem1"

    def test_get_recently_accessed_empty(self):
        """No recently accessed if never marked."""
        self.store.store("mem1", "User likes dark mode")
        recently = self.store.get_recently_accessed(days=7)
        assert len(recently) == 0

    def test_remove(self):
        """Remove should delete from cold store."""
        self.store.store("mem1", "User likes dark mode")
        assert self.store.count() == 1
        self.store.remove("mem1")
        assert self.store.count() == 0

    def test_compact(self):
        """Compact should run without error."""
        self.store.store("mem1", "Test")
        self.store.remove("mem1")
        self.store.compact()  # Should not raise

    def test_store_with_metadata(self):
        """Store with metadata dict."""
        self.store.store("mem1", "Test memory", metadata={"source": "phone"})
        results = self.store.search(["Test"], limit=1)
        assert len(results) == 1
        assert results[0]["metadata"]["source"] == "phone"

    def test_upsert_on_duplicate_id(self):
        """Storing with same ID should replace (INSERT OR REPLACE)."""
        self.store.store("mem1", "Version 1")
        self.store.store("mem1", "Version 2")
        assert self.store.count() == 1
        results = self.store.search(["Version"], limit=5)
        # Should have the latest version
        assert any("Version 2" in r["text"] for r in results)


# ============================================================================
# PrivacyGuard Tests
# ============================================================================

class TestPrivacyGuard:
    """Test the privacy perimeter enforcement."""

    @pytest.fixture
    def mock_registry(self):
        """Create a mock registry with trusted and untrusted devices."""
        from velvet.devices import Device, DeviceType, DeviceRole, TrustLevel, DeviceStatus

        trusted_device = Device(
            device_id="desktop-1",
            name="Desktop",
            device_type=DeviceType.COMPUTE,
            trust_level=TrustLevel.TRUSTED,
            status=DeviceStatus.ONLINE,
        )
        untrusted_device = Device(
            device_id="guest-cam",
            name="Guest Camera",
            device_type=DeviceType.SENSOR,
            trust_level=TrustLevel.UNTRUSTED,
            status=DeviceStatus.ONLINE,
        )

        registry = MagicMock()
        registry.get_device.side_effect = lambda did: {
            "desktop-1": trusted_device,
            "guest-cam": untrusted_device,
        }.get(did, None)

        return registry

    @pytest.fixture
    def guard(self, mock_registry):
        from velvet.privacy import PrivacyGuard
        return PrivacyGuard(registry=mock_registry)

    def test_trusted_can_sync(self, guard):
        """Trusted device can receive memory sync."""
        assert guard.can_sync_memory("desktop-1") is True

    def test_untrusted_cannot_sync(self, guard):
        """Untrusted device cannot receive memory sync."""
        assert guard.can_sync_memory("guest-cam") is False

    def test_unknown_cannot_sync(self, guard):
        """Unknown device cannot receive memory sync."""
        assert guard.can_sync_memory("random-device") is False

    def test_any_mesh_device_can_receive_tasks(self, guard):
        """Any mesh device can receive compute tasks (we USE them)."""
        assert guard.can_route_task("desktop-1") is True
        assert guard.can_route_task("guest-cam") is True

    def test_non_mesh_cannot_receive_tasks(self, guard):
        """Non-mesh devices cannot receive tasks."""
        assert guard.can_route_task("internet-server") is False

    def test_outbound_internet_blocked(self, guard):
        """Data leaving the mesh should be blocked."""
        from velvet.privacy import PrivacyViolation

        with pytest.raises(PrivacyViolation):
            guard.on_outbound_internet({}, "cloud-server")

    def test_check_memory_sync_trusted(self, guard):
        """Pre-flight check passes for trusted peer."""
        assert guard.check_memory_sync("desktop-1") is True

    def test_check_memory_sync_untrusted(self, guard):
        """Pre-flight check fails for untrusted peer."""
        assert guard.check_memory_sync("guest-cam") is False


# ============================================================================
# Jing Tests (Mocked PowerMem)
# ============================================================================

class TestJing:
    """Test Jing memory operations with mocked PowerMem."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """Mock PowerMem and config for each test."""
        # Mock PowerMem memory instance
        self.mock_mem = MagicMock()
        self.mock_mem.search.return_value = {
            "results": [
                {"memory": "User likes dark mode", "score": 0.95},
                {"memory": "User prefers Python", "score": 0.85},
            ],
            "relations": ["User → prefers → dark_mode"],
        }
        self.mock_mem.get_all.return_value = []
        self.tmp_path = tmp_path

    def _make_jing(self):
        """Create a Jing instance with mock PowerMem injected (skip _ensure_loaded)."""
        from velvet.shen.jing import Jing
        from velvet.shen.tartarus import ColdStore

        j = Jing.__new__(Jing)
        j._mem = self.mock_mem
        j._tartarus = ColdStore(str(self.tmp_path / "test_tartarus.db"))
        j._ready = True
        return j

    @pytest.mark.asyncio
    async def test_recall_returns_memories(self):
        """Recall should return memory strings from PowerMem."""
        jing = self._make_jing()
        results = await jing.recall("user preferences")
        assert len(results) == 2
        assert "dark mode" in results[0]

    @pytest.mark.asyncio
    async def test_remember_calls_powermem(self):
        """Remember should call PowerMem.add with correct format."""
        jing = self._make_jing()
        await jing.remember("User likes cats", role="user")
        self.mock_mem.add.assert_called_once()
        args, kwargs = self.mock_mem.add.call_args
        assert args[0] == [{"role": "user", "content": "User likes cats"}]

    @pytest.mark.asyncio
    async def test_remember_with_scope(self):
        """Remember with scope should pass scope in metadata."""
        jing = self._make_jing()
        await jing.remember("Secret data", scope="private")
        _, kwargs = self.mock_mem.add.call_args
        assert kwargs.get("metadata", {}).get("scope") == "private"

    @pytest.mark.asyncio
    async def test_graph_query(self):
        """Graph query should return relations."""
        jing = self._make_jing()
        results = await jing.graph_query("user preferences")
        assert len(results) >= 1

    def test_is_persistent(self):
        """Should be persistent when PowerMem is available."""
        jing = self._make_jing()
        assert jing.is_persistent is True

    def test_has_tartarus(self):
        """Should have Tartarus when ColdStore is available."""
        jing = self._make_jing()
        assert jing.has_tartarus is True

    @pytest.mark.asyncio
    async def test_replicate(self):
        """Replicate should call remember with source device metadata."""
        jing = self._make_jing()
        await jing.replicate({
            "text": "Replicated memory",
            "role": "user",
            "source_device": "phone-1",
        })
        self.mock_mem.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_recall_empty_when_no_powermem(self):
        """Recall should return empty list when PowerMem is unavailable."""
        from velvet.shen.jing import Jing
        j = Jing.__new__(Jing)
        j._mem = None
        j._tartarus = None
        j._ready = True
        results = await j.recall("test")
        assert results == []

    @pytest.mark.asyncio
    async def test_deep_recall_searches_tartarus(self):
        """Deep recall should search Tartarus when Aether results are thin."""
        jing = self._make_jing()
        # Make Aether return nothing
        self.mock_mem.search.return_value = {"results": [], "relations": []}
        # Add something to Tartarus
        jing._tartarus.store("cold1", "User lives in Bangalore")

        results = await jing.recall("Bangalore", deep=True)
        assert len(results) >= 1
        assert any("Bangalore" in r for r in results)


# ============================================================================
# Config Tests
# ============================================================================

class TestMemoryConfig:
    """Test MemoryConfig and XiConfig defaults."""

    def test_memory_config_defaults(self):
        from velvet.config import MemoryConfig
        cfg = MemoryConfig()
        assert cfg.embedding_model == "mxbai-embed-large"
        assert cfg.graph_enabled is True
        assert cfg.decay_rate == 0.1
        assert cfg.agent_scope == "public"
        assert cfg.audit_enabled is True

    def test_xi_config_defaults(self):
        from velvet.config import XiConfig
        cfg = XiConfig()
        assert cfg.journal_max_processed == 1000
        assert cfg.flush_on_shutdown is True

    def test_velvet_config_has_memory_and_xi(self):
        from velvet.config import VelvetConfig
        cfg = VelvetConfig()
        assert hasattr(cfg, "memory")
        assert hasattr(cfg, "xi")

    def test_ensure_directories_creates_paths(self, tmp_path):
        from velvet.config import VelvetConfig
        cfg = VelvetConfig(storage={"data_dir": str(tmp_path / "velvet_test")})
        cfg.ensure_directories()
        assert cfg.memory.memory_db_path != ""
        assert cfg.memory.tartarus_db_path != ""
        assert cfg.xi.journal_path != ""
        assert (tmp_path / "velvet_test" / "logs").exists()
