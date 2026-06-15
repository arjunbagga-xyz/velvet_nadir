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


# ============================================================================
# Privacy and Mirage Protocol (Sprint 17) Tests
# ============================================================================

class TestPrivacyAndMirage:
    """Tests for PrivacyGuard, PrivacyClassifier, and MirageProxy."""

    def test_get_privacy_guard_singleton(self):
        from velvet.privacy import get_privacy_guard
        g1 = get_privacy_guard()
        g2 = get_privacy_guard()
        assert g1 is g2

    def test_is_safe_to_send_blocks_pii(self):
        from velvet.privacy import get_privacy_guard
        guard = get_privacy_guard()
        # Mock _is_mesh_peer to return False so it treats destination as cloud
        with patch.object(guard, "_is_mesh_peer", return_value=False):
            # SSN pattern in text
            assert guard.is_safe_to_send("My SSN is 123-45-6789", "cloud") is False

    def test_is_safe_to_send_allows_clean_text(self):
        from velvet.privacy import get_privacy_guard
        guard = get_privacy_guard()
        with patch.object(guard, "_is_mesh_peer", return_value=False):
            assert guard.is_safe_to_send("Hello, how are you?", "cloud") is True

    def test_mirage_proxy_detects_names(self):
        from velvet.mirage import MirageProxy
        proxy = MirageProxy()
        # Test with name and trigger keywords
        text = "Hello, meet Priya Kapoor at the clinic."
        scrambled, smap = proxy.scramble(text)
        assert scrambled != text
        assert smap is not None
        assert "Priya Kapoor" in smap.forward

    def test_mirage_proxy_replaces_phone(self):
        from velvet.mirage import MirageProxy
        proxy = MirageProxy()
        text = "Call me at 555-123-4567 tomorrow."
        scrambled, smap = proxy.scramble(text)
        assert "555-123-4567" not in scrambled
        assert "555-" in scrambled
        assert smap is not None

    def test_mirage_round_trip(self):
        from velvet.mirage import MirageProxy
        proxy = MirageProxy()
        text = "Hello, I am Priya Kapoor and my number is 555-123-4567."
        scrambled, smap = proxy.scramble(text)
        assert scrambled != text
        rehydrated = proxy.rehydrate(scrambled, smap)
        assert rehydrated == text

    def test_mirage_proxy_no_pii(self):
        from velvet.mirage import MirageProxy
        proxy = MirageProxy()
        text = "What is the weather today?"
        scrambled, smap = proxy.scramble(text)
        assert scrambled == text
        assert smap is None

    def test_mirage_map_is_ephemeral(self):
        from velvet.mirage import MirageMap
        smap = MirageMap()
        smap.add("original", "fake")
        assert smap.forward["original"] == "fake"
        assert smap.reverse["fake"] == "original"

    def test_privacy_level_ordering(self):
        from velvet.privacy import PrivacyLevel
        assert PrivacyLevel.PUBLIC < PrivacyLevel.PERSONAL
        assert PrivacyLevel.PERSONAL < PrivacyLevel.SENSITIVE
        assert PrivacyLevel.SENSITIVE < PrivacyLevel.RESTRICTED

    def test_classifier_ssn_is_sensitive(self):
        from velvet.privacy import PrivacyClassifier, PrivacyLevel
        c = PrivacyClassifier()
        assert c.classify("My SSN is 000-12-3456") == PrivacyLevel.SENSITIVE

    def test_classifier_credit_card_is_sensitive(self):
        from velvet.privacy import PrivacyClassifier, PrivacyLevel
        c = PrivacyClassifier()
        assert c.classify("Card: 1234-5678-9012-3456") == PrivacyLevel.SENSITIVE

    def test_classifier_email_is_sensitive(self):
        from velvet.privacy import PrivacyClassifier, PrivacyLevel
        c = PrivacyClassifier()
        assert c.classify("Email me at test@example.com") == PrivacyLevel.SENSITIVE

    def test_classifier_medical_is_sensitive(self):
        from velvet.privacy import PrivacyClassifier, PrivacyLevel
        c = PrivacyClassifier()
        assert c.classify("I have high blood pressure") == PrivacyLevel.SENSITIVE

    def test_classifier_gossip_is_sensitive(self):
        from velvet.privacy import PrivacyClassifier, PrivacyLevel
        c = PrivacyClassifier()
        assert c.classify("don't tell anyone about the affair") == PrivacyLevel.SENSITIVE

    def test_classifier_password_is_restricted(self):
        from velvet.privacy import PrivacyClassifier, PrivacyLevel
        c = PrivacyClassifier()
        assert c.classify("my master password is supersecret") == PrivacyLevel.RESTRICTED

    def test_classifier_biometric_dtype_is_restricted(self):
        from velvet.privacy import PrivacyClassifier, PrivacyLevel
        c = PrivacyClassifier()
        assert c.classify("", data_type="face_embedding") == PrivacyLevel.RESTRICTED

    def test_classifier_schedule_is_personal(self):
        from velvet.privacy import PrivacyClassifier, PrivacyLevel
        c = PrivacyClassifier()
        assert c.classify("Let's schedule a meeting") == PrivacyLevel.PERSONAL

    def test_classifier_clean_text_is_public(self):
        from velvet.privacy import PrivacyClassifier, PrivacyLevel
        c = PrivacyClassifier()
        assert c.classify("Hello world") == PrivacyLevel.PUBLIC

    def test_classifier_aadhar_is_sensitive(self):
        from velvet.privacy import PrivacyClassifier, PrivacyLevel
        c = PrivacyClassifier()
        assert c.classify("My Aadhaar number is 1234 5678 9012") == PrivacyLevel.SENSITIVE
        assert c.classify("Aadhar is 123456789012") == PrivacyLevel.SENSITIVE

    def test_passport_is_sensitive(self):
        from velvet.privacy import PrivacyClassifier, PrivacyLevel
        c = PrivacyClassifier()
        assert c.classify("Passport number is A1234567") == PrivacyLevel.SENSITIVE

    def test_guard_blocks_restricted_from_all(self):
        from velvet.privacy import PrivacyGuard, PrivacyLevel
        guard = PrivacyGuard()
        with patch.object(guard, "_is_mesh_peer", return_value=True), \
             patch.object(guard, "_is_trusted_peer", return_value=True):
            assert guard.is_safe_to_send("any", "peer", level=PrivacyLevel.RESTRICTED) is False

    def test_guard_blocks_personal_raw_to_cloud(self):
        from velvet.privacy import PrivacyGuard, PrivacyLevel
        guard = PrivacyGuard()
        with patch.object(guard, "_is_mesh_peer", return_value=False):
            assert guard.is_safe_to_send("any", "cloud", level=PrivacyLevel.PERSONAL) is False

    def test_guard_allows_public_to_cloud(self):
        from velvet.privacy import PrivacyGuard, PrivacyLevel
        guard = PrivacyGuard()
        with patch.object(guard, "_is_mesh_peer", return_value=False):
            assert guard.is_safe_to_send("any", "cloud", level=PrivacyLevel.PUBLIC) is True

    def test_guard_allows_personal_to_trusted_peer(self):
        from velvet.privacy import PrivacyGuard, PrivacyLevel
        guard = PrivacyGuard()
        with patch.object(guard, "_is_mesh_peer", return_value=True), \
             patch.object(guard, "_is_trusted_peer", return_value=True):
            assert guard.is_safe_to_send("any", "trusted_peer", level=PrivacyLevel.PERSONAL) is True

    def test_guard_blocks_sensitive_from_untrusted_peer(self):
        from velvet.privacy import PrivacyGuard, PrivacyLevel
        guard = PrivacyGuard()
        with patch.object(guard, "_is_mesh_peer", return_value=True), \
             patch.object(guard, "_is_trusted_peer", return_value=False):
            assert guard.is_safe_to_send("any", "untrusted_peer", level=PrivacyLevel.SENSITIVE) is False

    def test_biometric_auto_restrict_still_works(self):
        from velvet.privacy import PrivacyGuard
        guard = PrivacyGuard()
        assert guard.biometric_auto_restrict("face_embedding") is True
        assert guard.biometric_auto_restrict("public_data") is False


# ============================================================================
# High Performance Local Backends (Sprint 18)
# ============================================================================

class TestHighPerfBackends:
    """Verify loading, signature detection, and inference routing for high-perf backends."""

    def test_select_backend_class_by_signature(self, tmp_path):
        from velvet.shen.polymath import get_polymath, LlamaCppBackend, TensorRTBackend, VLLMBackend
        poly = get_polymath()
        
        # 1. GGUF signature
        model_gguf = tmp_path / "model.gguf"
        model_gguf.write_text("fake gguf content")
        assert poly.select_backend_class(str(model_gguf)) == LlamaCppBackend
        
        # 2. TensorRT engine directory signature
        trt_dir = tmp_path / "trt_model"
        trt_dir.mkdir()
        (trt_dir / "model.engine").write_text("fake engine content")
        assert poly.select_backend_class(str(trt_dir)) == TensorRTBackend
        
        # 3. vLLM safetensors directory signature
        vllm_dir = tmp_path / "vllm_model"
        vllm_dir.mkdir()
        (vllm_dir / "model.safetensors").write_text("fake safetensors content")
        assert poly.select_backend_class(str(vllm_dir)) == VLLMBackend

    @pytest.mark.asyncio
    async def test_vllm_backend_generation(self, tmp_path):
        import sys
        from velvet.shen.polymath import VLLMBackend
        
        # Mock the vllm library and LLM object
        mock_llm_instance = MagicMock()
        mock_output = MagicMock()
        mock_output.outputs = [MagicMock(text="vLLM generated response")]
        mock_llm_instance.generate.return_value = [mock_output]
        
        with patch("sys.modules", new=dict(sys.modules)) as mock_sys_modules:
            mock_vllm = MagicMock()
            mock_vllm.LLM.return_value = mock_llm_instance
            mock_vllm.SamplingParams = MagicMock()
            mock_sys_modules["vllm"] = mock_vllm
            
            backend = VLLMBackend(str(tmp_path))
            res = await backend.generate("Hello vLLM", max_tokens=100)
            
            assert res == "vLLM generated response"
            mock_vllm.LLM.assert_called_once_with(model=str(tmp_path))
            mock_llm_instance.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_tensorrt_backend_generation(self, tmp_path):
        import sys
        from velvet.shen.polymath import TensorRTBackend
        
        # Mock tensorrt_llm and transformers
        mock_runner_instance = MagicMock()
        # Mock generate returning token IDs
        mock_runner_instance.generate.return_value = [[[1, 2, 3]]]
        
        mock_tokenizer_instance = MagicMock()
        mock_tokenizer_instance.encode.return_value = [10, 20]
        mock_tokenizer_instance.decode.return_value = "TensorRT generated response"
        
        with patch("sys.modules", new=dict(sys.modules)) as mock_sys_modules:
            mock_trt = MagicMock()
            mock_trt.runtime.ModelRunner.from_dir.return_value = mock_runner_instance
            mock_sys_modules["tensorrt_llm"] = mock_trt
            mock_sys_modules["tensorrt_llm.runtime"] = mock_trt.runtime
            
            mock_transformers = MagicMock()
            mock_transformers.AutoTokenizer.from_pretrained.return_value = mock_tokenizer_instance
            mock_sys_modules["transformers"] = mock_transformers
            
            backend = TensorRTBackend(str(tmp_path))
            res = await backend.generate("Hello TensorRT", max_tokens=100)
            
            assert res == "TensorRT generated response"
            mock_trt.runtime.ModelRunner.from_dir.assert_called_once_with(str(tmp_path), rank=0)
            mock_transformers.AutoTokenizer.from_pretrained.assert_called_once_with(str(tmp_path))
            mock_runner_instance.generate.assert_called_once_with([[10, 20]], max_new_tokens=100, temperature=0.7)
