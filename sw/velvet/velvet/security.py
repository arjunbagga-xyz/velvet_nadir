"""
Mesh Security: TLS Certificate Management + HMAC Message Signing.

Shared CA model — every trusted node holds the CA and can issue certs.
No primary node. Mesh survives any single node being off.

Usage:
    # First boot (auto-called by start_velvet):
    cert_mgr = CertManager("~/.velvet/certs")
    cert_mgr.ensure_ca()                          # Generate or load CA
    cert_mgr.issue_node_cert("laptop-01")          # Self-issue node cert

    # Onboarding (auto-called by inject_velvet):
    cert_mgr.issue_node_cert("jetson-01")          # Issue cert for new node
    # Then SCP ca.key, ca.crt, jetson-01.crt, jetson-01.key to remote

    # Message signing:
    sig = sign_message(payload_bytes, "my-mesh-secret")
    ok  = verify_message(payload_bytes, sig, "my-mesh-secret")
"""

__all__ = [
    "CertManager",
    "sign_message",
    "verify_message",
]

import hmac
import hashlib
import datetime
from pathlib import Path
from loguru import logger

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa


# ============================================================================
# HMAC Message Signing
# ============================================================================

HMAC_SIGNATURE_SIZE = 32  # SHA-256 produces 32 bytes


def sign_message(payload: bytes, secret: str) -> bytes:
    """Compute HMAC-SHA256 over message payload.

    Args:
        payload: Raw message bytes (msgpack-serialized VelvetMessage).
        secret: Shared mesh secret string.

    Returns:
        32-byte HMAC signature.
    """
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).digest()


def verify_message(payload: bytes, signature: bytes, secret: str) -> bool:
    """Verify HMAC signature. Constant-time comparison.

    Args:
        payload: Raw message bytes.
        signature: 32-byte HMAC to verify against.
        secret: Shared mesh secret string.

    Returns:
        True if signature is valid, False if tampered or wrong secret.
    """
    expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).digest()
    return hmac.compare_digest(signature, expected)


# ============================================================================
# TLS Certificate Manager
# ============================================================================

# Certificate validity period
_CA_VALIDITY_DAYS = 365 * 10   # 10 years for mesh CA
_NODE_VALIDITY_DAYS = 365 * 2  # 2 years for node certs
_KEY_SIZE = 4096


class CertManager:
    """Manages TLS certificates for the Velvet mesh.

    Shared CA model: every trusted node gets a copy of ca.key + ca.crt
    so any node can issue certs for new devices. No primary node dependency.
    """

    def __init__(self, certs_dir: str = "~/.velvet/certs"):
        self.certs_dir = Path(certs_dir).expanduser()
        self.ca_key_path = self.certs_dir / "ca.key"
        self.ca_cert_path = self.certs_dir / "ca.crt"

    def ensure_ca(self) -> tuple[Path, Path]:
        """Load existing CA or generate a new one.

        Called on every boot. Idempotent — if CA exists on disk, loads it.
        If not, generates a new self-signed CA for the mesh.

        Returns:
            Tuple of (ca_key_path, ca_cert_path).
        """
        self.certs_dir.mkdir(parents=True, exist_ok=True)
        if self.ca_key_path.exists() and self.ca_cert_path.exists():
            logger.info(f"Mesh CA loaded from {self.certs_dir}")
            return self.ca_key_path, self.ca_cert_path
        return self._generate_ca()

    def has_node_cert(self, device_id: str) -> bool:
        """Check if a node certificate exists on disk."""
        cert_path = self.certs_dir / f"{device_id}.crt"
        key_path = self.certs_dir / f"{device_id}.key"
        return cert_path.exists() and key_path.exists()

    def issue_node_cert(self, device_id: str) -> tuple[Path, Path]:
        """Generate key + cert for a mesh node, signed by our CA.

        Args:
            device_id: Unique device identifier (e.g., "jetson-01").

        Returns:
            Tuple of (cert_path, key_path).

        Raises:
            FileNotFoundError: If CA doesn't exist (call ensure_ca first).
        """
        if not self.ca_key_path.exists() or not self.ca_cert_path.exists():
            raise FileNotFoundError(
                "Mesh CA not found. Call ensure_ca() before issuing node certs."
            )

        # Load CA
        ca_key = self._load_private_key(self.ca_key_path)
        ca_cert = self._load_certificate(self.ca_cert_path)

        # Generate node key
        node_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=_KEY_SIZE,
        )

        # Build node certificate signed by CA
        subject = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, f"velvet-node-{device_id}"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Velvet Mesh"),
        ])

        now = datetime.datetime.now(datetime.timezone.utc)
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(ca_cert.subject)
            .public_key(node_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + datetime.timedelta(days=_NODE_VALIDITY_DAYS))
            .add_extension(
                x509.SubjectAlternativeName([
                    x509.DNSName(f"{device_id}.velvet.local"),
                ]),
                critical=False,
            )
            .add_extension(
                x509.BasicConstraints(ca=False, path_length=None),
                critical=True,
            )
            .sign(ca_key, hashes.SHA256())
        )

        # Write to disk
        cert_path = self.certs_dir / f"{device_id}.crt"
        key_path = self.certs_dir / f"{device_id}.key"

        key_path.write_bytes(
            node_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
        cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))

        logger.info(f"Issued node cert for '{device_id}' → {cert_path}")
        return cert_path, key_path

    def get_tls_paths(self, device_id: str) -> dict[str, str]:
        """Return paths dict suitable for populating ZenohConfig TLS fields.

        Args:
            device_id: The device whose cert paths to return.

        Returns:
            Dict with keys: root_ca, cert, key (all absolute path strings).
        """
        return {
            "root_ca": str(self.ca_cert_path),
            "cert": str(self.certs_dir / f"{device_id}.crt"),
            "key": str(self.certs_dir / f"{device_id}.key"),
        }

    def _generate_ca(self) -> tuple[Path, Path]:
        """Generate a self-signed mesh CA."""
        logger.info("Generating new mesh CA...")

        # Generate CA key
        ca_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=_KEY_SIZE,
        )

        # Build self-signed CA cert
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, "Velvet Mesh CA"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Velvet Mesh"),
        ])

        now = datetime.datetime.now(datetime.timezone.utc)
        ca_cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(ca_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + datetime.timedelta(days=_CA_VALIDITY_DAYS))
            .add_extension(
                x509.BasicConstraints(ca=True, path_length=None),
                critical=True,
            )
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    key_cert_sign=True,
                    crl_sign=True,
                    content_commitment=False,
                    key_encipherment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .sign(ca_key, hashes.SHA256())
        )

        # Write to disk
        self.ca_key_path.write_bytes(
            ca_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
        self.ca_cert_path.write_bytes(
            ca_cert.public_bytes(serialization.Encoding.PEM)
        )

        logger.info(f"Mesh CA generated → {self.certs_dir}")
        return self.ca_key_path, self.ca_cert_path

    @staticmethod
    def _load_private_key(path: Path):
        """Load a PEM-encoded private key from disk."""
        return serialization.load_pem_private_key(
            path.read_bytes(),
            password=None,
        )

    @staticmethod
    def _load_certificate(path: Path):
        """Load a PEM-encoded X.509 certificate from disk."""
        return x509.load_pem_x509_certificate(path.read_bytes())
