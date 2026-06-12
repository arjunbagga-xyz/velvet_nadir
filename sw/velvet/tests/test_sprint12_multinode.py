"""
Sprint 12 Multi-Node Tests.

Covers:
- MeshMemorySync: mesh_recall fan-out, recall request/response pipeline
- MeshMemorySync: privacy-gated replication, ignore-self broadcasts
- NativeDriver: asyncssh connect, inject_velvet 3-phase deployment
- NetworkScanner: scan_nmap async port scanner (nmap + fallback)
- Config: TOML deep-merge priority (File < Env < Override)
"""

import asyncio
import json
import pytest
import textwrap
import uuid
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
from dataclasses import dataclass

from velvet.shen.mesh_memory import MeshMemorySync
from velvet.privacy import PrivacyGuard
from velvet.scan import NetworkScanner, ScannedDevice
from velvet.config import load_config
from velvet.drivers import NativeDriver, RTSPDriver, DeviceDriver
from velvet.devices import ConnectionInfo, ConnectionMethod


# ============================================================================
# MeshMemorySync
# ============================================================================

class TestMeshMemorySync:
    """Tests for distributed memory sync and recall."""

    @pytest.fixture
    def mock_jing(self):
        """Mock Jing (memory store) with recall and replicate."""
        jing = AsyncMock()
        jing.recall = AsyncMock(return_value=[
            {"text": "I like coffee", "timestamp": "2026-04-01"},
            {"text": "Project deadline is Friday", "timestamp": "2026-04-02"},
        ])
        jing.replicate = AsyncMock()
        return jing

    @pytest.fixture
    def mock_privacy(self):
        """PrivacyGuard that trusts everything."""
        pg = MagicMock(spec=PrivacyGuard)
        pg.can_sync_memory = MagicMock(return_value=True)
        return pg

    @pytest.fixture
    def mock_privacy_untrusted(self):
        """PrivacyGuard that trusts nothing."""
        pg = MagicMock(spec=PrivacyGuard)
        pg.can_sync_memory = MagicMock(return_value=False)
        return pg

    @pytest.mark.asyncio
    async def test_on_local_write_broadcasts(self, mock_jing, mock_privacy):
        """Local writes trigger a fabric publish to sync topic."""
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
        """MeshMemorySync ignores memory writes from its own device."""
        sync = MeshMemorySync(jing=mock_jing, privacy_guard=mock_privacy)

        msg = MagicMock()
        msg.payload = {"action": "add", "text": "test", "source_device": "self-node"}

        with patch("velvet.config.get_config") as mock_cfg:
            mock_cfg.return_value = MagicMock()
            mock_cfg.return_value.device_id = "self-node"

            await sync._on_mesh_write(msg)

            mock_jing.replicate.assert_not_called()

    @pytest.mark.asyncio
    async def test_replicates_from_trusted_peer(self, mock_jing, mock_privacy):
        """Replicates memory from a trusted peer."""
        sync = MeshMemorySync(jing=mock_jing, privacy_guard=mock_privacy)

        msg = MagicMock()
        msg.payload = {"action": "add", "text": "shared memory", "source_device": "jetson-01"}

        with patch("velvet.config.get_config") as mock_cfg:
            mock_cfg.return_value = MagicMock()
            mock_cfg.return_value.device_id = "laptop-01"

            await sync._on_mesh_write(msg)

            mock_jing.replicate.assert_called_once()

    @pytest.mark.asyncio
    async def test_blocks_untrusted_peer(self, mock_jing, mock_privacy_untrusted):
        """Blocks memory replication from untrusted peers."""
        sync = MeshMemorySync(jing=mock_jing, privacy_guard=mock_privacy_untrusted)

        msg = MagicMock()
        msg.payload = {"action": "add", "text": "evil data", "source_device": "rogue-node"}

        with patch("velvet.config.get_config") as mock_cfg:
            mock_cfg.return_value = MagicMock()
            mock_cfg.return_value.device_id = "laptop-01"

            await sync._on_mesh_write(msg)

            mock_jing.replicate.assert_not_called()

    @pytest.mark.asyncio
    async def test_recall_request_handler(self, mock_jing, mock_privacy):
        """Incoming recall requests trigger local recall and response publish."""
        sync = MeshMemorySync(jing=mock_jing, privacy_guard=mock_privacy)
        mock_fabric = AsyncMock()
        sync._fabric = mock_fabric

        msg = MagicMock()
        msg.payload = {
            "query": "coffee",
            "limit": 5,
            "reply_to": "velvet/memory/recall/response/abc-123",
            "request_id": "abc-123",
            "source_device": "jetson-01",
        }
        msg.source_device = "jetson-01"

        with patch("velvet.config.get_config") as mock_cfg:
            mock_cfg.return_value = MagicMock()
            mock_cfg.return_value.device_id = "laptop-01"

            await sync._on_mesh_recall_request(msg)

            mock_jing.recall.assert_called_once_with("coffee", k=5)
            mock_fabric.publish.assert_called_once()
            topic = mock_fabric.publish.call_args[0][0]
            assert topic == "velvet/memory/recall/response/abc-123"

    @pytest.mark.asyncio
    async def test_mesh_recall_fanout(self, mock_jing, mock_privacy):
        """mesh_recall publishes a request, subscribes/unsubscribes, and returns results."""
        sync = MeshMemorySync(jing=mock_jing, privacy_guard=mock_privacy)

        # Build a mock fabric that simulates a peer responding
        mock_fabric = AsyncMock()
        captured_handlers = {}

        async def fake_subscribe(topic, handler):
            captured_handlers[topic] = handler

        async def fake_publish(topic, payload):
            # Simulate a peer responding after a tiny delay
            if "recall/request" in topic:
                # Find the reply handler and call it
                reply_topic = payload.get("reply_to")
                if reply_topic and reply_topic in captured_handlers:
                    response_msg = MagicMock()
                    response_msg.payload = {
                        "request_id": payload["request_id"],
                        "source_device": "peer-node",
                        "results": [{"text": "peer memory about coffee"}],
                    }
                    await captured_handlers[reply_topic](response_msg)

        mock_fabric.subscribe = AsyncMock(side_effect=fake_subscribe)
        mock_fabric.publish = AsyncMock(side_effect=fake_publish)
        mock_fabric.unsubscribe = AsyncMock()
        sync._fabric = mock_fabric

        with patch("velvet.config.get_config") as mock_cfg:
            mock_cfg.return_value = MagicMock()
            mock_cfg.return_value.device_id = "laptop-01"

            # Monkey-patch sleep to avoid 2s wait in tests
            with patch("asyncio.sleep", new_callable=AsyncMock):
                results = await sync.mesh_recall("coffee", limit=5)

        assert len(results) >= 1
        assert any("coffee" in str(r) for r in results)
        mock_fabric.unsubscribe.assert_called_once()

    @pytest.mark.asyncio
    async def test_mesh_recall_deduplicates(self, mock_jing, mock_privacy):
        """mesh_recall deduplicates results from multiple peers."""
        sync = MeshMemorySync(jing=mock_jing, privacy_guard=mock_privacy)

        mock_fabric = AsyncMock()
        captured_handlers = {}

        async def fake_subscribe(topic, handler):
            captured_handlers[topic] = handler

        async def fake_publish(topic, payload):
            if "recall/request" in topic:
                reply_topic = payload.get("reply_to")
                if reply_topic and reply_topic in captured_handlers:
                    # Two peers return the same result
                    for peer in ["peer-a", "peer-b"]:
                        response_msg = MagicMock()
                        response_msg.payload = {
                            "source_device": peer,
                            "results": [{"text": "duplicate memory"}],
                        }
                        await captured_handlers[reply_topic](response_msg)

        mock_fabric.subscribe = AsyncMock(side_effect=fake_subscribe)
        mock_fabric.publish = AsyncMock(side_effect=fake_publish)
        mock_fabric.unsubscribe = AsyncMock()
        sync._fabric = mock_fabric

        with patch("velvet.config.get_config") as mock_cfg:
            mock_cfg.return_value = MagicMock()
            mock_cfg.return_value.device_id = "laptop-01"

            with patch("asyncio.sleep", new_callable=AsyncMock):
                results = await sync.mesh_recall("memory", limit=10)

        # Should deduplicate — only 1 unique result
        assert len(results) == 1


# ============================================================================
# NativeDriver (asyncssh)
# ============================================================================

class TestNativeDriver:
    """Tests for NativeDriver SSH deployment."""

    @pytest.mark.asyncio
    async def test_connect_non_ssh_rejects(self):
        """NativeDriver only supports SSH; other methods return False."""
        driver = NativeDriver()
        info = ConnectionInfo(method=ConnectionMethod.HTTP_API, address="1.2.3.4")
        result = await driver.connect(info)
        assert result is False

    @pytest.mark.asyncio
    async def test_get_status_offline_when_disconnected(self):
        """Returns offline status when not connected."""
        driver = NativeDriver()
        status = await driver.get_status()
        assert status["status"] == "offline"

    @pytest.mark.asyncio
    async def test_inject_velvet_fails_without_connection(self):
        """inject_velvet returns False when not connected."""
        driver = NativeDriver()
        result = await driver.inject_velvet("test-node")
        assert result is False

    @pytest.mark.asyncio
    async def test_connect_with_asyncssh_mock(self):
        """Successful SSH connection via mocked asyncssh."""
        driver = NativeDriver()
        info = ConnectionInfo(
            method=ConnectionMethod.SSH,
            address="192.168.1.100",
            port=22,
            username="pi",
            password="raspberry",
        )

        mock_conn = AsyncMock()
        mock_asyncssh = MagicMock()
        mock_asyncssh.connect = AsyncMock(return_value=mock_conn)

        with patch.dict("sys.modules", {"asyncssh": mock_asyncssh}):
            # Re-import to pick up the mock
            import importlib
            import velvet.drivers
            importlib.reload(velvet.drivers)
            from velvet.drivers import NativeDriver as ReloadedDriver

            driver2 = ReloadedDriver()
            result = await driver2.connect(info)

        assert result is True
        assert driver2._connected is True

    @pytest.mark.asyncio
    async def test_disconnect_closes_connection(self):
        """disconnect() closes the SSH connection and resets state."""
        driver = NativeDriver()
        mock_conn = AsyncMock()
        mock_conn.close = MagicMock()
        mock_conn.wait_closed = AsyncMock()
        driver._conn = mock_conn
        driver._connected = True

        await driver.disconnect()

        mock_conn.close.assert_called_once()
        assert driver._connected is False
        assert driver._conn is None


# ============================================================================
# RTSPDriver
# ============================================================================

class TestRTSPDriver:
    """Tests for RTSP camera driver."""

    @pytest.mark.asyncio
    async def test_connect_constructs_url(self):
        """connect builds RTSP URL from connection info."""
        driver = RTSPDriver()
        info = ConnectionInfo(
            method=ConnectionMethod.HTTP_API,
            address="192.168.1.50",
            port=554,
            username="admin",
            password="pass123",
        )
        result = await driver.connect(info)
        assert result is True
        assert "admin:pass123@192.168.1.50" in driver._url

    @pytest.mark.asyncio
    async def test_status_when_connected(self):
        """Status shows streaming when connected."""
        driver = RTSPDriver()
        driver._connected = True
        status = await driver.get_status()
        assert status["status"] == "streaming"
        assert status["fps"] == 30


# ============================================================================
# NetworkScanner (Async Port Scan)
# ============================================================================

class TestNetworkScanner:
    """Tests for async port scanning in scan.py."""

    @pytest.mark.asyncio
    async def test_scan_nmap_fallback_no_nmap(self):
        """When nmap is not installed, falls back to asyncio socket scan."""
        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError("nmap")):
            # Also mock asyncio.open_connection to simulate closed ports
            with patch("asyncio.open_connection", side_effect=OSError("refused")):
                results = await NetworkScanner.scan_nmap("192.168.1.1", ports=[22, 80])
                assert results["ip"] == "192.168.1.1"
                assert results["open_ports"] == []

    @pytest.mark.asyncio
    async def test_scan_nmap_fallback_finds_open_port(self):
        """Fallback socket scan detects an open port."""
        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError("nmap")):
            # Port 22 is "open" (returns reader/writer), port 80 is closed
            mock_writer = AsyncMock()
            mock_writer.close = MagicMock()
            mock_writer.wait_closed = AsyncMock()

            call_count = 0

            async def fake_open_connection(ip, port):
                if port == 22:
                    return AsyncMock(), mock_writer
                raise OSError("refused")

            with patch("asyncio.open_connection", side_effect=fake_open_connection), \
                 patch("asyncio.wait_for", wraps=asyncio.wait_for):
                results = await NetworkScanner.scan_nmap("192.168.1.1", ports=[22, 80])

        assert 22 in results["open_ports"]
        assert 80 not in results["open_ports"]

    @pytest.mark.asyncio
    async def test_scan_nmap_with_real_nmap_output(self):
        """Parses real nmap output format correctly."""
        fake_nmap_output = textwrap.dedent("""\
            Starting Nmap 7.94 ( https://nmap.org )
            Nmap scan report for 192.168.1.100
            PORT     STATE  SERVICE
            22/tcp   open   ssh
            80/tcp   closed http
            7447/tcp open   zenoh
        """).encode()

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(fake_nmap_output, b""))
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            results = await NetworkScanner.scan_nmap("192.168.1.100", ports=[22, 80, 7447])

        assert 22 in results["open_ports"]
        assert 7447 in results["open_ports"]
        assert 80 not in results["open_ports"]
        assert results["services"][22] == "ssh"
        assert results["services"][7447] == "zenoh"


# ============================================================================
# Config TOML Deep Merge
# ============================================================================

class TestConfigDeepMerge:
    """Tests for config loading priority."""

    def test_override_beats_file(self, tmp_path):
        """Manual overrides take highest priority over TOML."""
        toml_path = tmp_path / "velvet.toml"
        toml_path.write_text(textwrap.dedent('''
            [velvet]
            device_id = "toml-id"
        '''))

        cfg = load_config(config_path=toml_path, device_id="override-id")
        assert cfg.device_id == "override-id"

    def test_nested_override(self, tmp_path):
        """Override works for nested subsystem configs."""
        toml_path = tmp_path / "velvet.toml"
        toml_path.write_text(textwrap.dedent('''
            [velvet.security]
            mesh_secret = "toml-secret"
        '''))

        cfg = load_config(
            config_path=toml_path,
            security={"mesh_secret": "override-secret"}
        )
        assert cfg.security.mesh_secret == "override-secret"

    def test_file_defaults_preserved(self, tmp_path):
        """Fields not overridden keep their file/default values."""
        toml_path = tmp_path / "velvet.toml"
        toml_path.write_text(textwrap.dedent('''
            [velvet]
            device_id = "toml-node"
            [velvet.llm]
            adapter = "vllm"
            model = "llama-70b"
        '''))

        cfg = load_config(config_path=toml_path)
        assert cfg.device_id == "toml-node"
        assert cfg.llm.adapter == "vllm"
        assert cfg.llm.model == "llama-70b"
        # Default preserved
        assert cfg.llm.base_url == "http://localhost:11434"


# ============================================================================
# ScannedDevice Dataclass
# ============================================================================

class TestScannedDevice:
    """Tests for the ScannedDevice model."""

    def test_basic_creation(self):
        """ScannedDevice initializes with required fields."""
        d = ScannedDevice(id="192.168.1.1", name="Test Device", scan_type="network")
        assert d.id == "192.168.1.1"
        assert d.ports == []
        assert d.services == []

    def test_with_metadata(self):
        """ScannedDevice accepts optional metadata."""
        d = ScannedDevice(
            id="ab:cd:ef:12:34:56",
            name="ESP32 Light",
            scan_type="ble",
            rssi=-45,
            metadata={"firmware": "v2.1"},
        )
        assert d.rssi == -45
        assert d.metadata["firmware"] == "v2.1"
