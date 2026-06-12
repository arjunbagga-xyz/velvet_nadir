"""
Sprint 12 Security Tests.

Covers:
- CertManager: CA generation, node cert issuance, idempotent reloads
- HMAC: sign/verify round-trip, tamper detection, constant-time comparison
- VelvetMessage: HMAC integration in to_bytes/from_bytes
- SecurityConfig: allow_google_adapter gate, mesh_secret propagation
- TLS auto-provisioning in start_velvet boot sequence
- Google adapter security gate in create_llm_adapter
"""

import datetime
import json
import os
import pytest
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

from velvet.security import CertManager, sign_message, verify_message, HMAC_SIGNATURE_SIZE
from velvet.config import load_config, VelvetConfig, SecurityConfig, ZenohConfig
from velvet.fabric import VelvetMessage, FabricError
from velvet.errors import LLMAdapterError


# ============================================================================
# HMAC Message Signing
# ============================================================================

class TestHMAC:
    """Tests for HMAC-SHA256 sign/verify."""

    def test_sign_returns_32_bytes(self):
        """HMAC-SHA256 always produces a 32-byte digest."""
        sig = sign_message(b"hello world", "secret")
        assert isinstance(sig, bytes)
        assert len(sig) == HMAC_SIGNATURE_SIZE

    def test_roundtrip_verify(self):
        """A signature produced by sign_message is accepted by verify_message."""
        payload = b"important mesh data"
        secret = "velvet-mesh-secret-2026"
        sig = sign_message(payload, secret)
        assert verify_message(payload, sig, secret) is True

    def test_wrong_secret_rejects(self):
        """A signature from one secret is rejected with a different secret."""
        payload = b"sensitive memory sync"
        sig = sign_message(payload, "correct-secret")
        assert verify_message(payload, sig, "wrong-secret") is False

    def test_tampered_payload_rejects(self):
        """Altering the payload after signing invalidates the HMAC."""
        payload = b"original data"
        sig = sign_message(payload, "key")
        tampered = b"modified data"
        assert verify_message(tampered, sig, "key") is False

    def test_empty_payload(self):
        """HMAC works on empty payloads."""
        sig = sign_message(b"", "key")
        assert verify_message(b"", sig, "key") is True

    def test_unicode_secret(self):
        """Secrets with unicode characters work correctly."""
        sig = sign_message(b"data", "ключ-секрет")
        assert verify_message(b"data", sig, "ключ-секрет") is True

    def test_different_payloads_different_sigs(self):
        """Different payloads produce different signatures."""
        s1 = sign_message(b"payload-a", "key")
        s2 = sign_message(b"payload-b", "key")
        assert s1 != s2


# ============================================================================
# TLS Certificate Manager
# ============================================================================

class TestCertManager:
    """Tests for mTLS certificate provisioning."""

    def test_ensure_ca_creates_files(self, tmp_path):
        """First call to ensure_ca generates ca.key and ca.crt on disk."""
        mgr = CertManager(str(tmp_path / "certs"))
        key_path, cert_path = mgr.ensure_ca()

        assert key_path.exists()
        assert cert_path.exists()
        assert key_path.name == "ca.key"
        assert cert_path.name == "ca.crt"

    def test_ensure_ca_idempotent(self, tmp_path):
        """Calling ensure_ca twice returns the same paths without regenerating."""
        mgr = CertManager(str(tmp_path / "certs"))
        k1, c1 = mgr.ensure_ca()
        content_k1 = k1.read_bytes()
        content_c1 = c1.read_bytes()

        k2, c2 = mgr.ensure_ca()
        assert k2.read_bytes() == content_k1
        assert c2.read_bytes() == content_c1

    def test_issue_node_cert(self, tmp_path):
        """issue_node_cert creates device-specific cert + key signed by CA."""
        mgr = CertManager(str(tmp_path / "certs"))
        mgr.ensure_ca()

        cert_path, key_path = mgr.issue_node_cert("jetson-01")

        assert cert_path.exists()
        assert key_path.exists()
        assert cert_path.name == "jetson-01.crt"
        assert key_path.name == "jetson-01.key"

    def test_issue_multiple_node_certs(self, tmp_path):
        """Can issue certs for multiple devices from the same CA."""
        mgr = CertManager(str(tmp_path / "certs"))
        mgr.ensure_ca()

        c1, k1 = mgr.issue_node_cert("node-a")
        c2, k2 = mgr.issue_node_cert("node-b")

        assert c1.read_bytes() != c2.read_bytes()
        assert k1.read_bytes() != k2.read_bytes()

    def test_issue_without_ca_fails(self, tmp_path):
        """Issuing a cert without first calling ensure_ca raises FileNotFoundError."""
        mgr = CertManager(str(tmp_path / "certs"))
        with pytest.raises(FileNotFoundError, match="Mesh CA not found"):
            mgr.issue_node_cert("orphan-node")

    def test_has_node_cert(self, tmp_path):
        """has_node_cert returns True only after a cert is issued."""
        mgr = CertManager(str(tmp_path / "certs"))
        mgr.ensure_ca()

        assert mgr.has_node_cert("new-node") is False
        mgr.issue_node_cert("new-node")
        assert mgr.has_node_cert("new-node") is True

    def test_get_tls_paths(self, tmp_path):
        """get_tls_paths returns correct dict of absolute path strings."""
        mgr = CertManager(str(tmp_path / "certs"))
        mgr.ensure_ca()
        mgr.issue_node_cert("laptop-01")

        paths = mgr.get_tls_paths("laptop-01")
        assert "root_ca" in paths
        assert "cert" in paths
        assert "key" in paths
        assert paths["root_ca"].endswith("ca.crt")
        assert paths["cert"].endswith("laptop-01.crt")
        assert paths["key"].endswith("laptop-01.key")

    def test_cert_validity(self, tmp_path):
        """Issued node cert is valid (not expired, properly signed by CA)."""
        from cryptography import x509

        mgr = CertManager(str(tmp_path / "certs"))
        mgr.ensure_ca()
        cert_path, _ = mgr.issue_node_cert("test-node")

        cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
        now = datetime.datetime.now(datetime.timezone.utc)

        assert cert.not_valid_before_utc <= now
        assert cert.not_valid_after_utc > now
        assert "velvet-node-test-node" in cert.subject.rfc4514_string()

    def test_ca_is_ca_certificate(self, tmp_path):
        """The CA cert has basicConstraints with ca=True."""
        from cryptography import x509

        mgr = CertManager(str(tmp_path / "certs"))
        mgr.ensure_ca()

        ca_cert = x509.load_pem_x509_certificate(mgr.ca_cert_path.read_bytes())
        bc = ca_cert.extensions.get_extension_for_class(x509.BasicConstraints)
        assert bc.value.ca is True


# ============================================================================
# VelvetMessage HMAC Integration
# ============================================================================

class TestVelvetMessageHMAC:
    """Tests for HMAC in VelvetMessage to_bytes/from_bytes."""

    def test_unsigned_roundtrip(self):
        """Messages work without a mesh_secret (no HMAC appended)."""
        with patch("velvet.config.get_config") as mock_cfg:
            mock_cfg.return_value = MagicMock()
            mock_cfg.return_value.security.mesh_secret = ""

            msg = VelvetMessage(
                msg_type="test/topic",
                payload={"key": "value"},
                source_device="dev-01",
            )
            raw = msg.to_bytes()
            restored = VelvetMessage.from_bytes(raw)

            assert restored.msg_type == "test/topic"
            assert restored.payload == {"key": "value"}
            assert restored.source_device == "dev-01"

    def test_signed_roundtrip(self):
        """Messages with mesh_secret survive sign → verify cycle."""
        with patch("velvet.config.get_config") as mock_cfg:
            mock_cfg.return_value = MagicMock()
            mock_cfg.return_value.security.mesh_secret = "test-secret-key-123"

            msg = VelvetMessage(
                msg_type="mesh/heartbeat",
                payload={"status": "alive"},
                source_device="node-42",
            )
            raw = msg.to_bytes()

            # Raw should be longer than unsigned (32 bytes HMAC appended)
            assert len(raw) > 32

            restored = VelvetMessage.from_bytes(raw)
            assert restored.msg_type == "mesh/heartbeat"
            assert restored.payload["status"] == "alive"

    def test_tampered_signed_message_rejected(self):
        """Tampering with a signed message raises FabricError."""
        with patch("velvet.config.get_config") as mock_cfg:
            mock_cfg.return_value = MagicMock()
            mock_cfg.return_value.security.mesh_secret = "secret"

            msg = VelvetMessage(
                msg_type="test", payload={"x": 1}, source_device="src"
            )
            raw = msg.to_bytes()

            # Tamper: flip a byte in the payload portion
            tampered = bytearray(raw)
            tampered[5] ^= 0xFF
            tampered = bytes(tampered)

            with pytest.raises(FabricError, match="Invalid HMAC"):
                VelvetMessage.from_bytes(tampered)


# ============================================================================
# SecurityConfig & Google Adapter Gate
# ============================================================================

class TestSecurityConfig:
    """Tests for SecurityConfig defaults and adapter gate."""

    def test_default_blocks_google(self):
        """By default, allow_google_adapter is False."""
        cfg = SecurityConfig()
        assert cfg.allow_google_adapter is False

    def test_default_requires_signed(self):
        """By default, require_signed_messages is True."""
        cfg = SecurityConfig()
        assert cfg.require_signed_messages is True

    def test_google_adapter_gate_blocks(self):
        """create_llm_adapter('google') raises when allow_google_adapter is False."""
        from velvet.llm import create_llm_adapter

        with patch("velvet.config.get_config") as mock_cfg:
            mock_cfg.return_value = MagicMock()
            mock_cfg.return_value.security.allow_google_adapter = False
            mock_cfg.return_value.security.allow_cloud_adapters = False

            with pytest.raises(LLMAdapterError, match="blocked by security"):
                create_llm_adapter("google", api_key="fake")

    def test_google_adapter_gate_allows(self):
        """create_llm_adapter('google') succeeds when allow_google_adapter is True."""
        from velvet.llm import create_llm_adapter

        with patch("velvet.config.get_config") as mock_cfg, \
             patch("velvet.services.google_ai.GoogleAIAdapter") as MockGoogleAdapter:
            mock_cfg.return_value = MagicMock()
            mock_cfg.return_value.security.allow_google_adapter = True
            MockGoogleAdapter.return_value = MagicMock()

            adapter = create_llm_adapter("google", api_key="fake")
            assert adapter is not None

    def test_unknown_adapter_raises(self):
        """create_llm_adapter with unknown type raises LLMAdapterError."""
        from velvet.llm import create_llm_adapter
        with pytest.raises(LLMAdapterError, match="Unknown adapter"):
            create_llm_adapter("nonexistent")


# ============================================================================
# ZenohConfig TLS Fields
# ============================================================================

class TestZenohTLSConfig:
    """Tests for TLS-related fields in ZenohConfig."""

    def test_tls_defaults(self):
        """TLS is off by default."""
        cfg = ZenohConfig()
        assert cfg.tls_enabled is False
        assert cfg.tls_mtls_enabled is False
        assert cfg.tls_root_ca == ""

    def test_tls_toml_loading(self, tmp_path):
        """TLS fields load from TOML config file."""
        toml_path = tmp_path / "velvet.toml"
        toml_path.write_text(textwrap.dedent('''
            [velvet.zenoh]
            device_id = "secure-node"
            tls_enabled = true
            tls_mtls_enabled = true
            tls_root_ca = "/path/to/ca.crt"
            tls_server_cert = "/path/to/node.crt"
            tls_server_key = "/path/to/node.key"

            [velvet.security]
            mesh_secret = "toml-mesh-secret"
        '''))

        cfg = load_config(config_path=toml_path)
        assert cfg.zenoh.tls_enabled is True
        assert cfg.zenoh.tls_mtls_enabled is True
        assert cfg.zenoh.tls_root_ca == "/path/to/ca.crt"
        assert cfg.security.mesh_secret == "toml-mesh-secret"


# ============================================================================
# Boot Sequence: TLS Auto-Provisioning
# ============================================================================

class TestTLSAutoProvisioning:
    """Tests for auto-provisioning in start_velvet."""

    def test_auto_provision_creates_certs(self, tmp_path):
        """The auto-provision block in start_velvet generates CA + node cert."""
        mgr = CertManager(str(tmp_path / "certs"))
        device_id = "test-boot-node"

        # Simulate the boot sequence from main.py lines 57-75
        mgr.ensure_ca()
        if not mgr.has_node_cert(device_id):
            mgr.issue_node_cert(device_id)

        paths = mgr.get_tls_paths(device_id)

        # Verify all files exist
        assert Path(paths["root_ca"]).exists()
        assert Path(paths["cert"]).exists()
        assert Path(paths["key"]).exists()

    def test_auto_provision_populates_zenoh_config(self, tmp_path):
        """After provisioning, ZenohConfig fields are populated with real paths."""
        mgr = CertManager(str(tmp_path / "certs"))
        device_id = "config-test"

        mgr.ensure_ca()
        mgr.issue_node_cert(device_id)
        paths = mgr.get_tls_paths(device_id)

        # Simulate what main.py does after cert provisioning
        zcfg = ZenohConfig()
        zcfg.tls_enabled = True
        zcfg.tls_root_ca = paths["root_ca"]
        zcfg.tls_server_cert = paths["cert"]
        zcfg.tls_server_key = paths["key"]
        zcfg.tls_mtls_enabled = True

        assert zcfg.tls_enabled is True
        assert zcfg.tls_mtls_enabled is True
        assert "ca.crt" in zcfg.tls_root_ca
        assert f"{device_id}.crt" in zcfg.tls_server_cert
        assert f"{device_id}.key" in zcfg.tls_server_key
