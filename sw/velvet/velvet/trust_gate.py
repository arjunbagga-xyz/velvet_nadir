"""
Biometric enforcement layer for trust-sensitive operations.
"""

from __future__ import annotations

import time
import uuid
import numpy as np
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from loguru import logger

from velvet.devices import TrustLevel
from velvet.errors import TrustGateError
from velvet.config import get_config
from velvet.basilisk import BasiliskEnclave
from velvet.fabric import VelvetMessage

if TYPE_CHECKING:
    from velvet.shen.xiang import XiangEngine


@dataclass
class TrustChangeRequest:
    """A pending request to change a device's trust level."""
    request_id: str
    device_id: str
    current_level: TrustLevel
    requested_level: TrustLevel
    reason: str
    verified: bool = False
    created_at: float = field(default_factory=time.time)
    expires_sec: float = 300  # 5 minute window to verify
    
    def is_expired(self) -> bool:
        return time.time() > self.created_at + self.expires_sec


class TrustGate:
    """
    Biometric enforcement layer for trust-sensitive operations.
    
    No device trust change can happen without:
    1. Face recognition match (via Xiàng) OR
    2. Voice recognition match (via Xiàng) OR
    3. Explicit UI button press (future Sprint 14/15)
    
    This is the ONLY path to promote/demote device trust.
    """
    
    def __init__(self, xiang: getattr(Any, 'XiangEngine', Any) | None = None):
        self._xiang = xiang
        self._pending_requests: dict[str, TrustChangeRequest] = {}
        self._config = get_config().trust_gate
        self._owner_key = self._config.owner_face_memory_key
        logger.info("[TrustGate] Initialized biometric enforcement layer.")

    async def request_trust_change(
        self, 
        device_id: str, 
        current_level: TrustLevel,
        requested_level: TrustLevel,
        reason: str
    ) -> TrustChangeRequest:
        """Create a pending trust change that requires biometric auth."""
        # Cleanup expired ones
        self._cleanup_expired()
        
        request_id = f"req_{uuid.uuid4().hex[:8]}"
        req = TrustChangeRequest(
            request_id=request_id,
            device_id=device_id,
            current_level=current_level,
            requested_level=requested_level,
            reason=reason,
            expires_sec=self._config.verification_timeout_sec
        )
        self._pending_requests[request_id] = req
        logger.info(f"[TrustGate] Created request {request_id} for device {device_id} -> {requested_level.value}")
        return req

    async def verify_biometric(
        self, 
        request_id: str,
        frame: np.ndarray | None = None,
        audio: np.ndarray | None = None
    ) -> bool:
        """Verify the requestor's identity via face/voice."""
        if request_id not in self._pending_requests:
            logger.warning(f"[TrustGate] Request {request_id} not found or expired.")
            return False
            
        req = self._pending_requests[request_id]
        if req.is_expired():
            del self._pending_requests[request_id]
            logger.warning(f"[TrustGate] Request {request_id} has expired.")
            return False

        is_owner = await self.is_owner_verified(frame, audio)
        if is_owner or not self._config.require_biometric:
            req.verified = True
            logger.info(f"[TrustGate] Request {request_id} verified.")
            return True
        else:
            logger.warning(f"[TrustGate] Verification failed for {request_id}.")
            return False

    async def execute_change(self, request_id: str) -> bool:
        """Execute a verified trust change. Fails if not verified."""
        if request_id not in self._pending_requests:
            raise TrustGateError(f"Request {request_id} not found")
            
        req = self._pending_requests[request_id]
        if req.is_expired():
            del self._pending_requests[request_id]
            raise TrustGateError(f"Request {request_id} expired")
            
        if not req.verified and self._config.require_biometric:
            raise TrustGateError(f"Request {request_id} is not verified. Biometric auth required.")
            
        # Execute the change
        try:
            from velvet.devices import get_registry
            registry = get_registry()
            device = registry.get_device(req.device_id)
            if not device:
                raise TrustGateError(f"Device {req.device_id} not found in registry")
                
            # Internal call directly bypassing the property setter guard
            device._set_trust_level_internal(req.requested_level)
            await registry.register(device)
            
            logger.info(f"[TrustGate] Executed trust change for {req.device_id} to {req.requested_level.value}")
            del self._pending_requests[request_id]
            
            # Broadcast the change via fabric if possible
            try:
                from velvet.fabric import get_fabric, MessageType
                fabric = get_fabric()
                await fabric.publish(MessageType.TRUST_CHANGE_VERIFIED.value, {
                    "device_id": req.device_id,
                    "level": req.requested_level.value,
                    "request_id": request_id
                })
            except Exception as e:
                logger.warning(f"[TrustGate] Failed to broadcast trust change: {e}")
                
            return True
            
        except Exception as e:
            logger.error(f"[TrustGate] Error executing change: {e}")
            raise TrustGateError(f"Execute failed: {e}")

    async def is_owner_verified(
        self, 
        frame: np.ndarray | None = None, 
        audio: np.ndarray | None = None
    ) -> bool:
        """Quick check: is this the owner? Used for sensitive ops gate."""
        if not self._config.require_biometric:
            return True
            
        if not self._xiang:
            logger.warning("[TrustGate] XiangEngine not provided, cannot verify owner biometrically.")
            return False
            
        if frame is not None:
            faces = await self._xiang.identify_faces(frame)
            for face in faces:
                if face.name == self._owner_key and face.confidence >= get_config().xiang.recognition_threshold:
                    return True
                    
        if audio is not None:
            voice_match = await self._xiang.identify_voice(audio, 16000)
            if voice_match.name == self._owner_key and voice_match.confidence >= get_config().xiang.recognition_threshold:
                return True
                
        return False

    async def handle_basilisk_auth(self, msg: VelvetMessage) -> dict[str, Any] | None:
        """
        Query handler for the Basilisk Protocol authentication.
        
        Extracts face/voice from msg.payload (ephemeral) and verifies.
        Returns a minimal sanitized result.
        """
        # We wrap the entire verification in an enclave
        async with BasiliskEnclave("basilisk_auth") as enclave:
            from velvet.basilisk import sanitize_for_hun
            
            # Ensure the raw payload is tracked for deletion
            payload = enclave.track(msg.payload)
            
            frame = payload.get("frame")
            audio = payload.get("audio")
            
            # Perform verification
            is_owner = await self.is_owner_verified(frame, audio)
            
            # Construct scalar result
            result = {
                "verified": is_owner,
                "timestamp": time.time(),
                "node_id": get_config().device_id
            }
            
            logger.info(f"[Basilisk] Remote auth request processed. Result: {is_owner}")
            return result
        
    def _cleanup_expired(self):
        """Remove expired requests."""
        now = time.time()
        expired = [req_id for req_id, req in self._pending_requests.items() if req.created_at + req.expires_sec < now]
        for req_id in expired:
            del self._pending_requests[req_id]
