import pytest
import os
from unittest.mock import MagicMock, patch
from velvet.fabric import VelvetMessage, MessageType, match_pattern, FabricError

# ============================================================================
# VelvetMessage Serialization & HMAC Integrity Tests
# ============================================================================

class TestVelvetMessageSerialization:
    """Verify that VelvetMessage survives packing/unpacking and HMAC guards against tampering."""

    def test_unsigned_roundtrip(self):
        """Unsigned message survives serialization/deserialization."""
        # Force config to NOT require secret for unsigned tests
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
        """Signed message survives sign -> verify serialization cycle."""
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
        """Tampered signed message throws FabricError on deserialization."""
        with patch("velvet.config.get_config") as mock_cfg:
            mock_cfg.return_value = MagicMock()
            mock_cfg.return_value.security.mesh_secret = "secret"

            msg = VelvetMessage(
                msg_type="test", payload={"x": 1}, source_device="src"
            )
            raw = msg.to_bytes()

            # Tamper: flip a byte in the payload
            tampered = bytearray(raw)
            tampered[5] ^= 0xFF
            tampered = bytes(tampered)

            with pytest.raises(FabricError, match="Invalid HMAC"):
                VelvetMessage.from_bytes(tampered)


# ============================================================================
# Topic Wildcard Match Patterns (Zenoh Style)
# ============================================================================

class TestZenohPatternMatching:
    """Verify Zenoh-style topic patterns with * and ** wildcards."""

    def test_exact_matches(self):
        assert match_pattern("sys/heartbeat", "sys/heartbeat") is True
        assert match_pattern("sys/heartbeat", "sys/status") is False

    def test_single_asterisk_matches_one_level(self):
        # * matches one path component (excluding /)
        assert match_pattern("sys/*/status", "sys/device/status") is True
        assert match_pattern("sys/*/status", "sys/device/info/status") is False

    def test_double_asterisk_matches_multi_level(self):
        # ** matches any subpath (including /)
        assert match_pattern("sys/**/status", "sys/device/status") is True
        assert match_pattern("sys/**/status", "sys/device/info/status") is True
        assert match_pattern("sys/**", "sys/device/info/status") is True
