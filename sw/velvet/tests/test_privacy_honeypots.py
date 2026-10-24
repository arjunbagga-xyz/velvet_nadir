"""
Unit and integration tests for Velvet Nadir Phase 4:
Privacy EgressGuard, IdentityRegistry, 4-Track Honeypot, Zero-Knowledge Credential Isolation,
Port Rotation, and Stealth Firewall.
"""

import asyncio
import io
import time
import pytest
import hmac
import hashlib
from PIL import Image

from velvet.privacy.cred_factory import BloomFilterGuard, HoneypotCredentialFactory
from velvet.privacy.identity_registry import IdentityRegistry, Account
from velvet.privacy.platforms.instagram import InstagramPoisonModule
from velvet.privacy.platforms.twitter import TwitterPoisonModule
from velvet.privacy.perturbation import PerturbationEngine
from velvet.privacy.egress_guard import EgressGuard, ContentType, PrivacyStrength
from velvet.privacy.port_rotation import PortRotator, EmergencyPortTrigger
from velvet.privacy.firewall import MeshNetworkSetup, FirewallAction
from velvet.privacy.honeypot_ports import HoneypotPortBinder
from velvet.privacy.honeypot_vulns import (
    Track1SloppyDeveloper,
    Track2CloudInfrastructure,
    Track3IoTInternalNetwork,
    Track4ExposedManagement,
    log_honeypot_forensic,
)


@pytest.mark.asyncio
async def test_bloom_filter_zero_false_negatives():
    """Verify BloomFilterGuard rejects real credentials with zero false negatives."""
    vault_salt = b"test-salt-secret-1234"
    real_passwords = [f"RealPass{i}!supersecret" for i in range(100)]
    
    # Pre-hash real passwords into Bloom filter
    real_hmacs = {
        hmac.new(vault_salt, p.encode("utf-8"), hashlib.sha256).hexdigest()
        for p in real_passwords
    }
    
    guard = BloomFilterGuard(initial_hashes=real_hmacs)
    
    # 1. Zero False Negatives: EVERY real password MUST test positive in the filter
    for p in real_passwords:
        h = hmac.new(vault_salt, p.encode("utf-8"), hashlib.sha256).hexdigest()
        assert guard.contains(h) is True, f"False negative detected for real secret: {p}!"

    # 2. HoneypotCredentialFactory ensures candidate never collides with real secrets
    factory = HoneypotCredentialFactory(
        master_seed=b"test-honeypot-master-seed-9876",
        guard=guard,
        vault_salt=vault_salt,
    )

    for i in range(20):
        fake_pwd = factory.generate_password(service=f"svc_{i}")
        fake_api = factory.generate_api_key(service=f"svc_{i}")
        fake_aws = factory.generate_aws_key(service=f"svc_{i}")
        fake_db = factory.generate_db_password(service=f"svc_{i}")

        assert fake_pwd not in real_passwords
        assert fake_api.startswith("vlt_fake_")
        assert fake_aws.startswith("AKIADECOY")
        assert fake_db.startswith("s3cure_")

        # Double check candidate HMAC is not in the set of real secrets
        fake_hmac = hmac.new(vault_salt, fake_pwd.encode("utf-8"), hashlib.sha256).hexdigest()
        assert fake_hmac not in real_hmacs


@pytest.mark.asyncio
async def test_identity_registry_real_vs_phantom_isolation():
    """Verify Hard Rule: Real accounts are never poisoned; phantom accounts shield real accounts."""
    registry = IdentityRegistry()
    
    activated_modules = []
    registry.register_listener(lambda acc: activated_modules.append(acc.platform))

    real_user = registry.register_real_account(
        platform="instagram",
        username="actual_human_user",
        display_name="Actual Human",
    )

    assert real_user.is_real is True
    assert registry.is_real_account("instagram", "actual_human_user") is True
    assert registry.is_phantom_account("instagram", "actual_human_user") is False
    assert "instagram" in activated_modules

    # Verify 3 phantom shield accounts were auto-created
    phantoms = registry.get_phantom_accounts("instagram")
    assert len(phantoms) == 3
    for p in phantoms:
        assert p.is_real is False
        assert p.username.startswith("decoy_actual_human_user_")

    # Platform module behavior: real account text is never styled
    insta_mod = InstagramPoisonModule()
    user_text = "Important urgent human communication."
    filtered_real = await insta_mod.apply_egress_filter(user_text, ContentType.TEXT, is_phantom=False)
    assert filtered_real == user_text  # Real account text strictly untouched!

    # Phantom account text has style shift applied
    filtered_phantom = await insta_mod.apply_egress_filter(user_text, ContentType.TEXT, is_phantom=True)
    assert isinstance(filtered_phantom, str)


@pytest.mark.asyncio
async def test_perturbation_engine_and_egress_guard():
    """Test adversarial media perturbation and platform epsilon scaling."""
    engine = PerturbationEngine(PrivacyStrength.BALANCED)
    
    # 1. Platform epsilons
    assert engine._get_epsilon("instagram") == pytest.approx(16.0 / 255.0)
    assert engine._get_epsilon("signal") == pytest.approx(4.0 / 255.0)
    assert engine._get_epsilon("twitter") == pytest.approx(8.0 / 255.0)

    # 2. Image perturbation
    # Create test image in memory
    img = Image.new("RGB", (64, 64), color=(128, 128, 128))
    img_bytes_io = io.BytesIO()
    img.save(img_bytes_io, format="PNG")
    raw_img_bytes = img_bytes_io.getvalue()

    perturbed_bytes = await engine.perturb_image(raw_img_bytes, destination="instagram")
    assert isinstance(perturbed_bytes, bytes)
    assert len(perturbed_bytes) > 0
    # The perturbed image bytes should be valid and differ from the original
    assert perturbed_bytes != raw_img_bytes

    # 3. Audio perturbation check
    assert engine._is_lossless_destination("instagram") is False
    assert engine._is_lossless_destination("reels") is False
    assert engine._is_lossless_destination("direct_share") is True

    test_audio = b"RIFFfake_audio_stream_data_here"
    bypassed_audio = await engine.perturb_audio(test_audio, destination="instagram")
    assert bypassed_audio == test_audio  # Bypassed on lossy


@pytest.mark.asyncio
async def test_honeypot_4_track_chaining_and_forensics(tmp_path):
    """Verify the 4 interconnected honeypot tracks, tarpits, and Tartarus forensic logs."""
    db_file = tmp_path / "tartarus_test.db"

    # Track 1: Sloppy Developer (SSH -> MySQL -> REST /debug)
    t1 = Track1SloppyDeveloper()
    
    # Test forensic logging
    record = log_honeypot_forensic(
        trap="test_ssh",
        attacker_ip="192.0.2.1",
        method="SSH_AUTH",
        payload={"user": "admin", "pass": "admin123"},
        db_path=db_file,
    )
    assert record["trap"] == "test_ssh"
    assert record["attacker_ip"] == "192.0.2.1"
    assert db_file.exists()

    # Track 2: Cloud Infra
    t2 = Track2CloudInfrastructure()
    assert t2.tarpit is not None

    # Track 3: IoT / Internal Network
    t3 = Track3IoTInternalNetwork()
    assert t3.tarpit is not None

    # Track 4: Exposed Management
    t4 = Track4ExposedManagement()
    assert t4.tarpit is not None


@pytest.mark.asyncio
async def test_scheduled_and_emergency_port_rotation():
    """Verify 12h scheduled make-before-break rotation and <500ms emergency rotation."""
    broadcasts = []
    def on_broadcast(event):
        broadcasts.append(event)

    rotator = PortRotator(
        services=["mesh_control", "grpc_service"],
        grace_period_seconds=0.1,  # Fast for test
        broadcast_callback=on_broadcast,
    )

    initial_ports = rotator.get_all_ports()
    assert "mesh_control" in initial_ports
    assert 30000 <= initial_ports["mesh_control"] <= 65000

    # 1. Scheduled Rotation (Make-before-break)
    new_ports = await rotator.rotate_scheduled()
    assert new_ports["mesh_control"] != initial_ports["mesh_control"]
    
    # Initial ports are in grace period (dual-listen)
    grace_ports = rotator.get_grace_ports()
    assert grace_ports["mesh_control"] == initial_ports["mesh_control"]
    assert len(broadcasts) == 1
    assert broadcasts[0]["emergency"] is False

    # Wait for grace period draining
    await asyncio.sleep(0.15)
    assert len(rotator.get_grace_ports()) == 0

    # 2. Emergency Rotation (<500ms trigger on unauthenticated probe)
    t0 = time.monotonic()
    emergency_ports = await rotator.emergency_trigger.on_unauthenticated_probe(
        port=new_ports["mesh_control"],
        source_ip="203.0.113.5",
        packet_type="SYN",
    )
    elapsed_ms = (time.monotonic() - t0) * 1000
    assert elapsed_ms < 500.0, f"Emergency rotation took {elapsed_ms:.2f}ms (exceeds 500ms limit)!"
    assert emergency_ports["mesh_control"] != new_ports["mesh_control"]
    # Grace ports immediately cleared in emergency
    assert len(rotator.get_grace_ports()) == 0
    assert broadcasts[-1]["emergency"] is True


def test_firewall_rules_stealth_drop():
    """Verify stealth OS firewall rules: real ports drop silently, honeypot ports open."""
    setup = MeshNetworkSetup()
    trusted_ips = ["10.0.0.1", "10.0.0.2"]
    real_ports = [45000, 45001]
    honeypot_ports = [22, 80, 443, 3306]

    rules = setup.configure_firewall(
        trusted_ips=trusted_ips,
        real_ports=real_ports,
        honeypot_ports=honeypot_ports,
        apply_to_os=False,
    )

    # 1. Honeypot ports allow from any source
    assert setup.test_packet("198.51.100.99", 22) == FirewallAction.ALLOW
    assert setup.test_packet("198.51.100.99", 80) == FirewallAction.ALLOW
    assert setup.test_packet("198.51.100.99", 443) == FirewallAction.ALLOW
    assert setup.test_packet("198.51.100.99", 3306) == FirewallAction.ALLOW

    # 2. Real ports allow from trusted IPs
    assert setup.test_packet("10.0.0.1", 45000) == FirewallAction.ALLOW
    assert setup.test_packet("10.0.0.2", 45001) == FirewallAction.ALLOW

    # 3. Real ports SILENTLY DROP untrusted IPs (Stealth: DROP, not REJECT)
    assert setup.test_packet("198.51.100.99", 45000) == FirewallAction.DROP
    assert setup.test_packet("1.2.3.4", 45001) == FirewallAction.DROP

    # 4. Unknown ports drop by default
    assert setup.test_packet("198.51.100.99", 9999) == FirewallAction.DROP
