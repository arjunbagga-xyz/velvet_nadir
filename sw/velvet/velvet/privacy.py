"""
Privacy Guard: Mesh Perimeter Enforcement.

Two perimeters:
  1. Mesh vs Internet — nothing leaves the mesh without explicit consent
  2. Trusted vs Untrusted within mesh — UNTRUSTED devices can be USED
     (compute, sensors) but get NO data back (no memory sync, no graph access)

This is NOT about privacy between devices. All TRUSTED devices share everything
freely — location, health, config, biometrics. The mesh IS the device.
"""

from __future__ import annotations

__all__ = [
    "PrivacyViolation",
    "PrivacyGuard",
]

from loguru import logger


class PrivacyViolation(Exception):
    """Raised when an operation would violate the privacy perimeter."""
    pass


class PrivacyGuard:
    """
    Enforces two privacy perimeters:
    1. Mesh vs Internet
    2. Trusted vs Untrusted within mesh
    """

    def __init__(self, registry=None):
        self._registry = registry

    def _get_registry(self):
        """Lazy-load the registry."""
        if self._registry is None:
            try:
                from velvet.devices import get_registry
                self._registry = get_registry()
            except RuntimeError:
                return None
        return self._registry

    def _is_mesh_peer(self, device_id: str) -> bool:
        """Check if a device is a registered mesh peer."""
        reg = self._get_registry()
        if reg is None:
            return False
        device = reg.get_device(device_id)
        return device is not None

    def _is_trusted_peer(self, device_id: str) -> bool:
        """Check if a device is a TRUSTED mesh peer."""
        reg = self._get_registry()
        if reg is None:
            return False
        device = reg.get_device(device_id)
        if device is None:
            return False
        return device.is_trusted()

    def can_sync_memory(self, device_id: str) -> bool:
        """
        Can we sync memory to this device?

        Only TRUSTED mesh peers get memory sync.
        """
        if not self._is_mesh_peer(device_id):
            return False
        return self._is_trusted_peer(device_id)

    def can_route_task(self, device_id: str) -> bool:
        """
        Can we route a compute task to this device?

        Any mesh device can receive compute tasks — we USE even untrusted devices.
        """
        return self._is_mesh_peer(device_id)

    def can_receive_data(self, device_id: str) -> bool:
        """
        Can this device receive our data (memories, secrets, etc.)?

        Same as can_sync_memory — only trusted peers.
        """
        return self.can_sync_memory(device_id)

    def on_outbound_internet(self, data: dict, destination: str):
        """
        Block any data leaving the mesh.

        Raises PrivacyViolation unless the destination is a known mesh peer.
        """
        if not self._is_mesh_peer(destination):
            raise PrivacyViolation(
                f"Blocked: data cannot leave mesh to '{destination}'. "
                f"Only mesh peers can receive data."
            )

    def check_memory_sync(self, device_id: str) -> bool:
        """
        Pre-flight check before syncing a memory to a peer.

        Returns True if allowed, False if blocked.
        Logs the reason if blocked.
        """
        if not self._is_mesh_peer(device_id):
            logger.debug(f"[PrivacyGuard] Blocked memory sync to {device_id}: not a mesh peer")
            return False

        if not self._is_trusted_peer(device_id):
            logger.debug(f"[PrivacyGuard] Blocked memory sync to {device_id}: untrusted device")
            return False

        return True
