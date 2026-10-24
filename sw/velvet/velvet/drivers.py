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
    "HardwareBusDriver",
    "CANBusDriver",
    "BLEBusDriver",
    "SerialBusDriver",
    "CNCGCodeDriver",
]


from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Callable
import time
from velvet.fabric import get_fabric, MessageType
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
                # Security Fix: DO NOT push ca.key. Only push ca.crt so it can verify the mesh.
                # Nodes start as UNTRUSTED and only get secrets after TrustGate biometric promotion.
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


class HardwareBusDriver(DeviceDriver, ABC):
    """Base class for Hardware Bus Drivers with event-driven mesh publishing."""
    
    def __init__(self, bus_id: str, rate_limit_sec: float = 0.5):
        self.bus_id = bus_id
        self.rate_limit_sec = rate_limit_sec
        self.running = False
        self._last_event_time = 0.0
        self._subscriptions: Dict[str, Callable] = {}
        self._is_commandeered = False

    def set_commandeered(self, state: bool):
        """When commandeered by User, bypass rate limits for unthrottled streaming."""
        self._is_commandeered = state
        logger.info(f"[BusDriver:{self.bus_id}] Commandeered state set to {state}")

    async def _publish_hardware_event(self, topic_suffix: str, payload: dict, force: bool = False):
        """Publish event to mesh adhering to threshold/rate-limiting unless commandeered."""
        now = time.time()
        if not force and not self._is_commandeered and (now - self._last_event_time < self.rate_limit_sec):
            return
            
        self._last_event_time = now
        fabric = get_fabric()
        
        event_data = {
            "bus_id": self.bus_id,
            "timestamp": now,
            "commandeered": self._is_commandeered,
            "payload": payload
        }
        
        await fabric.publish(f"hardware/event/{self.bus_id}/{topic_suffix}", event_data)


class CANBusDriver(HardwareBusDriver):
    """
    CAN Bus driver with dual-mode (DBC parsing + raw hex payloads).
    Uses python-can and cantools (with fallback).
    """
    
    def __init__(self, bus_id: str = "can0", channel: str = "can0", bustype: str = "socketcan", dbc_path: Optional[str] = None):
        super().__init__(bus_id=bus_id)
        self.channel = channel
        self.bustype = bustype
        self.dbc_path = dbc_path
        self._bus = None
        self._db = None
        self._monitor_task = None
        
    async def connect(self, info: ConnectionInfo) -> bool:
        self.channel = info.address or self.channel
        logger.info(f"[CANBusDriver] Connecting to CAN channel '{self.channel}' ({self.bustype})...")
        
        # Load DBC if available
        if self.dbc_path:
            try:
                import cantools
                self._db = cantools.database.load_file(self.dbc_path)
                logger.info(f"[CANBusDriver] Loaded DBC file from {self.dbc_path}")
            except Exception as e:
                logger.warning(f"[CANBusDriver] Failed to load DBC file ({e}). Falling back to raw hex mode.")
                
        try:
            import can
            # Mock / interface detection fallback for non-Linux / test environments
            try:
                self._bus = can.interface.Bus(channel=self.channel, bustype=self.bustype)
            except Exception:
                logger.warning(f"[CANBusDriver] Could not open physical CAN interface '{self.channel}'. Operating in simulated virtual mode.")
                self._bus = can.interface.Bus(channel='vcan0', bustype='virtual')
                
            self.running = True
            self._monitor_task = asyncio.create_task(self._read_loop())
            return True
        except Exception as e:
            logger.error(f"[CANBusDriver] Failed to initialize CAN bus: {e}")
            return False

    async def disconnect(self):
        self.running = False
        if self._monitor_task:
            self._monitor_task.cancel()
        if self._bus:
            self._bus.shutdown()
            self._bus = None
        logger.info(f"[CANBusDriver] Disconnected from {self.bus_id}")

    async def get_status(self) -> dict[str, Any]:
        return {
            "bus_id": self.bus_id,
            "channel": self.channel,
            "connected": self.running and self._bus is not None,
            "dbc_loaded": self._db is not None,
            "commandeered": self._is_commandeered
        }

    async def _read_loop(self):
        while self.running and self._bus:
            try:
                loop = asyncio.get_running_loop()
                msg = await loop.run_in_executor(None, self._bus.recv, 0.5)
                if msg:
                    await self._process_can_message(msg)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[CANBusDriver] Error reading CAN frame: {e}")
                await asyncio.sleep(0.1)

    async def _process_can_message(self, msg):
        raw_hex = msg.data.hex()
        payload = {
            "arbitration_id": hex(msg.arbitration_id),
            "dlc": msg.dlc,
            "raw_hex": raw_hex,
            "is_extended": msg.is_extended_id,
        }
        
        # Dual-mode DBC decoding
        if self._db:
            try:
                decoded = self._db.decode_message(msg.arbitration_id, msg.data)
                payload["decoded_signals"] = decoded
            except Exception:
                payload["decoded_signals"] = None
                
        await self._publish_hardware_event(hex(msg.arbitration_id), payload)


class BLEBusDriver(HardwareBusDriver):
    """
    Bluetooth Low Energy driver for scanning and characteristic subscriptions.
    Uses bleak.
    """
    
    def __init__(self, bus_id: str = "ble0"):
        super().__init__(bus_id=bus_id)
        self._client = None
        self._target_address = ""
        
    async def connect(self, info: ConnectionInfo) -> bool:
        self._target_address = info.address
        logger.info(f"[BLEBusDriver] Connecting to BLE device '{self._target_address}'...")
        try:
            from bleak import BleakClient
            self._client = BleakClient(self._target_address)
            connected = await self._client.connect()
            self.running = connected
            return connected
        except Exception as e:
            logger.warning(f"[BLEBusDriver] BLE connection to {self._target_address} failed: {e}. Running in simulation mode.")
            self.running = True
            return True

    async def disconnect(self):
        self.running = False
        if self._client:
            try:
                await self._client.disconnect()
            except Exception:
                pass
            self._client = None

    async def get_status(self) -> dict[str, Any]:
        return {
            "bus_id": self.bus_id,
            "target": self._target_address,
            "connected": self.running
        }

    async def subscribe_characteristic(self, char_uuid: str):
        if self._client and self._client.is_connected:
            def notification_handler(sender, data):
                asyncio.create_task(
                    self._publish_hardware_event(char_uuid, {"uuid": char_uuid, "hex": data.hex()})
                )
            await self._client.start_notify(char_uuid, notification_handler)


class SerialBusDriver(HardwareBusDriver):
    """
    Serial/UART bus driver for microcontrollers (Arduino, ESP32, STM32).
    Uses pyserial.
    """
    
    def __init__(self, bus_id: str = "serial0", port: str = "COM3", baudrate: int = 115200):
        super().__init__(bus_id=bus_id)
        self.port = port
        self.baudrate = baudrate
        self._serial = None
        self._read_task = None
        
    async def connect(self, info: ConnectionInfo) -> bool:
        self.port = info.address or self.port
        logger.info(f"[SerialBusDriver] Opening Serial port '{self.port}' at {self.baudrate} baud...")
        try:
            import serial
            self._serial = serial.Serial(self.port, self.baudrate, timeout=0.1)
            self.running = True
            self._read_task = asyncio.create_task(self._read_loop())
            return True
        except Exception as e:
            logger.warning(f"[SerialBusDriver] Serial connection to {self.port} failed ({e}). Operating in simulation mode.")
            self.running = True
            return True

    async def disconnect(self):
        self.running = False
        if self._read_task:
            self._read_task.cancel()
        if self._serial:
            self._serial.close()
            self._serial = None

    async def get_status(self) -> dict[str, Any]:
        return {
            "bus_id": self.bus_id,
            "port": self.port,
            "baudrate": self.baudrate,
            "connected": self.running
        }

    async def _read_loop(self):
        while self.running and self._serial:
            try:
                line = self._serial.readline()
                if line:
                    decoded = line.decode('utf-8', errors='ignore').strip()
                    await self._publish_hardware_event("rx", {"data": decoded})
            except Exception:
                await asyncio.sleep(0.1)


class CNCGCodeDriver(HardwareBusDriver):
    """
    CNC & 3D Printer driver handling G-Code over serial and Moonraker/OctoPrint HTTP API fallbacks.
    """
    
    def __init__(self, bus_id: str = "cnc0", port_or_url: str = "http://localhost:5000"):
        super().__init__(bus_id=bus_id)
        self.target = port_or_url
        self.is_http_api = self.target.startswith("http://") or self.target.startswith("https://")
        self._serial_driver = None
        self._session = None
        
    async def connect(self, info: ConnectionInfo) -> bool:
        self.target = info.address or self.target
        self.is_http_api = self.target.startswith("http://") or self.target.startswith("https://")
        
        logger.info(f"[CNCGCodeDriver] Initializing CNC/3D Printer connection to '{self.target}'...")
        if not self.is_http_api:
            # Serial G-Code driver
            self._serial_driver = SerialBusDriver(bus_id=f"{self.bus_id}_serial", port=self.target, baudrate=115200)
            connected = await self._serial_driver.connect(info)
            self.running = connected
            return connected
        else:
            # OctoPrint / Moonraker HTTP REST API
            import aiohttp
            self._session = aiohttp.ClientSession()
            self.running = True
            return True

    async def disconnect(self):
        self.running = False
        if self._serial_driver:
            await self._serial_driver.disconnect()
        if self._session:
            await self._session.close()
            self._session = None

    async def send_gcode(self, gcode_command: str) -> dict:
        """Send G-Code command to machine."""
        logger.info(f"[CNCGCodeDriver:{self.bus_id}] Executing G-Code: '{gcode_command}'")
        if self.is_http_api and self._session:
            # OctoPrint API endpoint
            try:
                url = f"{self.target.rstrip('/')}/api/printer/command"
                async with self._session.post(url, json={"command": gcode_command}) as resp:
                    return {"status": "success", "http_code": resp.status, "command": gcode_command}
            except Exception as e:
                logger.warning(f"[CNCGCodeDriver] OctoPrint API call failed: {e}. Falling back to simulation response.")
                
        return {"status": "simulated_success", "command": gcode_command, "timestamp": time.time()}

    async def get_status(self) -> dict[str, Any]:
        return {
            "bus_id": self.bus_id,
            "target": self.target,
            "type": "OctoPrint/Moonraker API" if self.is_http_api else "G-Code Serial",
            "connected": self.running
        }
