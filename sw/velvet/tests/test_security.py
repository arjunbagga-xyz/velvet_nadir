import pytest
import textwrap
import os
from pathlib import Path
import numpy as np
from unittest.mock import MagicMock, AsyncMock, patch

from velvet.security import CertManager, sign_message, verify_message, HMAC_SIGNATURE_SIZE
from velvet.config import load_config, SecurityConfig, ZenohConfig
from velvet.fabric import VelvetMessage, FabricError, MessageType
from velvet.errors import VelvetError, VelvetAdapterError, LLMAdapterError
from velvet.basilisk import BasiliskEnclave, sanitize_for_hun
from velvet.skills.basilisk_skill import basilisk_authenticate, basilisk_query
from velvet.devices import DeviceScript

# ============================================================================
# HMAC Message Signing Tests
# ============================================================================

class TestHMAC:
    """Tests for HMAC-SHA256 sign/verify logic."""

    def test_sign_returns_32_bytes(self):
        sig = sign_message(b"hello world", "secret")
        assert isinstance(sig, bytes)
        assert len(sig) == HMAC_SIGNATURE_SIZE

    def test_roundtrip_verify(self):
        payload = b"important mesh data"
        secret = "velvet-mesh-secret-2026"
        sig = sign_message(payload, secret)
        assert verify_message(payload, sig, secret) is True

    def test_wrong_secret_rejects(self):
        payload = b"sensitive memory sync"
        sig = sign_message(payload, "correct-secret")
        assert verify_message(payload, sig, "wrong-secret") is False

    def test_tampered_payload_rejects(self):
        payload = b"original data"
        sig = sign_message(payload, "key")
        tampered = b"modified data"
        assert verify_message(tampered, sig, "key") is False


# ============================================================================
# TLS Certificate Manager Tests
# ============================================================================

class TestCertManager:
    """Tests for CA generation and cert provisioning."""

    def test_ensure_ca_creates_files(self, tmp_path):
        mgr = CertManager(str(tmp_path / "certs"))
        key_path, cert_path = mgr.ensure_ca()
        assert key_path.exists()
        assert cert_path.exists()
        assert key_path.name == "ca.key"
        assert cert_path.name == "ca.crt"

    def test_ensure_ca_idempotent(self, tmp_path):
        mgr = CertManager(str(tmp_path / "certs"))
        k1, c1 = mgr.ensure_ca()
        content_k1 = k1.read_bytes()
        k2, c2 = mgr.ensure_ca()
        assert content_k1 == k2.read_bytes()

    def test_issue_node_cert(self, tmp_path):
        mgr = CertManager(str(tmp_path / "certs"))
        mgr.ensure_ca()
        key_path, cert_path = mgr.issue_node_cert("test-node")
        assert key_path.exists()
        assert cert_path.exists()


# ============================================================================
# Google Adapter Security Gate
# ============================================================================

class TestSecurityConfig:
    """Tests for SecurityConfig defaults and adapter gate."""

    def test_default_blocks_google(self):
        cfg = SecurityConfig()
        assert cfg.allow_cloud_adapters is False

    def test_google_adapter_gate_blocks(self):
        from velvet.llm import create_llm_adapter
        with patch("velvet.config.get_config") as mock_cfg:
            mock_cfg.return_value = MagicMock()
            mock_cfg.return_value.security.allow_google_adapter = False
            mock_cfg.return_value.security.allow_cloud_adapters = False

            with pytest.raises(LLMAdapterError, match="blocked by security"):
                create_llm_adapter("google", api_key="fake")


# ============================================================================
# DeviceScript Sandbox Tests
# ============================================================================

class TestDeviceScriptSandbox:
    """Verify that DeviceScript blocks banned calls/imports and executes safe code."""

    def test_sandbox_blocks_evil(self):
        ds = DeviceScript(action="test", script="result = 2 + 2")
        ds.validate_script()
        res = ds.run_sandboxed()
        assert res["success"] is True
        assert res["result"] == 4
        
        # Evil import: subprocess
        ds.script = "import subprocess\nresult = subprocess.run(['ls'])"
        ds.is_sandboxed = False 
        success, messages = ds.validate_script()
        assert success is False
        assert any("Banned import" in m for m in messages)
        
        # Evil eval
        ds.script = "result = eval('1+1')"
        ds.is_sandboxed = False
        success, messages = ds.validate_script()
        assert success is False
        assert any("Banned call" in m for m in messages)


# ============================================================================
# Error Hierarchy
# ============================================================================

def test_error_hierarchy():
    err = LLMAdapterError("test error")
    assert isinstance(err, VelvetAdapterError)
    assert isinstance(err, VelvetError)


# ============================================================================
# Basilisk Protocol (Secure Enclave & Sanitization)
# ============================================================================

class TestBasiliskProtocol:
    """Tests for secure memory enclave, raw tensor sanitization, and P2P auth."""

    @pytest.mark.asyncio
    async def test_basilisk_enclave_cleanup(self):
        class LargeBlob:
            def __init__(self):
                self.data = np.zeros(100)
                
        blob = LargeBlob()
        async with BasiliskEnclave("test_cleanup") as enclave:
            enclave.track(blob)
            assert len(enclave._tracked_refs) == 1
            assert enclave._tracked_refs[0] is blob
            
        assert len(enclave._tracked_refs) == 0

    @pytest.mark.asyncio
    async def test_sanitize_for_hun(self):
        raw_payload = {
            "verified": True,
            "identity": "owner",
            "face_embedding": np.random.rand(10),
            "frame": np.random.rand(10, 10, 3),
            "nested": {
                "score": 0.99,
                "tensor_data": [1.0, 2.0, 3.0]
            }
        }
        
        safe = sanitize_for_hun(raw_payload)
        assert safe["verified"] is True
        assert safe["identity"] == "owner"
        assert "BASILISK_STRIPPED" in str(safe["face_embedding"])
        assert "BASILISK_STRIPPED" in str(safe["frame"])
        assert safe["nested"]["score"] == 0.99
        assert safe["nested"]["tensor_data"] == "<BASILISK_STRIPPED:list>"

    @pytest.mark.asyncio
    async def test_basilisk_authenticate_skill_success(self):
        mock_fabric = MagicMock()
        mock_fabric.request = AsyncMock()
        
        device_response = VelvetMessage(
            msg_type="mesh/device/cam1/capture_basilisk",
            payload={"frame": np.zeros(10), "source": "cam1"},
            source_device="cam1"
        )
        
        gate_response = VelvetMessage(
            msg_type=MessageType.BASILISK_AUTH.value,
            payload={"verified": True, "node_id": "gateway"},
            source_device="gateway"
        )
        
        mock_fabric.request.side_effect = [[device_response], [gate_response]]
        
        with patch("velvet.skills.basilisk_skill.get_fabric", return_value=mock_fabric):
            result = await basilisk_authenticate(device_id="cam1")
            assert result.success is True
            assert result.data["verified"] is True

    @pytest.mark.asyncio
    async def test_basilisk_query_skill_sanitization(self):
        mock_fabric = MagicMock()
        mock_fabric.request = AsyncMock()
        
        raw_response = {
            "status": "ok",
            "biometrics": [0.1, 0.2, 0.3],
            "log": "Access granted"
        }
        
        device_msg = VelvetMessage(
            msg_type="some/topic",
            payload=raw_response,
            source_device="remote_node"
        )
        
        mock_fabric.request.return_value = [device_msg]
        
        with patch("velvet.skills.basilisk_skill.get_fabric", return_value=mock_fabric):
            result = await basilisk_query(topic="some/topic", payload={"cmd": "get_secrets"})
            assert result.success is True
            assert result.data["status"] == "ok"
            assert result.data["biometrics"] == "<BASILISK_STRIPPED:list>"
            assert result.data["log"] == "Access granted"
