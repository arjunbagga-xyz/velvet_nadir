# Trust Provisioning & Onboarding (`trust_provisioner.py`, `onboarding.py`)

## Overview
Coordinates device trust levels (`UNTRUSTED`, `PROBATIONARY`, `TRUSTED`, `REVOKED`), mutual authentication, and cryptographic certificate distribution.

## 3-Phase Provisioning Flow
1. **Device Onboarding (Phase 1)**: Native drivers injected alongside `ca.crt` (never `ca.key`) and randomized `PortMap` written to `~/.velvet/velvet.toml`.
2. **Scheduled 12h Rotation Broadcast (Phase 2)**: Port re-keying distributed via signed `VelvetMessage` over Zenoh topic `velvet/mesh/security/port_rotation`.
3. **Biometric Promotion (Phase 3)**: Elevation from `PROBATIONARY` to `TRUSTED` requires biometric operator authorization, distributing master port seeds and full enclave certificates via SFTP.
