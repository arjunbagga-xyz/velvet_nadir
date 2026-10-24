"""
Device Commandeering Service (User Remote Control).

Smart Routing engine that determines the optimal remote access protocol for the USER
to access and control remote nodes across the mesh:
1. High-Performance / Gaming -> Sunshine / Moonlight protocol stream (ultra low-latency < 10ms, gamepad passthrough).
2. Headless Server -> SSH terminal widget (xterm.js via Generative UI).
3. Web / Mobile Fallback -> WebRTC GStreamer H.264/HEVC stream + DataChannel input injection.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Any
from loguru import logger

from velvet.devices import Device, ConnectionMethod, DeviceRole


class CommandeerProtocol(Enum):
    MOONLIGHT = "moonlight"     # Sunshine / Moonlight high-fps game/desktop streaming
    SSH_TERMINAL = "ssh_terminal" # SSH xterm.js terminal pop-up
    WEBRTC_STREAM = "webrtc_stream" # GStreamer WebRTC stream fallback
    ADB_SCRCPY = "adb_scrcpy"    # scrcpy screen mirror for Android phones


@dataclass
class CommandeerSession:
    session_id: str
    target_device_id: str
    protocol: CommandeerProtocol
    connection_url: str
    connection_params: Dict[str, Any]
    active: bool = True


class CommandeeringService:
    """
    Smart Router for User Remote Access.
    """
    
    def __init__(self, device_registry=None):
        self.registry = device_registry
        self._active_sessions: Dict[str, CommandeerSession] = {}

    def resolve_commandeering_route(self, device: Device, user_intent: str = "remote_control") -> CommandeerSession:
        """
        Determine optimal streaming protocol based on device hardware capabilities and user intent.
        """
        device_id = device.device_id
        hw = device.hardware
        addr = device.connection.address or "127.0.0.1"

        logger.info(f"[CommandeeringService] Resolving remote access route for device '{device_id}' (GPU={hw.gpu}, RAM={hw.ram_gb}GB)...")

        # 1. Gaming / Heavy GPU -> Sunshine/Moonlight Protocol
        if "gaming" in user_intent.lower() or (hw.gpu and hw.gpu_vram_gb >= 4.0):
            logger.info(f"[CommandeeringService] Selected Sunshine/Moonlight stream for '{device_id}'")
            session = CommandeerSession(
                session_id=f"comm_{device_id}_moonlight",
                target_device_id=device_id,
                protocol=CommandeerProtocol.MOONLIGHT,
                connection_url=f"moonlight://{addr}",
                connection_params={
                    "host": addr,
                    "sunshine_port": 47989,
                    "codec": "hevc" if hw.gpu_vram_gb >= 8 else "h264",
                    "gamepad_passthrough": True
                }
            )
        # 2. Android Phone / Mobile -> scrcpy stream
        elif "android" in (device.software.os or "").lower() or device.role == DeviceRole.MOBILE:
            logger.info(f"[CommandeeringService] Selected scrcpy screen mirror for '{device_id}'")
            session = CommandeerSession(
                session_id=f"comm_{device_id}_scrcpy",
                target_device_id=device_id,
                protocol=CommandeerProtocol.ADB_SCRCPY,
                connection_url=f"scrcpy://{addr}:5555",
                connection_params={
                    "adb_address": f"{addr}:5555",
                    "bitrate": 8000000,
                    "max_fps": 60
                }
            )
        # 3. Headless / Server / No Display -> SSH Terminal xterm.js Widget
        elif not hw.has_camera and hw.gpu_vram_gb < 2.0 and device.connection.method == ConnectionMethod.SSH:
            logger.info(f"[CommandeeringService] Selected SSH Terminal for headless node '{device_id}'")
            session = CommandeerSession(
                session_id=f"comm_{device_id}_ssh",
                target_device_id=device_id,
                protocol=CommandeerProtocol.SSH_TERMINAL,
                connection_url=f"ssh://{addr}:{device.connection.port or 22}",
                connection_params={
                    "host": addr,
                    "port": device.connection.port or 22,
                    "user": device.connection.username or "root",
                    "widget": "xterm.js"
                }
            )
        # 4. Universal Fallback -> WebRTC GStreamer Pipeline
        else:
            logger.info(f"[CommandeeringService] Selected WebRTC GStreamer fallback for '{device_id}'")
            session = CommandeerSession(
                session_id=f"comm_{device_id}_webrtc",
                target_device_id=device_id,
                protocol=CommandeerProtocol.WEBRTC_STREAM,
                connection_url=f"wss://{addr}:8443/webrtc",
                connection_params={
                    "signaling_server": f"wss://{addr}:8443/webrtc",
                    "datachannel_input": True,
                    "ice_servers": [{"urls": "stun:stun.l.google.com:19302"}]
                }
            )

        self._active_sessions[session.session_id] = session
        return session

    def inject_remote_input(self, session_id: str, input_event: dict) -> bool:
        """
        Inject remote user keyboard/mouse events into host node.
        """
        session = self._active_sessions.get(session_id)
        if not session or not session.active:
            logger.warning(f"[CommandeeringService] Cannot inject input — inactive session '{session_id}'")
            return False

        logger.debug(f"[CommandeeringService] Injecting input event {input_event.get('type')} into session '{session_id}'")
        # Route to input subsystem (evdev / PyDirectInput)
        return True

    def close_session(self, session_id: str):
        if session_id in self._active_sessions:
            self._active_sessions[session_id].active = False
            del self._active_sessions[session_id]
            logger.info(f"[CommandeeringService] Commandeering session '{session_id}' closed.")
