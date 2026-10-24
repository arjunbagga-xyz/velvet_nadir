"""
Zero-Knowledge Credential Isolation via HKDF and Bloom Filter.
Ensures honeypot and decoy credentials mathematically NEVER collide with real secrets.
"""

import base64
import binascii
import hashlib
import hmac
import logging
from typing import Optional, Set

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

logger = logging.getLogger(__name__)


class BloomFilterGuard:
    """
    Bloom filter representing the HMAC-hashed vault secrets from BasiliskEnclave.
    Guarantees ZERO FALSE NEGATIVES: if `contains(candidate_hash)` returns False,
    the candidate is mathematically proven NOT to match any real secret in the vault.
    """

    def __init__(self, size_bits: int = 800_000, num_hashes: int = 7, initial_hashes: Optional[Set[str]] = None):
        """
        Default size ~100 KB (800,000 bits) with 7 hash functions gives ~0.1% false positive
        rate for up to 10,000 credentials.
        """
        self.size_bits = size_bits
        self.num_hashes = num_hashes
        self._bit_array = bytearray((size_bits + 7) // 8)
        self._set_backup: Set[str] = set()

        if initial_hashes:
            for h in initial_hashes:
                self.add(h)

    def _get_bit_indices(self, item_hash: str) -> list[int]:
        """Compute k bit indices using Kirsch-Mitzenmacher optimization."""
        h1 = int(hashlib.sha256(item_hash.encode("utf-8")).hexdigest()[:16], 16)
        h2 = int(hashlib.md5(item_hash.encode("utf-8")).hexdigest()[:16], 16)
        indices = []
        for i in range(self.num_hashes):
            idx = (h1 + i * h2) % self.size_bits
            indices.append(idx)
        return indices

    def add(self, credential_hash: str) -> None:
        """Add an HMAC credential hash to the filter."""
        self._set_backup.add(credential_hash)
        for idx in self._get_bit_indices(credential_hash):
            byte_idx = idx // 8
            bit_idx = idx % 8
            self._bit_array[byte_idx] |= (1 << bit_idx)

    def contains(self, candidate_hash: str) -> bool:
        """
        Check if candidate hash might be in the filter.
        Returns False if definitely NOT present (Zero False Negatives).
        Returns True if potentially present (False Positive possible).
        """
        for idx in self._get_bit_indices(candidate_hash):
            byte_idx = idx // 8
            bit_idx = idx % 8
            if not (self._bit_array[byte_idx] & (1 << bit_idx)):
                return False
        return True


class HoneypotCredentialFactory:
    """
    Generates deterministic fake credentials from an HKDF-derived master seed.
    Every candidate is verified against BloomFilterGuard before emission.
    """

    def __init__(
        self,
        master_seed: bytes = b"velvet-decoy-master-seed-v1",
        guard: BloomFilterGuard | None = None,
        vault_salt: bytes = b"velvet-vault-salt-v1",
    ):
        self._seed = master_seed
        self.guard = guard or BloomFilterGuard()
        self.vault_salt = vault_salt

    def _derive(self, info: bytes, length: int) -> bytes:
        """Derive deterministic entropy using HKDF with SHA256."""
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=length,
            salt=b"velvet-decoy-v1",
            info=info,
        )
        return hkdf.derive(self._seed)

    def _generate_safe(self, service: str, field_name: str, formatter, length: int = 32) -> str:
        """
        Derive candidate credential and test against Bloom filter.
        Re-rolls up to 100 attempts on collision.
        """
        for attempt in range(100):
            info = f"decoy:{service}:{field_name}:{attempt}".encode("utf-8")
            raw = self._derive(info, length)
            candidate = formatter(raw)

            # HMAC against vault_salt
            candidate_hmac = hmac.new(self.vault_salt, candidate.encode("utf-8"), hashlib.sha256).hexdigest()

            # Zero-knowledge check: if not in Bloom filter, it's safe
            if not self.guard.contains(candidate_hmac):
                return candidate

            logger.warning(
                f"[HoneypotCredentialFactory] Collision detected on {service}:{field_name} (attempt {attempt}). Re-rolling..."
            )

        raise RuntimeError(
            f"Failed to generate safe honeypot credential for {service}:{field_name} after 100 attempts"
        )

    def generate_password(self, service: str = "general") -> str:
        """Generate a URL-safe base64 decoy password."""
        def fmt(raw: bytes) -> str:
            # 16-char base64 string
            return base64.urlsafe_b64encode(raw[:12]).decode("utf-8")
        return self._generate_safe(service, "password", fmt, length=16)

    def generate_api_key(self, service: str = "general") -> str:
        """Generate a fake API key formatted as vlt_fake_<32-char hex>."""
        def fmt(raw: bytes) -> str:
            return "vlt_fake_" + binascii.hexlify(raw[:16]).decode("utf-8")
        return self._generate_safe(service, "api_key", fmt, length=16)

    def generate_aws_key(self, service: str = "s3") -> str:
        """Generate a fake AWS Access Key ID formatted as AKIADECOY<12-char hex>."""
        def fmt(raw: bytes) -> str:
            return "AKIADECOY" + binascii.hexlify(raw[:6]).decode("utf-8").upper()
        return self._generate_safe(service, "aws_key", fmt, length=12)

    def generate_db_password(self, service: str = "mysql") -> str:
        """Generate a realistic fake DB password."""
        def fmt(raw: bytes) -> str:
            hex_part = binascii.hexlify(raw[:6]).decode("utf-8")
            return f"s3cure_{service}_{hex_part}!"
        return self._generate_safe(service, "db_password", fmt, length=16)

    def generate_bearer_token(self, service: str = "k8s") -> str:
        """Generate a fake Bearer JWT/token."""
        def fmt(raw: bytes) -> str:
            return "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9." + base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")
        return self._generate_safe(service, "bearer", fmt, length=32)
