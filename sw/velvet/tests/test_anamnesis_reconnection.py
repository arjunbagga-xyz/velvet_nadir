import pytest
import asyncio
from velvet.config import get_config
from velvet.shen.jing import Jing
from velvet.shen.mesh_memory import MeshMemorySync
from velvet.privacy import PrivacyGuard


class MockFabric:
    """Mock Zenoh fabric broker to capture pub/sub events during sync."""
    def __init__(self):
        self.channels = {}
        self.published = []

    async def subscribe(self, topic, callback):
        self.channels[topic] = callback

    async def unsubscribe(self, topic, callback):
        if topic in self.channels:
            del self.channels[topic]

    async def publish(self, topic, payload):
        self.published.append((topic, payload))
        # Trigger any direct subscribers (simulate local loopback)
        if topic in self.channels:
            # Wrap payload in a mock msg object
            class MockMsg:
                def __init__(self, p):
                    self.payload = p
            asyncio.create_task(self.channels[topic](MockMsg(payload)))


@pytest.fixture
def clean_jing(tmp_path, monkeypatch):
    """Fixture creating a fresh Jing instance with a temp SQLite ColdStore path."""
    Jing._instance = None
    monkeypatch.setattr(get_config().memory, "tartarus_db_path", tmp_path / "tartarus_test.db")
    jing = Jing()
    return jing


@pytest.fixture
def sync_node(clean_jing, monkeypatch):
    """Fixture wrapping Jing inside MeshMemorySync with a MockFabric."""
    fabric = MockFabric()
    monkeypatch.setattr("velvet.fabric.get_fabric", lambda: fabric)
    
    # Mock PrivacyGuard to always trust
    class MockPrivacy:
        def can_sync_memory(self, device_id):
            return True
            
    sync = MeshMemorySync(jing=clean_jing, privacy_guard=MockPrivacy())
    sync._fabric = fabric
    sync._running = True
    return sync, fabric


@pytest.mark.asyncio
async def test_sutra_causal_logging(clean_jing):
    """Verify that storing memories adds them to the causal log (Sutra)."""
    assert clean_jing.get_merkle_root() == "empty"
    
    # Save a memory
    await clean_jing.remember("User wants coffee.", role="user")
    
    # Check version vector
    vv = clean_jing.get_version_vector()
    device_id = get_config().device_id
    assert vv[device_id] == 1
    
    # Merkle root should now be updated (not empty)
    root = clean_jing.get_merkle_root()
    assert root != "empty"
    assert len(root) == 64  # SHA-256 hex string length


@pytest.mark.asyncio
async def test_anamnesis_handshake_flow(sync_node, clean_jing, monkeypatch):
    """Verify cryptographic handshake verification, delta discovery, and Syzygy sync."""
    sync, fabric = sync_node
    
    # Enable HMAC verification setting
    monkeypatch.setattr(get_config().security, "mesh_secret", "supersecret")
    monkeypatch.setattr(get_config().security, "require_signed_messages", True)
    
    # Node 1: Add a local memory (version = 1)
    await clean_jing.remember("Memory A", role="user")
    
    # Create subscriptions
    await sync.start()
    
    # Simulate receiving handshake from Node 2 (which is lagging, version = 0)
    node2_tin_phu = {
        "version_vector": {},
        "merkle_root": "empty",
    }
    
    # Construct invalid signature envelope first
    invalid_envelope = {
        "source_device": "node2",
        "target_device": get_config().device_id,
        "tin_phu": node2_tin_phu,
        "signature": "invalid_hmac_hex"
    }
    
    # Trigger receipt of invalid handshake
    await fabric.publish("velvet/anamnesis/handshake", invalid_envelope)
    await asyncio.sleep(0.1)
    
    # Verify no response was sent back due to signature rejection
    assert not any(t == "velvet/anamnesis/sync/response" for t, _ in fabric.published if t != "velvet/anamnesis/handshake")
    
    # Now construct VALID signature handshake
    valid_payload = {
        "source_device": "node2",
        "target_device": get_config().device_id,
        "tin_phu": node2_tin_phu,
    }
    valid_sig = sync._sign_payload(valid_payload, "supersecret")
    valid_envelope = {**valid_payload, "signature": valid_sig}
    
    # Trigger receipt of valid handshake
    await fabric.publish("velvet/anamnesis/handshake", valid_envelope)
    await asyncio.sleep(0.1)
    
    # Verify Node 1 detected that Node 2 was lagging, and sent missing sutras in sync/response
    response_msg = next((p for t, p in fabric.published if t == "velvet/anamnesis/sync/response"), None)
    assert response_msg is not None
    assert response_msg["target_device"] == "node2"
    assert len(response_msg["sutras"]) == 1
    assert response_msg["sutras"][0]["payload"]["fact"] == "Memory A"


@pytest.mark.asyncio
async def test_reconnection_lagging_pull(sync_node, clean_jing, monkeypatch):
    """Verify that a lagging node requests delta and merges peer response structurally."""
    sync, fabric = sync_node
    monkeypatch.setattr(get_config().security, "mesh_secret", "supersecret")
    
    await sync.start()
    
    # Simulate receiving handshake from Node 2 (which is AHEAD, version = 1)
    node2_vector = {"node2": 1}
    node2_sutras = [
        {
            "id": "node2:1",
            "device_id": "node2",
            "version_num": 1,
            "hash": "somehash",
            "action": "add",
            "payload": {"fact": "Memory from Node 2", "role": "user", "metadata": {}},
            "timestamp": "2026-07-06T12:00:00Z"
        }
    ]
    
    node2_tin_phu = {
        "version_vector": node2_vector,
        "merkle_root": "merkle_val_node2",
    }
    
    valid_payload = {
        "source_device": "node2",
        "target_device": get_config().device_id,
        "tin_phu": node2_tin_phu,
    }
    valid_sig = sync._sign_payload(valid_payload, "supersecret")
    envelope = {**valid_payload, "signature": valid_sig}
    
    # Trigger handshake receipt
    await fabric.publish("velvet/anamnesis/handshake", envelope)
    await asyncio.sleep(0.1)
    
    # Verify we requested delta
    request_msg = next((p for t, p in fabric.published if t == "velvet/anamnesis/sync/request"), None)
    assert request_msg is not None
    assert request_msg["target_device"] == "node2"
    assert request_msg["version_vector"] == {}
    
    # Now simulate Node 2 returning the sync response delta
    response_payload = {
        "source_device": "node2",
        "target_device": get_config().device_id,
        "sutras": node2_sutras
    }
    response_sig = sync._sign_payload(response_payload, "supersecret")
    response_envelope = {**response_payload, "signature": response_sig}
    
    await fabric.publish("velvet/anamnesis/sync/response", response_envelope)
    await asyncio.sleep(0.1)
    
    # Verify the lagging node structurally merged the transaction (Syzygy)
    my_vector = clean_jing.get_version_vector()
    assert my_vector["node2"] == 1
    
    # Check memory is updated
    memories = await clean_jing.recall("Memory from Node 2", deep=True)
    assert any("Memory from Node 2" in m for m in memories)
