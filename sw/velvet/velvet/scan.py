"""
Device Discovery Module.

Scans the physical and digital environment to find devices that are NOT yet on the mesh.
"""

__all__ = [
    "ScannedDevice",
    "NetworkScanner",
    "ServiceScanner",
    "BLEScanner",
    "scan_all",
    "start_discovery_service",
    "stop_discovery_service",
]

import asyncio
import socket
import subprocess
import platform
import re
from dataclasses import dataclass, field
from typing import Any
from loguru import logger

# Optional imports
try:
    from bleak import BleakScanner as _BleakScanner
    BLEAK_AVAILABLE = True
except ImportError:
    BLEAK_AVAILABLE = False

try:
    from zeroconf import Zeroconf, ServiceBrowser, ServiceStateChange
    ZEROCONF_AVAILABLE = True
except ImportError:
    ZEROCONF_AVAILABLE = False


@dataclass
class ScannedDevice:
    """A device found during a scan."""
    id: str                      # MAC, IP, or UUID
    name: str
    scan_type: str               # "network", "ble", "mdns"
    ip_address: str = ""
    mac_address: str = ""
    ports: list[int] = field(default_factory=list)
    services: list[str] = field(default_factory=list)
    rssi: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class NetworkScanner:
    """Scans local network for IPs (ARP/Ping/Nmap)."""
    
    @staticmethod
    async def scan_arp() -> list[ScannedDevice]:
        """Scan local network using ARP (requires arp-scan or system arp)."""
        devices = []
        try:
            # Simple ARP scan implementation using subprocess
            # This is OS specific. For v1 we try a generic ping sweep or arp command.
            # Using 'arp -a' is the most cross-platform "easy" way without nmap
            
            cmd = ["arp", "-a"]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            
            output = stdout.decode()
            
            # Simple regex for finding IPs and MACs
            # Output format varies wildly by OS, this is a heuristic
            lines = output.split('\n')
            for line in lines:
                parts = line.split()
                if len(parts) >= 3:
                    # Very rough heuristic
                    ip = parts[0]
                    mac = parts[1]
                    if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip):
                        # Filter out multicast/broadcast
                        if ip.endswith(".255") or ip == "224.0.0.22":
                            continue
                            
                        devices.append(ScannedDevice(
                            id=ip,
                            name=f"Unknown Device ({ip})",
                            scan_type="network",
                            ip_address=ip,
                            mac_address=mac
                        ))
            
        except Exception as e:
            logger.warning(f"ARP scan failed: {e}")
            
        return devices

    @staticmethod
    async def scan_nmap(target_ip: str, ports: list[int] | None = None) -> dict:
        """Deep scan of a specific target. Uses nmap if available, else falls back to simple socket check."""
        results = {"ip": target_ip, "open_ports": [], "services": {}}
        ports_to_check = ports or [22, 5555, 80, 443, 7447, 554, 8554]
        
        # 1. Try Nmap if available
        try:
            cmd = ["nmap", "-sT", "-p", ",".join(map(str, ports_to_check)), target_ip]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            if proc.returncode == 0:
                output = stdout.decode()
                for line in output.split("\n"):
                    match = re.search(r"^(\d+)/tcp\s+open\s+(\S+)", line)
                    if match:
                        port = int(match.group(1))
                        service = match.group(2)
                        results["open_ports"].append(port)
                        results["services"][port] = service
                return results
        except FileNotFoundError:
            logger.debug("nmap not found, falling back to simple asyncio port scan")
        except Exception as e:
            logger.warning(f"nmap scan failed: {e}")
            
        # 2. Fallback to asyncio simple scan
        open_ports = []
        for port in ports_to_check:
            try:
                fut = asyncio.open_connection(target_ip, port)
                reader, writer = await asyncio.wait_for(fut, timeout=0.2)
                open_ports.append(port)
                writer.close()
                await writer.wait_closed()
            except (OSError, asyncio.TimeoutError):
                pass
                
        results["open_ports"] = open_ports
        return results


class ServiceScanner:
    """Scans for mDNS services (Zeroconf)."""
    
    def __init__(self):
        self.found_devices: dict[str, ScannedDevice] = {}
        self.zeroconf = None
        self.browser = None
        
    def start(self):
        if not ZEROCONF_AVAILABLE:
            logger.warning("Zeroconf not installed, skipping mDNS scan")
            return

        self.zeroconf = Zeroconf()
        services = ["_http._tcp.local.", "_ssh._tcp.local.", "_googlecast._tcp.local.", "_printer._tcp.local."]
        self.browser = ServiceBrowser(self.zeroconf, services, handlers=[self._on_service_state_change])
        logger.info("mDNS scanner started")
        
    def stop(self):
        if self.zeroconf:
            self.zeroconf.close()
            
    def _on_service_state_change(self, zeroconf, service_type, name, state_change):
        if state_change is ServiceStateChange.Added:
            info = zeroconf.get_service_info(service_type, name)
            if info:
                ip = socket.inet_ntoa(info.addresses[0]) if info.addresses else ""
                device = ScannedDevice(
                    id=f"{ip}_{service_type}",
                    name=name.split('.')[0],
                    scan_type="mdns",
                    ip_address=ip,
                    services=[service_type],
                    metadata={"port": info.port, "properties": {k.decode(): v.decode() if isinstance(v, bytes) else v for k, v in info.properties.items()}}
                )
                self.found_devices[device.id] = device
                # logger.debug(f"mDNS found: {name} at {ip}")


class BLEScanner:
    """Scans for Bluetooth LE devices."""
    
    @staticmethod
    async def scan(timeout: float = 5.0) -> list[ScannedDevice]:
        if not BLEAK_AVAILABLE:
            logger.warning("Bleak not installed, skipping BLE scan")
            return []
            
        devices = []
        try:
            found = await _BleakScanner.discover(timeout=timeout)
            for d in found:
                if d.name and d.name != "Unknown":
                    devices.append(ScannedDevice(
                        id=d.address,
                        name=d.name,
                        scan_type="ble",
                        mac_address=d.address,
                        rssi=d.rssi,
                        metadata={"details": str(d.details)}
                    ))
        except Exception as e:
            logger.warning(f"BLE scan error: {e}")
            
        return devices


async def scan_all() -> list[ScannedDevice]:
    """Run all scanners and aggregate results."""
    logger.info("Starting comprehensive device scan...")
    
    # Run active scans in parallel
    results = await asyncio.gather(
        NetworkScanner.scan_arp(),
        BLEScanner.scan(timeout=3.0),
        return_exceptions=True
    )
    
    # Collect results
    all_devices = []
    
    # Network results
    if isinstance(results[0], list):
        all_devices.extend(results[0])
        
    # BLE results
    if isinstance(results[1], list):
        all_devices.extend(results[1])
        
    logger.info(f"Scan complete. Found {len(all_devices)} devices.")
    return all_devices


# ============================================================================
# Discovery Service Lifecycle
# ============================================================================

_service_scanner: ServiceScanner | None = None

def start_discovery_service() -> None:
    """Start the background discovery service (mDNS)."""
    global _service_scanner
    if _service_scanner is None:
        _service_scanner = ServiceScanner()
        _service_scanner.start()

def stop_discovery_service() -> None:
    """Stop the background discovery service."""
    global _service_scanner
    if _service_scanner:
        _service_scanner.stop()
        _service_scanner = None
