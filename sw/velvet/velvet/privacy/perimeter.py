"""
Privacy Guard: Mesh Perimeter Enforcement & 4-Level Privacy Classification.

Two perimeters:
  1. Mesh vs Internet — nothing leaves the mesh without explicit consent
  2. Trusted vs Untrusted within mesh — UNTRUSTED devices can be USED
     (compute, sensors) but get NO data back (no memory sync, no graph access)

And 4-level data classification:
  - PUBLIC (0)
  - PERSONAL (1)
  - SENSITIVE (2)
  - RESTRICTED (3)
"""

from __future__ import annotations

__all__ = [
    "PrivacyViolation",
    "PrivacyGuard",
    "PrivacyLevel",
    "PrivacyClassifier",
    "get_privacy_guard",
]

import re
from enum import IntEnum
from loguru import logger


class PrivacyViolation(Exception):
    """Raised when an operation would violate the privacy perimeter."""
    pass


class PrivacyLevel(IntEnum):
    """
    4-level data classification. Higher = more restricted.
    
    Routing rules:
    - PUBLIC:     Cloud ✅  Mesh (all) ✅  Store plaintext ✅
    - PERSONAL:   Cloud ✅* Mesh (trusted) ✅  Store plaintext ✅
    - SENSITIVE:  Cloud ✅* Mesh (trusted) ✅  Store encrypted ✅
    - RESTRICTED: Cloud ❌  Mesh ❌  Store encrypted+ephemeral ✅ (stay on device forever)
    
    * = Must pass through MirageProxy first
    """
    PUBLIC = 0
    PERSONAL = 1
    SENSITIVE = 2
    RESTRICTED = 3


class PrivacyClassifier:
    """
    Classifies content into PrivacyLevel tiers.
    
    Multi-strategy approach:
    1. Data type check — biometric types → RESTRICTED instantly
    2. Regex patterns — SSN, credit card, Aadhaar, Passport → SENSITIVE instantly
    3. Keyword heuristics — medical, financial, gossip, Aadhaar, Passport → SENSITIVE
    4. Personal context keywords — schedules, preferences → PERSONAL
    5. NER model (optional, in MirageProxy) — catches names, addresses, orgs
    6. Default → PUBLIC
    """
    
    RESTRICTED_DATA_TYPES = {
        "face_embedding", "voice_embedding", "raw_audio",
        "fingerprint", "retina", "biometric", "person",
    }
    
    RESTRICTED_KEYWORDS = [
        "password", "passwd", "passcode", "secret key", "private key",
        "api key", "api_key", "seed phrase", "recovery phrase",
        "master password", "credential",
    ]
    
    SENSITIVE_PATTERNS = [
        r'\b\d{3}-\d{2}-\d{4}\b',                  # SSN
        r'\b(?:\d{4}[-\s]?){3}\d{4}\b',             # Credit card
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email
        r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b',       # Phone
        r'\+\d{1,3}[-.\s]?\d{3,14}\b',              # International phone
        r'\b\d{4}\s\d{4}\s\d{4}\b',                  # Aadhaar Card (spaced)
        r'\b\d{12}\b',                              # Aadhaar Card (plain)
        r'\b[A-Z][0-9]{7}\b',                        # Passport (Indian format)
    ]
    
    SENSITIVE_KEYWORDS = [
        "aadhar", "aadhaar", "passport", "social security", "credit card",
        "blood pressure", "diagnosis", "prescription", "medication",
        "symptoms", "blood test", "cholesterol", "heart rate",
        "therapy session", "mental health", "anxiety", "depression",
        "blood sugar", "insulin", "allergies", "surgery", "medical record",
        "bank account", "routing number", "account number",
        "credit score", "salary", "income", "tax return",
        "investment portfolio", "mortgage", "loan balance",
        "don't tell anyone", "between us", "secret about",
        "heard that", "apparently they", "cheating on", "having an affair",
        "getting divorced", "fired from", "got arrested", "in trouble with",
        "don't mention", "keep this quiet", "off the record",
        "sleeping with", "hooking up", "broke up with",
        "home address", "lives at", "staying at",
    ]
    
    PERSONAL_KEYWORDS = [
        "schedule", "appointment", "reminder", "preference",
        "birthday", "my address", "phone number", "contact",
        "my name", "my email", "meeting with", "call with",
        "pick up", "drop off", "my doctor", "my lawyer",
        "my kids", "my wife", "my husband", "my partner",
        "my boss", "my friend", "my family",
    ]
    
    def classify(self, text: str, data_type: str = "") -> PrivacyLevel:
        """
        Classify content into a privacy tier.
        Returns the HIGHEST (most restrictive) level detected.
        """
        if data_type in self.RESTRICTED_DATA_TYPES:
            return PrivacyLevel.RESTRICTED
            
        text_lower = text.lower()
        
        for kw in self.RESTRICTED_KEYWORDS:
            if kw in text_lower:
                return PrivacyLevel.RESTRICTED
                
        for pattern in self.SENSITIVE_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return PrivacyLevel.SENSITIVE
                
        for kw in self.SENSITIVE_KEYWORDS:
            if kw in text_lower:
                return PrivacyLevel.SENSITIVE
                
        for kw in self.PERSONAL_KEYWORDS:
            if kw in text_lower:
                return PrivacyLevel.PERSONAL

        # Check PIIDetector for PII findings (e.g. names) to align classification with MirageProxy
        try:
            from velvet.mirage import PIIDetector, PIIType
            detector = PIIDetector()
            findings = detector.scan(text)
            if findings:
                has_restricted = any(f.pii_type in (PIIType.PASSWORD, PIIType.CUSTOM_SECRET) for f in findings)
                if has_restricted:
                    return PrivacyLevel.RESTRICTED
                
                has_sensitive = any(f.pii_type in (
                    PIIType.SSN, PIIType.CREDIT_CARD, PIIType.EMAIL, PIIType.PHONE,
                    PIIType.AADHAR, PIIType.PASSPORT, PIIType.MEDICAL, PIIType.FINANCIAL, PIIType.GOSSIP
                ) for f in findings)
                if has_sensitive:
                    return PrivacyLevel.SENSITIVE
                
                return PrivacyLevel.PERSONAL
        except Exception as e:
            logger.debug(f"[PrivacyClassifier] PIIDetector error: {e}")
                
        return PrivacyLevel.PUBLIC


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

    def biometric_auto_restrict(self, data_type: str) -> bool:
        """DEPRECATED: Use PrivacyClassifier.classify(data_type=...) instead."""
        return PrivacyClassifier().classify("", data_type=data_type) == PrivacyLevel.RESTRICTED

    def can_sync_memory(self, device_id: str, data_type: str | None = None) -> bool:
        """
        Can we sync memory to this device?

        Only TRUSTED mesh peers get memory sync.
        RESTRICTED data (such as biometrics) is never synced (stay on device forever).
        """
        if data_type and self.biometric_auto_restrict(data_type):
            return False
            
        if not self._is_mesh_peer(device_id):
            return False
        return self._is_trusted_peer(device_id)

    def can_route_task(self, device_id: str) -> bool:
        """
        Can we route a compute task to this device?

        Any mesh device can receive compute tasks — we USE even untrusted devices.
        """
        return self._is_mesh_peer(device_id)

    def can_receive_data(self, device_id: str, data_type: str | None = None) -> bool:
        """
        Can this device receive our data (memories, secrets, etc.)?

        Same as can_sync_memory — only trusted peers, no restricted data.
        """
        return self.can_sync_memory(device_id, data_type)

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
        """
        if not self._is_mesh_peer(device_id):
            logger.debug(f"[PrivacyGuard] Blocked memory sync to {device_id}: not a mesh peer")
            return False

        if not self._is_trusted_peer(device_id):
            logger.debug(f"[PrivacyGuard] Blocked memory sync to {device_id}: untrusted device")
            return False

        return True

    def is_safe_to_send(self, text: str, destination: str,
                         level: PrivacyLevel | None = None) -> bool:
        """
        Check if content is safe to send to a destination.
        
        Rules:
        - Mesh trusted peers: PUBLIC, PERSONAL, and SENSITIVE allowed. RESTRICTED blocked (stay on device forever).
        - Mesh untrusted peers: PUBLIC only
        - Cloud/internet: PUBLIC only (PERSONAL+ must be scrambled/sanitized first)
        """
        is_mesh = self._is_mesh_peer(destination)
        is_trusted = is_mesh and self._is_trusted_peer(destination)
        
        # Mesh trusted peers can receive PUBLIC, PERSONAL, SENSITIVE, but NOT RESTRICTED
        if is_trusted:
            if level == PrivacyLevel.RESTRICTED:
                logger.warning(
                    f"[PrivacyGuard] RESTRICTED data blocked from leaving local device to trusted peer: {destination}"
                )
                return False
            return True
        
        # For everything else (cloud, untrusted mesh), check content
        if level is not None:
            if level > PrivacyLevel.PUBLIC:
                logger.warning(
                    f"[PrivacyGuard] {level.name} data blocked from "
                    f"{'untrusted peer' if is_mesh else 'cloud'}: {destination}"
                )
                return False
            return True
        
        # Heuristic PII detection (fallback path)
        # If ANY PII is detected, block. Caller should use MirageProxy instead.
        from velvet.mirage import PIIDetector
        detector = PIIDetector()
        findings = detector.scan(text)
        if findings:
            logger.warning(
                f"[PrivacyGuard] Detected {len(findings)} PII/sensitive item(s) in outbound "
                f"text, blocking send to {destination}. Use MirageProxy for "
                f"safe cloud interaction."
            )
            return False
        
        return True


_privacy_guard: PrivacyGuard | None = None

def get_privacy_guard() -> PrivacyGuard:
    """Get or create the global PrivacyGuard singleton."""
    global _privacy_guard
    if _privacy_guard is None:
        _privacy_guard = PrivacyGuard()
    return _privacy_guard
