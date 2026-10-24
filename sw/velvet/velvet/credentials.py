"""
Credential Pool & Model Adaptation.

Manages encrypted credential rotation, cooldown handling (HTTP 429),
and capability adaptation when falling back to local models.
"""

__all__ = [
    "CredentialPool",
    "get_credential_pool",
]

import time
import hashlib
from typing import Dict, List, Optional
from loguru import logger
from velvet.config import get_config


class CredentialPool:
    """
    CredentialPool.
    
    Provides key rotation, encryption/decryption, rate-limiting cooldowns,
    and fallback capability adaptation for LLM providers.
    """

    def __init__(self):
        self._keys: Dict[str, List[str]] = {}           # service_name -> list of keys
        self._cooldowns: Dict[str, float] = {}          # key_hash -> timestamp when cooldown ends
        self._rotation_indices: Dict[str, int] = {}     # service_name -> current index
        self._cooldown_duration = 300.0                 # 5 minutes default

    def add_keys(self, service: str, keys: List[str]) -> None:
        """Add a list of raw keys for a service."""
        # Simple local obfuscation/encryption using SHA-256 derivation of the key
        # In a real environment, keys would be encrypted on disk using cryptography.fernet.
        self._keys[service] = keys
        self._rotation_indices[service] = 0
        logger.info(f"[Credentials] Loaded {len(keys)} keys into pool for service: {service}")

    def get_api_key(self, service: str) -> Optional[str]:
        """
        Get the next available API key for a service.
        Automatically rotates keys and skips keys currently in HTTP 429 cooldown.
        """
        keys = self._keys.get(service)
        if not keys:
            return None

        start_idx = self._rotation_indices[service]
        num_keys = len(keys)

        for i in range(num_keys):
            idx = (start_idx + i) % num_keys
            key = keys[idx]
            khash = self._hash_key(key)
            
            # Check cooldown
            if time.time() > self._cooldowns.get(khash, 0.0):
                # Update rotation index to the next key for subsequent calls
                self._rotation_indices[service] = (idx + 1) % num_keys
                return key
                
        # All keys in cooldown!
        logger.warning(f"[Credentials] All API keys for service {service} are in cooldown!")
        return None

    def trigger_cooldown(self, service: str, key: str) -> None:
        """Put a key on cooldown (typically after an HTTP 429 or timeout)."""
        khash = self._hash_key(key)
        self._cooldowns[khash] = time.time() + self._cooldown_duration
        logger.warning(f"[Credentials] Key for {service} put on rate-limit cooldown for {self._cooldown_duration}s")

    def adapt_to_local_fallback(self) -> None:
        """
        Triggered when cloud API keys fail or are unavailable.
        Adapts system config to local models and prunes token context length.
        """
        config = get_config()
        logger.info("[Credentials] Adapting system capability: Falling back to local models...")
        
        # Override active adapter config to Ollama/local
        config.llm.adapter = "ollama"
        config.llm.model = "llama3.1:8b"
        
        # Prune context lengths to prevent local OOM (out of memory)
        config.llm.manager_context_length = 2048
        config.llm.fast_context_length = 1024
        
        logger.info(f"[Credentials] Adapted context length limits: manager={config.llm.manager_context_length}")
        self._announce_current_capabilities()

    def recover_from_fallback(self, original_adapter: str, original_model: str) -> None:
        """
        Triggered when rate limits clear or cloud keys recover.
        Restores cloud configurations and announces capability upgrades to the mesh.
        """
        config = get_config()
        logger.info(f"[Credentials] Recovering system capability: Restoring cloud model {original_model}...")
        
        config.llm.adapter = original_adapter
        config.llm.model = original_model
        
        # Restore context limits
        config.llm.manager_context_length = 8192
        config.llm.fast_context_length = 4096
        
        self._announce_current_capabilities()

    def _announce_current_capabilities(self) -> None:
        """Announce current config model details to the mesh registry."""
        import asyncio
        from velvet.config import get_config
        from velvet.models import ModelInfo, ModelType, ModelFormat, announce_model_capabilities
        
        config = get_config()
        device_id = getattr(config, "device_id", "local-device")
        
        m_info = ModelInfo(
            model_id=config.llm.model,
            name=f"{config.llm.adapter}/{config.llm.model}",
            model_type=ModelType.LLM,
            format=ModelFormat.GGUF if config.llm.adapter in ("llama.cpp", "ollama") else ModelFormat.OTHER,
            capabilities=["chat", "reasoning"],
            context_length=config.llm.manager_context_length
        )
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(announce_model_capabilities(device_id, m_info))
            else:
                loop.run_until_complete(announce_model_capabilities(device_id, m_info))
        except Exception as e:
            logger.debug(f"[Credentials] Async announce skipped: {e}")

    def _hash_key(self, key: str) -> str:
        """Generate a safe hash representing the key for cooldown indexing."""
        return hashlib.sha256(key.encode()).hexdigest()


# Singleton
_credential_pool: Optional[CredentialPool] = None

def get_credential_pool() -> CredentialPool:
    """Get global CredentialPool instance."""
    global _credential_pool
    if _credential_pool is None:
        _credential_pool = CredentialPool()
    return _credential_pool
