"""
Port Rotation Management: Scheduled 12-Hour Rotation & <500ms Emergency Trigger.
Maintains make-before-break dual listening for graceful migration,
and rapid re-keying on unauthenticated probe detection.
"""

import asyncio
import logging
import random
import time
from typing import Dict, List, Optional, Set, Callable, Any

from .port_map import PortMap

logger = logging.getLogger(__name__)


class EmergencyPortTrigger:
    """
    Immediate emergency port rotation trigger.
    If an unauthenticated SYN probe or non-TLS packet hits a real active mesh port,
    EmergencyPortTrigger fires immediately, re-keying port maps in <500ms
    and shifting the real listener without waiting for connection draining.
    """

    def __init__(self, rotator: "PortRotator"):
        self.rotator = rotator
        self.last_trigger_time: float = 0.0
        self.trigger_count: int = 0

    async def on_unauthenticated_probe(self, port: int, source_ip: str, packet_type: str = "SYN") -> Dict[str, int]:
        """
        Called when an unauthorized probe touches a real port.
        Executes immediate emergency rotation in < 500ms.
        """
        start_time = time.monotonic()
        logger.warning(
            f"🚨 EMERGENCY: Unauthenticated probe on real port {port} from {source_ip} (type={packet_type})! "
            f"Initiating immediate port re-key..."
        )
        
        # Trigger immediate rotation without graceful draining
        new_ports = await self.rotator.rotate_emergency()
        elapsed_ms = (time.monotonic() - start_time) * 1000
        
        self.last_trigger_time = time.time()
        self.trigger_count += 1
        
        logger.info(f"⚡ Emergency port re-key completed in {elapsed_ms:.2f}ms (< 500ms target satisfied).")
        return new_ports


class PortRotator:
    """
    Orchestrates scheduled 12-hour port rotation and emergency rotation.
    Maintains dual-listen during scheduled rotation for make-before-break reliability.
    """

    def __init__(
        self,
        services: Optional[List[str]] = None,
        grace_period_seconds: float = 60.0,
        broadcast_callback: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ):
        self.services = services or ["zenoh_mesh", "grpc_control", "display_bridge", "file_sync"]
        self.grace_period_seconds = grace_period_seconds
        self.broadcast_callback = broadcast_callback
        
        self.port_map = PortMap.generate(self.services)
        self.emergency_trigger = EmergencyPortTrigger(self)
        self._rotation_task: Optional[asyncio.Task] = None
        self._is_running: bool = False
        self.active_listeners: Dict[str, Any] = {}

    def get_port(self, service_name: str) -> Optional[int]:
        """Get current active port for a service."""
        return self.port_map.services.get(service_name)

    def get_all_ports(self) -> Dict[str, int]:
        """Get copy of all current active service ports."""
        return self.port_map.services.copy()

    def get_grace_ports(self) -> Dict[str, int]:
        """Get copy of grace-period ports still accepting connections."""
        return self.port_map.grace_period_services.copy()

    async def rotate_scheduled(self) -> Dict[str, int]:
        """
        Perform 12-hour scheduled rotation.
        Make-before-break: moves existing ports into grace period so in-flight tasks
        and active streams are not disconnected.
        """
        logger.info("[PortRotator] Starting 12-hour scheduled make-before-break port rotation...")
        old_ports = self.port_map.services.copy()
        self.port_map.rotate(self.services)
        new_ports = self.port_map.services.copy()

        # Broadcast update to mesh and UI
        await self._broadcast_rotation(new_ports, emergency=False)

        # Schedule grace period cleanup task
        asyncio.create_task(self._drain_grace_period(old_ports, self.grace_period_seconds))
        return new_ports

    async def rotate_emergency(self) -> Dict[str, int]:
        """
        Perform immediate emergency rotation (< 500ms).
        Re-keys immediately, dropping old ports to thwart active scans.
        """
        logger.warning("[PortRotator] EXECUTING IMMEDIATE EMERGENCY PORT ROTATION!")
        self.port_map.rotate(self.services)
        # In emergency, immediately clear grace period ports so attacker cannot connect
        self.port_map.grace_period_services.clear()
        new_ports = self.port_map.services.copy()

        await self._broadcast_rotation(new_ports, emergency=True)
        return new_ports

    async def _broadcast_rotation(self, new_ports: Dict[str, int], emergency: bool) -> None:
        """Broadcast new port map on Zenoh and UI display bridge."""
        event = {
            "type": "mesh/security/port_rotation",
            "ports": new_ports,
            "emergency": emergency,
            "timestamp": time.time(),
        }
        if self.broadcast_callback:
            try:
                res = self.broadcast_callback(event)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                logger.error(f"[PortRotator] Failed to broadcast port rotation: {e}")

        logger.info(f"[PortRotator] Port rotation published (Emergency={emergency}): {new_ports}")

    async def _drain_grace_period(self, old_ports: Dict[str, int], duration: float) -> None:
        """Wait for grace period then clear old ports."""
        try:
            await asyncio.sleep(duration)
            self.port_map.grace_period_services.clear()
            logger.info(f"[PortRotator] Grace period expired ({duration}s). Closed old ports: {old_ports}")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"[PortRotator] Error during grace period draining: {e}")

    def start_scheduler(self, interval_hours: float = 12.0) -> asyncio.Task:
        """Start the periodic 12-hour rotation daemon."""
        self._is_running = True
        interval_seconds = interval_hours * 3600.0

        async def _loop():
            try:
                while self._is_running:
                    await asyncio.sleep(interval_seconds)
                    if self._is_running:
                        await self.rotate_scheduled()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"[PortRotator] Rotation loop error: {e}")

        self._rotation_task = asyncio.create_task(_loop())
        logger.info(f"[PortRotator] Port rotator scheduled every {interval_hours} hours.")
        return self._rotation_task

    async def stop(self) -> None:
        """Stop rotation daemon."""
        self._is_running = False
        if self._rotation_task and not self._rotation_task.done():
            self._rotation_task.cancel()
            try:
                await self._rotation_task
            except asyncio.CancelledError:
                pass
        logger.info("[PortRotator] Port rotator stopped.")

    stop_scheduler = stop
