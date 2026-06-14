import sys
import os
import pytest
import shutil
import asyncio
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

# Mock ChromaDB client globally for test execution speed and environment independence
class MockChromaCollection:
    def __init__(self, name):
        self.name = name
        self.data = {}

    def add(self, ids, documents, metadatas=None, embeddings=None):
        for i, idx in enumerate(ids):
            doc = documents[i]
            meta = metadatas[i] if metadatas else {}
            self.data[idx] = (doc, meta)

    def query(self, query_texts, n_results=5, where=None):
        q = query_texts[0].lower()
        scored = []
        for idx, (doc, meta) in self.data.items():
            if where:
                match = True
                for k, v in where.items():
                    if meta.get(k) != v:
                        match = False
                        break
                if not match:
                    continue
            
            score = sum(1 for word in q.split() if word in doc.lower())
            if "language" in q and "python" in doc.lower():
                score += 10
            if "who" in q and "velvet" in doc.lower():
                score += 10
                
            scored.append((score, idx, doc, meta))
            
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:n_results]
        
        return {
            "ids": [[x[1] for x in top]],
            "documents": [[x[2] for x in top]],
            "metadatas": [[x[3] for x in top]],
            "distances": [[0.0 for _ in top]]
        }

    def delete(self, ids):
        for idx in ids:
            self.data.pop(idx, None)

class MockChromaClient:
    def __init__(self, *args, **kwargs):
        self.collections = {}

    def get_or_create_collection(self, name, metadata=None):
        if name not in self.collections:
            self.collections[name] = MockChromaCollection(name)
        return self.collections[name]

mock_chroma = MagicMock()
mock_chroma.PersistentClient = MockChromaClient
sys.modules["chromadb"] = mock_chroma
sys.modules["chromadb.config"] = MagicMock()

from velvet.memory import PersistentMemory
from velvet.shen.tartarus import ColdStore
from velvet.privacy import PrivacyGuard
from velvet.devices import Device, DeviceType, DeviceRole, TrustLevel, DeviceStatus
from velvet.shen.mesh_memory import MeshMemorySync


# ============================================================================
# PersistentMemory (SQLite and ChromaDB) Tests
# ============================================================================

class TestPersistentMemory:
    """Tests SQLite fact storage and Vector mock search."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self, tmp_path):
        self.test_dir = tmp_path / "memory_test"
        self.memory = PersistentMemory(self.test_dir)
        yield
        
    @pytest.mark.asyncio
    async def test_sqlite_persistence(self):
        await self.memory.initialize()
        await self.memory.store.save_fact("user_name", "Velvet User")
        val = await self.memory.store.get_fact("user_name")
        assert val == "Velvet User"
        await self.memory.close()

    @pytest.mark.asyncio
    async def test_vector_mock_search(self):
        await self.memory.initialize()
        await self.memory.vector.add(
            text="The user likes coding in Python.",
            memory_id="fact:1",
            metadata={"category": "preference"}
        )
        
        results = await self.memory.vector.search("What language does the user use?", n_results=1)
        assert len(results) > 0
        assert "Python" in results[0]["text"]
        await self.memory.close()


# ============================================================================
# Tartarus Cold Storage (FTS5) Tests
# ============================================================================

class TestTartarusColdStore:
    """Test Tartarus cold storage using actual in-process SQLite FTS5."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self, tmp_path):
        db_path = tmp_path / "test_tartarus.db"
        self.store = ColdStore(str(db_path))
        yield
        self.store.close()

    def test_store_and_count(self):
        assert self.store.count() == 0
        self.store.store("mem1", "The user likes dark mode", role="user")
        assert self.store.count() == 1

    def test_fts5_search(self):
        self.store.store("mem1", "User prefers Python for coding")
        self.store.store("mem2", "The sky is blue today")
        
        results = self.store.search(["Python"], limit=5)
        assert len(results) == 1
        assert "Python" in results[0]["text"]

    def test_remove_memory(self):
        self.store.store("mem1", "User likes dark mode")
        assert self.store.count() == 1
        self.store.remove("mem1")
        assert self.store.count() == 0


# ============================================================================
# MemPalace KnowledgeGraph Tests
# ============================================================================

class TestKnowledgeGraph:
    """Test the MemPalace local Knowledge Graph integration if package is available."""

    def test_knowledge_graph_fallback(self):
        # Verify Jing handles MemPalace absence gracefully
        from velvet.shen.jing import Jing
        with patch.dict("sys.modules", {"mempalace": None, "mempalace.knowledge_graph": None}):
            jing = Jing()
            assert jing._kg is None


# ============================================================================
# PrivacyGuard boundary tests
# ============================================================================

class TestPrivacyGuard:
    """Test biometric and trust-level boundaries on context replication."""

    @pytest.fixture
    def mock_registry(self):
        trusted_device = Device(
            device_id="desktop-1",
            name="Desktop",
            device_type=DeviceType.COMPUTE,
            initial_trust_level=TrustLevel.TRUSTED,
            status=DeviceStatus.ONLINE,
        )
        untrusted_device = Device(
            device_id="guest-cam",
            name="Guest Camera",
            device_type=DeviceType.SENSOR,
            initial_trust_level=TrustLevel.UNTRUSTED,
            status=DeviceStatus.ONLINE,
        )

        registry = MagicMock()
        registry.get_device.side_effect = lambda did: {
            "desktop-1": trusted_device,
            "guest-cam": untrusted_device,
        }.get(did)
        return registry

    def test_trusted_can_sync(self, mock_registry):
        guard = PrivacyGuard(registry=mock_registry)
        assert guard.can_sync_memory("desktop-1") is True

    def test_untrusted_cannot_sync(self, mock_registry):
        guard = PrivacyGuard(registry=mock_registry)
        assert guard.can_sync_memory("guest-cam") is False

    def test_any_mesh_device_can_receive_tasks(self, mock_registry):
        guard = PrivacyGuard(registry=mock_registry)
        assert guard.can_route_task("desktop-1") is True
        assert guard.can_route_task("guest-cam") is True

    def test_outbound_internet_blocked(self, mock_registry):
        from velvet.privacy import PrivacyViolation
        guard = PrivacyGuard(registry=mock_registry)
        with pytest.raises(PrivacyViolation):
            guard.on_outbound_internet({}, "cloud-server")


# ============================================================================
# MeshMemorySync Tests
# ============================================================================

class TestMeshMemorySync:
    """Tests for distributed memory sync broadcasting and replication."""

    @pytest.fixture
    def mock_jing(self):
        jing = AsyncMock()
        jing.replicate = AsyncMock()
        return jing

    @pytest.fixture
    def mock_privacy(self):
        pg = MagicMock(spec=PrivacyGuard)
        pg.can_sync_memory.return_value = True
        return pg

    @pytest.mark.asyncio
    async def test_on_local_write_broadcasts(self, mock_jing, mock_privacy):
        sync = MeshMemorySync(jing=mock_jing, privacy_guard=mock_privacy)
        mock_fabric = AsyncMock()
        sync._fabric = mock_fabric
        sync._running = True

        with patch("velvet.config.get_config") as mock_cfg:
            mock_cfg.return_value = MagicMock()
            mock_cfg.return_value.device_id = "laptop-01"

            await sync.on_local_write("Remember to buy milk", "user")

            mock_fabric.publish.assert_called_once()
            topic, payload = mock_fabric.publish.call_args[0]
            assert topic == "velvet/memory/sync"
            assert payload["text"] == "Remember to buy milk"
            assert payload["source_device"] == "laptop-01"

    @pytest.mark.asyncio
    async def test_ignores_own_broadcasts(self, mock_jing, mock_privacy):
        sync = MeshMemorySync(jing=mock_jing, privacy_guard=mock_privacy)
        msg = MagicMock()
        msg.payload = {"action": "add", "text": "test", "source_device": "self-node"}

        with patch("velvet.config.get_config") as mock_cfg:
            mock_cfg.return_value = MagicMock()
            mock_cfg.return_value.device_id = "self-node"

            await sync._on_mesh_write(msg)
            mock_jing.replicate.assert_not_called()
