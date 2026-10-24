# Cryptographic Subsystem (`crypto.py`)

## Overview
`velvet.crypto` provides core cryptographic operations for the Velvet Nadir mesh, including device identity keys, key exchange, encryption at rest in BasiliskEnclave, and zero-knowledge token derivation.

## Key Capabilities
- **Ed25519 & X25519**: Device public/private key pairs for mesh mutual authentication and session key agreement over Zenoh.
- **HKDF Derivation**: Deterministic, salt-isolated key derivation for honeypot credential generation (`velvet.privacy.cred_factory`) and ephemeral tokens.
- **Symmetric AEAD**: ChaCha20-Poly1305 and AES-256-GCM for encrypted channel payloads and local enclave vaults.
- **Zero-Knowledge Proofs & Bloom Filters**: Collision-free decoy validation proving honeypot secrets do not intersect with real vault entries.
