"""
Honeypot Port Binder: Binds standard attack ports to the 4-track vulnerability web.
Standard ports (22, 80, 443, etc.) are traps; real services live on high random ports.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Callable, Any

from .honeypot_vulns import (
    Track1SloppyDeveloper,
    Track2CloudInfrastructure,
    Track3IoTInternalNetwork,
    Track4ExposedManagement,
    log_honeypot_forensic,
)

logger = logging.getLogger(__name__)


class HoneypotPortBinder:
    """
    Binds standard network ports to the 4-track deception web.
    In production, binds 0.0.0.0 on standard ports (22, 80, 443, 3306, etc.).
    Supports port offsets or custom test port maps for unprivileged execution.
    """

    def __init__(self, port_offset: int = 0, port_map: Any = None):
        self.port_offset = port_offset
        self.port_map = port_map
        self.servers: List[asyncio.Server] = []
        self.bound_ports: Dict[int, int] = {}  # standard_port -> actual_bound_port

        self.track1 = Track1SloppyDeveloper()
        self.track2 = Track2CloudInfrastructure()
        self.track3 = Track3IoTInternalNetwork()
        self.track4 = Track4ExposedManagement()

    def get_track_handlers(self) -> List[Tuple[int, Callable]]:
        """Map standard ports to track handlers."""
        return [
            # Track 1: Sloppy Dev
            (22, self.track1.handle_ssh),
            (3306, self.track1.handle_mysql),
            (8080, self.track1.handle_rest_debug),
            # Track 2: Cloud Infra
            (443, self.track2.handle_https_admin),
            (9000, self.track2.handle_s3_minio),
            (5432, self.track2.handle_postgres),
            # Track 3: IoT / Network
            (80, self.track3.handle_openwrt_http),
            (6379, self.track3.handle_redis),
            (27017, self.track3.handle_mongodb),
            # Track 4: Exposed Management
            (5900, self.track4.handle_vnc),
            (2375, self.track4.handle_docker_api),
            (8443, self.track4.handle_k8s_dashboard),
        ]

    async def start(self, host: str = "0.0.0.0", specific_ports: Optional[List[int]] = None) -> Dict[int, int]:
        """
        Start honeypot listeners.
        Returns dict mapping standard_port -> actual_bound_port.
        """
        handlers = self.get_track_handlers()
        for std_port, handler in handlers:
            if specific_ports is not None and std_port not in specific_ports:
                continue

            target_port = std_port + self.port_offset

            # Factory function to capture handler and target_port cleanly in closure
            def make_client_callback(h):
                async def _cb(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
                    peer = writer.get_extra_info("peername")
                    client_ip = peer[0] if peer else "unknown"
                    try:
                        await h(reader, writer, client_ip)
                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        logger.error(f"[Honeypot] Handler error on port {std_port}: {e}")
                        writer.close()
                return _cb

            try:
                server = await asyncio.start_server(make_client_callback(handler), host, target_port)
                self.servers.append(server)
                self.bound_ports[std_port] = target_port
                logger.info(f"[HoneypotPortBinder] Honeypot bound: std {std_port} -> listening on {host}:{target_port}")
            except OSError as e:
                logger.warning(f"[HoneypotPortBinder] Could not bind port {target_port} for std {std_port}: {e}")

        return self.bound_ports

    async def stop(self) -> None:
        """Stop all running honeypot servers."""
        for server in self.servers:
            server.close()
            await server.wait_closed()
        self.servers.clear()
        self.bound_ports.clear()
        logger.info("[HoneypotPortBinder] All honeypot listeners stopped.")
