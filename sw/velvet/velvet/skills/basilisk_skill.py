"""
Basilisk Protocol Skills for Velvet Nadir.

Enables explicit, secure P2P communication for authentication and sensitive queries.
"""

from loguru import logger
import asyncio
import time
from typing import Any

from ..skills import (
    skill,
    SkillCategory,
    SkillParameter,
    SkillResult,
    AutonomyLevel,
)
from ..fabric import get_fabric, MessageType
from ..basilisk import BasiliskEnclave, sanitize_for_hun

@skill(
    name="basilisk_authenticate",
    description="Perform a one-time biometric authentication of a remote device via the Basilisk Protocol.",
    category=SkillCategory.PERCEPTION,
    parameters=[
        SkillParameter("device_id", "string", "The ID of the remote device to authenticate (e.g., 'garage_camera')"),
        SkillParameter("mode", "string", "Authentication mode: 'face', 'voice', or 'both'", required=False, default="both")
    ],
    autonomy=AutonomyLevel.LEVEL_0,  # Explicitly passive
    tags=["security", "basilisk", "auth"]
)
async def basilisk_authenticate(device_id: str, mode: str = "both") -> SkillResult:
    """Explicitly pull a biometric frame from a device and verify identity."""
    try:
        fabric = get_fabric()
        
        # 1. Request the frame/audio from the device
        # This assumes the device has a Queryable listener for Basilisk capture
        topic = f"mesh/device/{device_id}/capture_basilisk"
        payload = {"mode": mode, "reason": "Explicit owner authentication request"}
        
        logger.info(f"[Basilisk] Initiating explicit auth for {device_id}...")
        
        # 2. Execute P2P Request (Basilisk Protocol)
        responses = await fabric.request(topic, payload, timeout_sec=10.0)
        if not responses:
            return SkillResult.fail(f"Device {device_id} did not respond to Basilisk request. Connection timed out.")
            
        # 3. Process the response through the Local Basilisk Auth Handler
        # This keeps the raw biometric data trapped in a P2P request to the local TrustGate
        auth_msg = responses[0]
        
        # Ensure we have data
        if not auth_msg.payload:
             return SkillResult.fail(f"Device {device_id} returned an empty payload.")

        # Self-query to the local TrustGate handler
        result_msgs = await fabric.request(MessageType.BASILISK_AUTH.value, auth_msg.payload)
        
        if not result_msgs:
             return SkillResult.fail("Local Basilisk authentication pipeline failed to process the result.")
             
        # Result from TrustGate.handle_basilisk_auth is already sanitized for metadata
        result_data = result_msgs[0].payload
        verified = result_data.get("verified", False)
        
        if verified:
            return SkillResult.ok(
                data={"verified": True, "device": device_id},
                speak=f"Basilisk Protocol successful. {device_id} identity verified. Trust has been promoted."
            )
        else:
            return SkillResult.fail(f"Biometric verification failed for {device_id}. The identity does not match the owner.")

    except Exception as e:
        logger.error(f"Basilisk Auth Skill error: {e}")
        return SkillResult.fail(f"Basilisk Protocol error: {str(e)}")


@skill(
    name="basilisk_query",
    description="Send a point-to-point secure query to a remote node via the Basilisk Protocol (No long-term persistence).",
    category=SkillCategory.DIGITAL,
    parameters=[
        SkillParameter("topic", "string", "The Zenoh topic to query (e.g. 'sys/status')"),
        SkillParameter("payload", "dict", "The request data (dict)")
    ],
    autonomy=AutonomyLevel.LEVEL_0,
    tags=["security", "basilisk", "rpc"]
)
async def basilisk_query(topic: str, payload: dict) -> SkillResult:
    """Generic P2P Basilisk query."""
    try:
        fabric = get_fabric()
        
        # Use a logical enclave to ensure local cleanup
        async with BasiliskEnclave(f"query_{topic[:10]}") as enclave:
            # Track the input payload
            enclave.track(payload)
            
            logger.info(f"[Basilisk] Executing secure P2P query: {topic}")
            responses = await fabric.request(topic, payload)
            
            if not responses:
                return SkillResult.fail(f"No response received for Basilisk query on: {topic}")
            
            # Sanitize the response immediately for Hun (LLM)
            raw_resp = responses[0].payload
            
            # Track raw response for deletion
            enclave.track(raw_resp)
            
            safe_resp = sanitize_for_hun(raw_resp)
            
            return SkillResult.ok(
                data=safe_resp, 
                speak="Basilisk secure query completed and data vaporized from memory."
            )
            
    except Exception as e:
        logger.error(f"Basilisk Query error: {e}")
        return SkillResult.fail(f"Basilisk Protocol error: {str(e)}")
