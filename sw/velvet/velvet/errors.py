"""
Standardized error hierarchy for Velvet Nadir.

All adapter-level errors inherit from VelvetAdapterError so callers can
catch a single base class instead of bare Exception.
"""

__all__ = [
    "VelvetError",
    "VelvetAdapterError",
    "LLMAdapterError",
    "MemoryAdapterError",
    "FabricError",
    "TrustGateError",
]


class VelvetError(Exception):
    """Base for all Velvet-specific errors."""
    pass


class VelvetAdapterError(VelvetError):
    """Base for adapter/integration errors (LLM, memory, fabric)."""
    pass


class LLMAdapterError(VelvetAdapterError):
    """Raised when an LLM adapter fails to generate or connect."""
    pass


class MemoryAdapterError(VelvetAdapterError):
    """Raised when a memory backend (vector, SQLite) operation fails."""
    pass


class FabricError(VelvetAdapterError):
    """Raised when the communication fabric encounters an error."""
    pass


class TrustGateError(VelvetError):
    """Raised when a trust level change bypasses the TrustGate or fails biometric validation."""
    pass
