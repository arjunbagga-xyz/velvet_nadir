"""
Model Registry for Velvet Nadir.

Tracks which ML models are available on which devices.
Routes inference requests to the best available device.
"""

__all__ = [
    "ModelType",
    "ModelFormat",
    "ModelInfo",
    "LoadedModel",
    "InferenceRequest",
    "InferenceResponse",
    "ModelRegistry",
    "InferenceRouter",
    "create_model_registry_with_fabric",
    "get_model_registry",
    "get_inference_router",
    "init_model_registry",
]

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from loguru import logger


class ModelType(Enum):
    """Type of ML model."""
    LLM = "llm"              # Language models
    VISION = "vision"        # Image/video models
    AUDIO = "audio"          # Speech/audio models
    EMBEDDING = "embedding"  # Embedding models
    MULTIMODAL = "multimodal"  # Vision + language
    OTHER = "other"


class ModelFormat(Enum):
    """Model file format."""
    GGUF = "gguf"           # llama.cpp format
    ONNX = "onnx"           # ONNX format
    TENSORRT = "tensorrt"   # NVIDIA TensorRT
    PYTORCH = "pytorch"     # PyTorch (.pt, .bin)
    SAFETENSORS = "safetensors"
    COREML = "coreml"       # Apple CoreML
    OTHER = "other"


@dataclass
class ModelInfo:
    """Information about a model."""
    model_id: str                # "llama-3-8b-q4", "whisper-large-v3"
    name: str                    # Human-readable name
    model_type: ModelType
    format: ModelFormat
    size_gb: float = 0
    capabilities: list[str] = field(default_factory=list)  # ["chat", "vision", "embed"]
    context_length: int = 0      # For LLMs
    quantization: str = ""       # "q4_k_m", "fp16", etc.
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "model_id": self.model_id,
            "name": self.name,
            "model_type": self.model_type.value,
            "format": self.format.value,
            "size_gb": self.size_gb,
            "capabilities": self.capabilities,
            "context_length": self.context_length,
            "quantization": self.quantization,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ModelInfo":
        return cls(
            model_id=data["model_id"],
            name=data.get("name", data["model_id"]),
            model_type=ModelType(data.get("model_type", "other")),
            format=ModelFormat(data.get("format", "other")),
            size_gb=data.get("size_gb", 0),
            capabilities=data.get("capabilities", []),
            context_length=data.get("context_length", 0),
            quantization=data.get("quantization", ""),
            metadata=data.get("metadata", {}),
        )


@dataclass
class LoadedModel:
    """A model loaded on a specific device."""
    model_info: ModelInfo
    device_id: str
    loaded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    utilization: float = 0.0     # 0-1, current usage
    available: bool = True


@dataclass
class InferenceRequest:
    """A request for model inference."""
    request_id: str
    model_id: str | None = None       # Specific model or None for best match
    model_type: ModelType | None = None  # Type if no specific model
    capabilities_needed: list[str] = field(default_factory=list)
    prompt: str = ""
    images: list[bytes] = field(default_factory=list)  # For vision models
    audio: bytes | None = None        # For audio models
    max_tokens: int = 512
    temperature: float = 0.7
    priority: int = 5                 # 1-10, higher = more urgent
    timeout_seconds: float = 30.0
    metadata: dict = field(default_factory=dict)


@dataclass
class InferenceResponse:
    """Response from model inference."""
    request_id: str
    device_id: str
    model_id: str
    success: bool
    result: str | list[float] | dict = ""
    tokens_used: int = 0
    latency_ms: float = 0
    error: str | None = None


class ModelRegistry:
    """
    Registry of models available across devices.
    
    Tracks:
    - Which models exist on which devices
    - Model utilization and availability
    - Routes inference to best device
    """
    
    def __init__(self):
        # model_id -> list of (device_id, LoadedModel)
        self._models: dict[str, list[LoadedModel]] = {}
        # device_id -> list of model_ids
        self._device_models: dict[str, list[str]] = {}
        # All known model infos
        self._model_infos: dict[str, ModelInfo] = {}
        
    async def register_model(self, device_id: str, model: ModelInfo) -> None:
        """Register a model as available on a device."""
        loaded = LoadedModel(model_info=model, device_id=device_id)
        
        # Add to model -> devices mapping
        if model.model_id not in self._models:
            self._models[model.model_id] = []
        
        # Check if already registered on this device
        existing = [m for m in self._models[model.model_id] if m.device_id == device_id]
        if existing:
            # Update existing
            idx = self._models[model.model_id].index(existing[0])
            self._models[model.model_id][idx] = loaded
        else:
            self._models[model.model_id].append(loaded)
        
        # Add to device -> models mapping
        if device_id not in self._device_models:
            self._device_models[device_id] = []
        if model.model_id not in self._device_models[device_id]:
            self._device_models[device_id].append(model.model_id)
        
        # Store model info
        self._model_infos[model.model_id] = model
        
        logger.info(f"Model registered: {model.model_id} on {device_id}")
    
    async def unregister_model(self, device_id: str, model_id: str) -> bool:
        """Unregister a model from a device."""
        if model_id in self._models:
            self._models[model_id] = [
                m for m in self._models[model_id] if m.device_id != device_id
            ]
            if not self._models[model_id]:
                del self._models[model_id]
        
        if device_id in self._device_models:
            if model_id in self._device_models[device_id]:
                self._device_models[device_id].remove(model_id)
        
        logger.info(f"Model unregistered: {model_id} from {device_id}")
        return True
    
    async def unregister_device(self, device_id: str) -> None:
        """Remove all models for a device."""
        models = self._device_models.get(device_id, []).copy()
        for model_id in models:
            await self.unregister_model(device_id, model_id)
        if device_id in self._device_models:
            del self._device_models[device_id]
    
    def get_model_info(self, model_id: str) -> ModelInfo | None:
        """Get info about a model."""
        return self._model_infos.get(model_id)
    
    def get_model_devices(self, model_id: str) -> list[str]:
        """Get device IDs where a model is loaded."""
        if model_id not in self._models:
            return []
        return [m.device_id for m in self._models[model_id] if m.available]
    
    def get_device_models(self, device_id: str) -> list[str]:
        """Get model IDs loaded on a device."""
        return self._device_models.get(device_id, [])
    
    def find_models_by_type(self, model_type: ModelType) -> list[ModelInfo]:
        """Find all models of a given type."""
        return [
            info for info in self._model_infos.values()
            if info.model_type == model_type
        ]
    
    def find_models_by_capability(self, capability: str) -> list[ModelInfo]:
        """Find all models with a specific capability."""
        return [
            info for info in self._model_infos.values()
            if capability in info.capabilities
        ]
    
    async def best_device_for(
        self, 
        model_id: str | None = None,
        model_type: ModelType | None = None,
        capabilities: list[str] | None = None,
    ) -> tuple[str, str] | None:
        """
        Find the best device for inference.
        
        Returns (device_id, model_id) or None if no suitable device.
        """
        from .devices import get_registry
        
        registry = get_registry()
        
        # Strategy: find matching models, then pick least utilized device
        candidates: list[tuple[str, str, float]] = []  # (device_id, model_id, score)
        
        if model_id:
            # Specific model requested
            for loaded in self._models.get(model_id, []):
                if loaded.available:
                    device = registry.get_device(loaded.device_id)
                    if device and device.is_online():
                        # Score: lower utilization = better
                        score = 1.0 - loaded.utilization
                        candidates.append((loaded.device_id, model_id, score))
        else:
            # Find by type or capabilities
            for mid, loaded_list in self._models.items():
                info = self._model_infos.get(mid)
                if not info:
                    continue
                    
                # Check type match
                if model_type and info.model_type != model_type:
                    continue
                    
                # Check capabilities
                if capabilities:
                    if not all(cap in info.capabilities for cap in capabilities):
                        continue
                
                # Add all available instances
                for loaded in loaded_list:
                    if loaded.available:
                        device = registry.get_device(loaded.device_id)
                        if device and device.is_online():
                            score = 1.0 - loaded.utilization
                            candidates.append((loaded.device_id, mid, score))
        
        if not candidates:
            return None
        
        # Sort by score (higher = better)
        candidates.sort(key=lambda x: x[2], reverse=True)
        return (candidates[0][0], candidates[0][1])
    
    async def update_utilization(self, device_id: str, model_id: str, utilization: float):
        """Update model utilization on a device."""
        if model_id in self._models:
            for loaded in self._models[model_id]:
                if loaded.device_id == device_id:
                    loaded.utilization = max(0.0, min(1.0, utilization))
                    break
    
    def get_stats(self) -> dict:
        """Get registry statistics."""
        return {
            "total_models": len(self._model_infos),
            "total_instances": sum(len(v) for v in self._models.values()),
            "devices_with_models": len(self._device_models),
            "by_type": {
                t.value: len([m for m in self._model_infos.values() if m.model_type == t])
                for t in ModelType
            },
        }


# ============================================================================
# Inference Router
# ============================================================================

class InferenceRouter:
    """
    Routes inference requests to the best available device.
    
    Handles:
    - Finding best device for a request
    - Sending request over Zenoh
    - Waiting for response
    - Fallback if device fails
    """
    
    def __init__(self, model_registry: ModelRegistry):
        self.registry = model_registry
        self._pending: dict[str, asyncio.Future] = {}
    
    async def route(self, request: InferenceRequest) -> InferenceResponse:
        """Route an inference request to the best device."""
        from .fabric import get_fabric, MessageType
        import uuid
        
        # Assign request ID if not set
        if not request.request_id:
            request.request_id = str(uuid.uuid4())[:8]
        
        # Find best device
        result = await self.registry.best_device_for(
            model_id=request.model_id,
            model_type=request.model_type,
            capabilities=request.capabilities_needed,
        )
        
        if not result:
            return InferenceResponse(
                request_id=request.request_id,
                device_id="",
                model_id=request.model_id or "",
                success=False,
                error="No suitable device found for inference",
            )
        
        device_id, model_id = result
        logger.debug(f"Routing inference {request.request_id} to {device_id} ({model_id})")
        
        # Create future for response
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[request.request_id] = future
        
        # Send request over Zenoh
        fabric = get_fabric()
        await fabric.publish(
            f"velvet/inference/{device_id}/request",
            {
                "request_id": request.request_id,
                "model_id": model_id,
                "prompt": request.prompt,
                "max_tokens": request.max_tokens,
                "temperature": request.temperature,
                "metadata": request.metadata,
            }
        )
        
        # Wait for response
        try:
            response = await asyncio.wait_for(future, timeout=request.timeout_seconds)
            return response
        except asyncio.TimeoutError:
            del self._pending[request.request_id]
            return InferenceResponse(
                request_id=request.request_id,
                device_id=device_id,
                model_id=model_id,
                success=False,
                error=f"Timeout waiting for response from {device_id}",
            )
    
    async def handle_response(self, response_data: dict):
        """Handle an inference response from a device."""
        request_id = response_data.get("request_id")
        if request_id and request_id in self._pending:
            response = InferenceResponse(
                request_id=request_id,
                device_id=response_data.get("device_id", ""),
                model_id=response_data.get("model_id", ""),
                success=response_data.get("success", False),
                result=response_data.get("result", ""),
                tokens_used=response_data.get("tokens_used", 0),
                latency_ms=response_data.get("latency_ms", 0),
                error=response_data.get("error"),
            )
            self._pending[request_id].set_result(response)
            del self._pending[request_id]


# ============================================================================
# Zenoh Integration
# ============================================================================

async def create_model_registry_with_fabric() -> tuple[ModelRegistry, InferenceRouter]:
    """
    Create a ModelRegistry and InferenceRouter integrated with Zenoh.
    """
    from .fabric import get_fabric, MessageType
    
    registry = ModelRegistry()
    router = InferenceRouter(registry)
    fabric = get_fabric()
    
    async def on_model_announce(msg):
        """Handle model announcement."""
        data = msg.payload
        device_id = data.get("device_id")
        model_data = data.get("model")
        if device_id and model_data:
            model = ModelInfo.from_dict(model_data)
            await registry.register_model(device_id, model)
    
    async def on_inference_response(msg):
        """Handle inference response."""
        await router.handle_response(msg.payload)
    
    # Subscribe to model topics
    await fabric.subscribe("velvet/mesh/model/announce", on_model_announce)
    await fabric.subscribe("velvet/inference/+/response", on_inference_response)
    
    return registry, router


# ============================================================================
# Singleton
# ============================================================================

_model_registry: ModelRegistry | None = None
_inference_router: InferenceRouter | None = None


def get_model_registry() -> ModelRegistry:
    """Get the global model registry."""
    if _model_registry is None:
        raise RuntimeError("Model registry not initialized.")
    return _model_registry


def get_inference_router() -> InferenceRouter:
    """Get the global inference router."""
    if _inference_router is None:
        raise RuntimeError("Inference router not initialized.")
    return _inference_router


async def init_model_registry(with_fabric: bool = True) -> tuple[ModelRegistry, InferenceRouter]:
    """Initialize the global model registry and router."""
    global _model_registry, _inference_router
    if with_fabric:
        _model_registry, _inference_router = await create_model_registry_with_fabric()
    else:
        _model_registry = ModelRegistry()
        _inference_router = InferenceRouter(_model_registry)
    return _model_registry, _inference_router
