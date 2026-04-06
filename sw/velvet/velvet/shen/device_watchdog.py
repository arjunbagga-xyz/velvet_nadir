"""
Device Watchdog: Background Health Monitor.

A BreathTask that monitors mesh device health, logging stats to Jing
and flagging anomalies on untrusted devices.

Never auto-promotes trust — only suggests promotions to the user.
"""

from __future__ import annotations

from loguru import logger

from velvet.shen.xi import BreathTask, ComputeBudget, ConversationTurn


class DeviceWatchdog(BreathTask):
    """
    Background device health monitoring.

    Runs between conversations to:
    1. Log device health stats to Jing
    2. Flag anomalies on untrusted devices
    3. Suggest (never auto-do) trust promotions for reliable untrusted devices
    """

    def __init__(self, jing=None, registry=None):
        self._jing = jing
        self._registry = registry
        self._untrusted_healthy_count: dict[str, int] = {}

    def name(self) -> str:
        return "device_watchdog"

    def budget(self) -> ComputeBudget:
        return ComputeBudget(
            cpu_seconds=1.0,
            gpu_needed=False,
            ram_mb=32,
            network_io=True,  # May query device stats
            priority=8,  # Low priority
        )

    async def run(self, batch: list[ConversationTurn]) -> None:
        """Run the health check cycle."""
        registry = self._get_registry()
        if not registry:
            return

        jing = self._get_jing()

        try:
            devices = registry.get_all_devices()
        except Exception:
            devices = []

        for device in devices:
            try:
                is_online = device.is_online()
                is_trusted = device.is_trusted()

                # Log health to Jing
                if jing and is_online:
                    health_text = (
                        f"Device health: {device.name} ({device.device_id}), "
                        f"type={device.device_type.value}, "
                        f"trusted={is_trusted}, online={is_online}"
                    )
                    await jing.remember(health_text, role="system", metadata={
                        "source": "device_watchdog",
                        "device_id": device.device_id,
                        "trusted": is_trusted,
                    })

                # Track untrusted device reliability
                if not is_trusted:
                    if is_online:
                        self._untrusted_healthy_count[device.device_id] = \
                            self._untrusted_healthy_count.get(device.device_id, 0) + 1
                    else:
                        self._untrusted_healthy_count[device.device_id] = 0

                    # Suggest promotion if consistently healthy (10+ cycles)
                    if self._untrusted_healthy_count.get(device.device_id, 0) >= 10:
                        if jing:
                            suggestion = (
                                f"Trust suggestion: Device '{device.name}' "
                                f"({device.device_id}) has been consistently "
                                f"online for 10+ health checks. Consider "
                                f"promoting to TRUSTED."
                            )
                            await jing.remember(suggestion, role="system", metadata={
                                "source": "device_watchdog",
                                "action": "trust_suggestion",
                                "device_id": device.device_id,
                            })
                            logger.info(f"[DeviceWatchdog] Suggesting trust promotion for {device.name}")
                            # Reset counter so we don't spam
                            self._untrusted_healthy_count[device.device_id] = 0

            except Exception as e:
                logger.error(f"[DeviceWatchdog] Error checking {device.device_id}: {e}")

    def _get_jing(self):
        if self._jing is None:
            try:
                from velvet.shen.jing import Jing
                self._jing = Jing()
            except Exception:
                pass
        return self._jing

    def _get_registry(self):
        if self._registry is None:
            try:
                from velvet.devices import get_registry
                self._registry = get_registry()
            except Exception:
                pass
        return self._registry
