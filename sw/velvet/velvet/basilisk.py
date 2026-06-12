"""
The Basilisk Protocol — Ephemeral RAM Enclave for Velvet Nadir.

Provides secure, temporary memory isolation for sensitive biometric and raw sensor data.
Ensures metadata and large blobs are never persisted to disk or journals.
"""

import gc
import asyncio
import time
from typing import Any, Callable, Awaitable, List
from loguru import logger

class BasiliskEnclave:
    """
    Basilisk Protocol Enclave for memory isolation.
    
    Acts as a context manager that ensures data specifically tracked
    within the block is explicitly deleted and garbage collected on exit.
    """
    
    def __init__(self, name: str = "general"):
        self.name = name
        self.start_time = time.time()
        self._tracked_refs: List[Any] = []
        self._data: dict[str, Any] = {}

    def track(self, obj: Any) -> Any:
        """Mark an object for explicit deletion on enclave exit."""
        if obj is not None:
            self._tracked_refs.append(obj)
        return obj

    def put(self, key: str, value: Any):
        """Store ephemeral data in the enclave and track it."""
        self._data[key] = value
        self.track(value)
        
    def get(self, key: str) -> Any:
        """Retrieve ephemeral data."""
        return self._data.get(key)

    async def __aenter__(self) -> "BasiliskEnclave":
        logger.debug(f"[Basilisk] '{self.name}' enclave established.")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        count = len(self._tracked_refs) + len(self._data)
        
        # 1. Clear internal data dict
        self._data.clear()
        
        # 2. Clear tracked references
        self._tracked_refs.clear()
        
        # 3. Force Garbage Collection
        # Double collection to handle generation artifacts
        gc.collect()
        gc.collect()
        
        logger.debug(f"[Basilisk] '{self.name}' enclave collapsed after {duration:.3f}s. Cleared {count} references.")


def sanitize_for_hun(data: Any) -> Any:
    """
    Recursively strips raw tensors and large binary blobs from a payload.
    Returns a 'safe' version for storage in logs or LLM WorkingMemory.
    """
    if isinstance(data, dict):
        safe_dict = {}
        for k, v in data.items():
            if _is_raw_tensor(k, v):
                safe_dict[k] = f"<BASILISK_STRIPPED:{type(v).__name__}>"
            else:
                safe_dict[k] = sanitize_for_hun(v)
        return safe_dict
    elif isinstance(data, list):
        return [sanitize_for_hun(item) for item in data]
    return data


def _is_raw_tensor(key: str, value: Any) -> bool:
    """Determine if a value looks like raw biometric or high-sensitivity data."""
    # 1. Key-based detection
    sensitive_keys = {
        "face_embedding", "voice_embedding", "biometrics", 
        "tensor_data", "frame", "audio", "raw_image", "embedding"
    }
    if key.lower() in sensitive_keys:
        return True
        
    # 2. Type/Size detection
    try:
        import numpy as np
        if isinstance(value, np.ndarray):
            return value.size > 100
    except ImportError:
        pass

    try:
        import torch
        if isinstance(value, torch.Tensor):
            return True
    except (ImportError, TypeError):
        pass
        
    return False

async def run_basilisk(name: str, coro_func: Callable[..., Awaitable[Any]], *args, **kwargs) -> Any:
    """Helper to run a coroutine securely within a Basilisk enclave."""
    async with BasiliskEnclave(name) as enclave:
        return await coro_func(enclave, *args, **kwargs)
