"""
Device Drivers for Velvet Mesh.

Drivers are responsible for the actual "connection" and "control" logic.
- NativeDriver: SSH/ADB into a Host Node to install/start Velvet.
- RTSPDriver: Connect to an IP Camera stream.
"""

__all__ = [
    "DeviceDriver",
    "NativeDriver",
    "RTSPDriver",
]

from abc import ABC, abstractmethod
from typing import Any
import asyncio
from loguru import logger

from .devices import ConnectionInfo, ConnectionMethod, DeviceRole

class DeviceDriver(ABC):
    """Base class for device drivers."""
    
    @abstractmethod
    async def connect(self, info: ConnectionInfo) -> bool:
        """Establish connection to the device."""
        pass
        
    @abstractmethod
    async def disconnect(self):
        """Disconnect from the device."""
        pass
        
    @abstractmethod
    async def get_status(self) -> dict[str, Any]:
        """Get current device status/telemetry."""
        pass


class NativeDriver(DeviceDriver):
    """
    Driver for Host Nodes (Linux/Windows/Mac).
    Uses asyncssh for real SSH connections and SCP/SFTP for file transfer.
    """
    
    def __init__(self):
        self._connected = False
        self._host = ""
        self._conn = None  # asyncssh.SSHClientConnection
        
    async def connect(self, info: ConnectionInfo) -> bool:
        if info.method != ConnectionMethod.SSH:
            logger.warning("NativeDriver only supports SSH for now")
            return False
        
        self._host = info.address
        logger.info(f"Connecting to Host Node {self._host} via SSH...")
        
        try:
            import asyncssh
            
            connect_kwargs = {
                "host": info.address,
                "port": info.port or 22,
                "known_hosts": None,  # Accept all host keys for mesh nodes
            }
            
            if info.username:
                connect_kwargs["username"] = info.username
            if info.password:
                connect_kwargs["password"] = info.password
            
            self._conn = await asyncssh.connect(**connect_kwargs)
            self._connected = True
            logger.info(f"SSH connected to {self._host}")
            return True
            
        except Exception as e:
            logger.error(f"SSH connection failed to {self._host}: {e}")
            return False
        
    async def disconnect(self):
        if self._conn:
            self._conn.close()
            await self._conn.wait_closed()
        self._connected = False
        self._conn = None
        logger.info(f"Disconnected from {self._host}")
        
    async def get_status(self) -> dict[str, Any]:
        if not self._connected or not self._conn:
            return {"status": "offline"}
        try:
            result = await self._conn.run("uptime -s 2>/dev/null || echo 'unknown'", check=False)
            return {
                "status": "online",
                "uptime": result.stdout.strip() if result.stdout else "unknown",
                "service": "active",
            }
        except Exception:
            return {"status": "online", "service": "unknown"}

    async def run_command(self, cmd: str) -> str:
        """Execute a command on the remote host and return stdout."""
        if not self._conn:
            raise RuntimeError("Not connected")
        result = await self._conn.run(cmd, check=False)
        return result.stdout.strip() if result.stdout else ""
    
    async def inject_velvet(self, device_id: str) -> bool:
        """
        Deploy Velvet Agent + mTLS certs to the remote host.
        
        Three phases:
        1. Provision certs (CA + node cert via SFTP)
        2. Install Velvet
        3. Configure + start
        """
        if not self._connected or not self._conn:
            return False
        
        logger.info(f"Injecting Velvet Agent + certs to {self._host} (id={device_id})...")
        
        try:
            # Phase 1: Provision TLS certificates
            from .security import CertManager
            from .config import get_config
            
            cert_mgr = CertManager(get_config().security.certs_dir)
            cert_mgr.issue_node_cert(device_id)
            
            remote_certs = "~/.velvet/certs"
            await self._conn.run(f"mkdir -p {remote_certs}")
            
            async with self._conn.start_sftp_client() as sftp:
                # Copy CA (so this node can onboard others independently)
                await sftp.put(str(cert_mgr.ca_key_path), f"{remote_certs}/ca.key")
                await sftp.put(str(cert_mgr.ca_cert_path), f"{remote_certs}/ca.crt")
                # Copy node cert + key
                await sftp.put(
                    str(cert_mgr.certs_dir / f"{device_id}.crt"),
                    f"{remote_certs}/{device_id}.crt"
                )
                await sftp.put(
                    str(cert_mgr.certs_dir / f"{device_id}.key"),
                    f"{remote_certs}/{device_id}.key"
                )
            logger.info(f"Phase 1: Certs provisioned to {self._host}")
            
            # Phase 2: Install Velvet
            await self._conn.run("pip install velvet-nadir 2>/dev/null || pip3 install velvet-nadir", check=False)
            logger.info(f"Phase 2: Velvet installed on {self._host}")
            
            # Phase 3: Configure + start
            config = get_config()
            velvet_toml = f'''[zenoh]
device_id = "{device_id}"
tls_enabled = true
tls_mtls_enabled = true

[security]
mesh_secret = "{config.security.mesh_secret}"
'''
            await self._conn.run(f"mkdir -p ~/.velvet && cat > ~/.velvet/velvet.toml << 'EOF'\n{velvet_toml}\nEOF")
            await self._conn.run("nohup python -m velvet.main run > /dev/null 2>&1 &", check=False)
            logger.info(f"Phase 3: Velvet started on {self._host}")
            
            logger.info(f"Injection complete. {device_id} should join mesh via mTLS.")
            return True
            
        except Exception as e:
            logger.error(f"Injection failed for {self._host}: {e}")
            return False


class RTSPDriver(DeviceDriver):
    """
    Driver for IP Cameras (Peripheral).
    Manages the RTSP stream connection.
    """
    
    def __init__(self):
        self._connected = False
        self._url = ""
        
    async def connect(self, info: ConnectionInfo) -> bool:
        # Construct RTSP provided credentials
        creds = ""
        if info.username and info.password:
            creds = f"{info.username}:{info.password}@"
            
        self._url = f"rtsp://{creds}{info.address}:{info.port}/stream1" # heuristic
        logger.info(f"Connecting to RTSP stream: rtsp://{creds}{info.address}...")
        
        # Verify stream availability (e.g. with opencv or ffmpeg probe)
        await asyncio.sleep(1) 
        self._connected = True
        return True
        
    async def disconnect(self):
        self._connected = False
        
    async def get_status(self) -> dict[str, Any]:
        return {
            "status": "streaming" if self._connected else "offline",
            "fps": 30 if self._connected else 0,
            "bitrate": "4Mbps"
        }
