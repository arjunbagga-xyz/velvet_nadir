"""
Polymath: Unified Hardware Intelligence.

Single source of truth for all hardware-driven decisions:
- GPU/CPU/RAM detection
- LLM inference backend selection (TensorRT, llama.cpp, vLLM)
- TTS/STT/Wake Word provider selection
- Singleton — probes hardware exactly once

Replaces separate CapabilityResolver. All runtime "what should I use?"
questions go through Polymath.
"""

import sys
import asyncio
import shutil
import platform
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from functools import cached_property
from pathlib import Path
from typing import Optional

from loguru import logger

# Optional imports for hardware detection
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import pynvml
    HAS_PYNVML = True
except ImportError:
    HAS_PYNVML = False


class HardwareType(Enum):
    JETSON_ORIN = "jetson_orin"
    JETSON_NANO = "jetson_nano"
    NVIDIA_GPU = "nvidia_gpu"
    APPLE_SILICON = "apple_silicon"
    CPU_ONLY = "cpu_only"
    UNKNOWN = "unknown"


@dataclass
class HardwareProfile:
    type: HardwareType
    gpu_name: str = ""
    vram_gb: float = 0.0
    ram_gb: float = 0.0
    has_cuda: bool = False
    has_tensorrt: bool = False
    cpu_cores: int = 1
    os: str = ""
    os_version: str = ""


# ============================================================================
# Inference Backends
# ============================================================================

class InferenceBackend(ABC):
    """Abstract base class for inference backends."""
    
    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> str:
        pass
    
    @abstractmethod
    def name(self) -> str:
        pass


class LlamaCppBackend(InferenceBackend):
    """Inference via llama.cpp (CPU/GPU)."""
    
    def __init__(self, model_path: str, n_gpu_layers: int = 0):
        self.model_path = model_path
        self.n_gpu_layers = n_gpu_layers
        self._llm = None
        
    def _ensure_loaded(self):
        if self._llm:
            return
        try:
            from llama_cpp import Llama
            logger.info(f"[Polymath] Loading Llama model from: {self.model_path}")
            self._llm = Llama(
                model_path=self.model_path,
                n_gpu_layers=self.n_gpu_layers,
                verbose=False
            )
        except ImportError:
            logger.error("[Polymath] llama-cpp-python not installed.")
            raise

    def name(self) -> str:
        return "llama.cpp"

    async def generate(self, prompt: str, **kwargs) -> str:
        self._ensure_loaded()
        max_tokens = kwargs.get("max_tokens", 512)
        temperature = kwargs.get("temperature", 0.7)
        output = self._llm.create_completion(
            prompt, max_tokens=max_tokens, temperature=temperature
        )
        return output["choices"][0]["text"]


class VLLMBackend(InferenceBackend):
    """Inference via local vLLM engine (in-process)."""
    
    def __init__(self, model_path: str):
        self.model_path = model_path
        self._llm = None
        
    def _ensure_loaded(self):
        if self._llm is not None:
            return
        try:
            import vllm
            logger.info(f"[Polymath] Loading local vLLM model from: {self.model_path}")
            self._llm = vllm.LLM(model=self.model_path)
        except ImportError:
            logger.error("[Polymath] vllm package is not installed.")
            raise
            
    def name(self) -> str:
        return "vLLM-local"
        
    async def generate(self, prompt: str, **kwargs) -> str:
        self._ensure_loaded()
        import vllm
        max_tokens = kwargs.get("max_tokens", 512)
        temperature = kwargs.get("temperature", 0.7)
        sampling_params = vllm.SamplingParams(
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        loop = asyncio.get_running_loop()
        def _run_inference():
            outputs = self._llm.generate([prompt], sampling_params)
            if outputs:
                return outputs[0].outputs[0].text
            return ""
            
        return await loop.run_in_executor(None, _run_inference)


class TensorRTBackend(InferenceBackend):
    """Inference via TensorRT-LLM (Jetson Optimized)."""
    
    def __init__(self, engine_dir: str):
        self.engine_dir = engine_dir
        self._runner = None
        self._tokenizer = None
        
    def name(self) -> str:
        return "TensorRT-LLM"

    def _ensure_loaded(self):
        if self._runner is not None:
            return
        try:
            from tensorrt_llm.runtime import ModelRunner
            from transformers import AutoTokenizer
            logger.info(f"[Polymath] Loading TensorRT-LLM engine from: {self.engine_dir}")
            self._runner = ModelRunner.from_dir(self.engine_dir, rank=0)
            self._tokenizer = AutoTokenizer.from_pretrained(self.engine_dir)
        except ImportError:
            logger.error("[Polymath] tensorrt_llm or transformers not installed.")
            raise

    async def generate(self, prompt: str, **kwargs) -> str:
        self._ensure_loaded()
        max_tokens = kwargs.get("max_tokens", 512)
        temperature = kwargs.get("temperature", 0.7)
        
        loop = asyncio.get_running_loop()
        def _run_inference():
            input_ids = self._tokenizer.encode(prompt)
            outputs = self._runner.generate(
                [input_ids],
                max_new_tokens=max_tokens,
                temperature=temperature
            )
            output_ids = outputs[0][0]
            if hasattr(output_ids, "tolist"):
                output_ids = output_ids.tolist()
            return self._tokenizer.decode(output_ids, skip_special_tokens=True)
            
        return await loop.run_in_executor(None, _run_inference)


# ============================================================================
# Polymath: Unified Hardware Intelligence (Singleton)
# ============================================================================

class Polymath:
    """
    Unified hardware intelligence layer.
    
    Handles:
    - Hardware probing (GPU, CPU, RAM, OS)
    - LLM inference backend selection & creation
    - TTS/STT/Wake Word provider resolution
    - All runtime "what should I use?" decisions
    
    Singleton: instantiated once, probes hardware once.
    """
    
    def __init__(self, device=None):
        """
        Args:
            device: Optional Device from mesh registry. If None, auto-detects.
        """
        self._device = device
        self.profile = self._probe_hardware()
        self._cached_memory_config = None
        logger.info(
            f"[Polymath] {self.profile.type.value} | "
            f"GPU={self.profile.gpu_name or 'None'} ({self.profile.vram_gb}GB) | "
            f"RAM={self.profile.ram_gb}GB | OS={self.profile.os}"
        )

    # =========================================================================
    # Hardware Probing
    # =========================================================================

    def _probe_hardware(self) -> HardwareProfile:
        """Detect system capabilities."""
        # If we have a Device from the mesh, use its specs
        if self._device:
            hw = self._device.hardware
            sw = self._device.software
            
            is_jetson = "jetson" in (hw.gpu or "").lower()
            has_cuda = bool(hw.gpu)
            hw_type = HardwareType.CPU_ONLY
            if is_jetson:
                hw_type = HardwareType.JETSON_ORIN
            elif has_cuda:
                hw_type = HardwareType.NVIDIA_GPU
            
            return HardwareProfile(
                type=hw_type,
                gpu_name=hw.gpu or "",
                vram_gb=hw.gpu_vram_gb,
                ram_gb=hw.ram_gb,
                has_cuda=has_cuda,
                has_tensorrt=False,
                cpu_cores=hw.cpu_cores,
                os=sw.os,
                os_version=sw.os_version,
            )

        # Auto-detect from local machine
        ram_gb = 0.0
        cpu_cores = 1
        if HAS_PSUTIL:
            ram_gb = psutil.virtual_memory().total / (1024**3)
            cpu_cores = psutil.cpu_count(logical=False) or 1
        
        # NVIDIA Detection
        has_cuda = False
        vram_gb = 0.0
        gpu_name = ""
        
        if HAS_PYNVML:
            try:
                pynvml.nvmlInit()
                device_count = pynvml.nvmlDeviceGetCount()
                if device_count > 0:
                    has_cuda = True
                    handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                    name = pynvml.nvmlDeviceGetName(handle)
                    gpu_name = name.decode("utf-8") if isinstance(name, bytes) else name
                    for i in range(device_count):
                        h = pynvml.nvmlDeviceGetHandleByIndex(i)
                        info = pynvml.nvmlDeviceGetMemoryInfo(h)
                        vram_gb += info.total / (1024**3)
                pynvml.nvmlShutdown()
            except Exception:
                pass

        # Jetson Detection
        is_jetson = False
        if platform.system() == "Linux" and Path("/etc/nv_tegra_release").exists():
            is_jetson = True
        
        # TensorRT Detection
        has_tensorrt = bool(shutil.which("trtexec"))

        # Classify Hardware Type
        hw_type = HardwareType.CPU_ONLY
        if is_jetson:
            hw_type = HardwareType.JETSON_ORIN
        elif sys.platform == "darwin" and platform.machine() == "arm64":
            hw_type = HardwareType.APPLE_SILICON
        elif has_cuda and vram_gb > 0:
            hw_type = HardwareType.NVIDIA_GPU
            
        return HardwareProfile(
            type=hw_type,
            gpu_name=gpu_name,
            vram_gb=round(vram_gb, 2),
            ram_gb=round(ram_gb, 2),
            has_cuda=has_cuda,
            has_tensorrt=has_tensorrt,
            cpu_cores=cpu_cores,
            os=platform.system(),
            os_version=platform.release(),
        )

    # =========================================================================
    # LLM Backend Selection & Creation
    # =========================================================================

    def create_backend(self, model_path: str, **kwargs) -> InferenceBackend:
        """Instantiate the best backend for the given model."""
        backend_cls = self.select_backend_class(model_path)
        
        n_gpu_layers = 0
        if self.profile.has_cuda:
            n_gpu_layers = -1  # Offload all
        elif self.profile.type == HardwareType.APPLE_SILICON:
            n_gpu_layers = -1  # Metal
            
        logger.info(f"[Polymath] Loading {model_path} with {backend_cls.__name__} (gpu_layers={n_gpu_layers})")
        
        if backend_cls == TensorRTBackend:
            return TensorRTBackend(engine_dir=str(model_path))
        elif backend_cls == VLLMBackend:
            return VLLMBackend(model_path=str(model_path))
             
        return LlamaCppBackend(model_path=str(model_path), n_gpu_layers=n_gpu_layers)

    def select_backend_class(self, model_path: str = None) -> type[InferenceBackend]:
        """Select the best backend CLASS based on hardware and model signature."""
        profile = self.profile
        
        if model_path:
            p = Path(model_path)
            if p.suffix == ".gguf" or p.name.endswith(".gguf"):
                return LlamaCppBackend
            if p.is_dir():
                try:
                    # Look for TensorRT .engine files
                    if any(f.suffix == ".engine" for f in p.iterdir()):
                        return TensorRTBackend
                except Exception:
                    pass
                try:
                    # Look for safetensors or config.json
                    has_safetensors = any(f.suffix == ".safetensors" for f in p.iterdir())
                    has_config = (p / "config.json").exists()
                    if has_safetensors or has_config:
                        return VLLMBackend
                except Exception:
                    pass

        if profile.type == HardwareType.JETSON_ORIN:
            if profile.has_tensorrt:
                return TensorRTBackend
            logger.info("[Polymath] TensorRT not found, fallback to LlamaCppBackend")
            return LlamaCppBackend

        if profile.type == HardwareType.NVIDIA_GPU and profile.vram_gb >= 12 and profile.os == "Linux":
            return VLLMBackend

        return LlamaCppBackend

    @cached_property
    def inference_backend(self) -> str:
        """Best LLM inference backend name for this device."""
        from velvet.config import get_config
        
        adapter = get_config().llm.adapter
        if adapter and adapter != "auto":
            return adapter

        if self.profile.type == HardwareType.JETSON_ORIN:
            return "tensorrt"
        if self.profile.vram_gb >= 12 and self.profile.os == "Linux":
            return "vllm"
        if self.profile.has_cuda:
            return "llama.cpp"
        return "ollama"

    # =========================================================================
    # TTS / STT / Wake Word Provider Selection
    # =========================================================================

    @cached_property
    def tts_provider(self) -> str:
        """Select the best TTS provider for this device."""
        from velvet.config import get_config
        
        configured = get_config().audio.tts_provider
        if configured and configured != "auto":
            return configured

        # Auto-detect based on available packages
        try:
            import riva.client  # noqa: F401
            return "riva"
        except ImportError:
            pass
        try:
            import piper  # noqa: F401
            return "piper"
        except ImportError:
            pass
        
        return "pyttsx3"

    @cached_property
    def stt_provider(self) -> str:
        """Select the best STT provider for this device."""
        from velvet.config import get_config
        
        configured = get_config().audio.stt_provider
        if configured and configured != "auto":
            return configured

        try:
            import riva.client  # noqa: F401
            return "riva"
        except ImportError:
            pass
        try:
            import faster_whisper  # noqa: F401
            return "whisper"
        except ImportError:
            pass
        
        return "google"

    @cached_property
    def wake_word_framework(self) -> str:
        """Select the best wake word inference framework."""
        try:
            import tflite_runtime  # noqa: F401
            return "tflite"
        except ImportError:
            return "onnx"

    # =========================================================================
    # Memory Configuration (PowerMem)
    # =========================================================================

    def build_memory_config(self) -> dict:
        """
        Build a full PowerMem config dict, mesh-aware.

        Queries local Ollama and mesh peers to resolve the best available
        embedding and LLM providers, then assembles the complete config with
        all Sprint 10 features wired from VelvetConfig.
        """
        if self._cached_memory_config is not None:
            return self._cached_memory_config

        from velvet.config import get_config
        cfg = get_config()
        mem = cfg.memory

        llm_cfg = self._resolve_memory_llm_provider()
        embed_cfg = self._resolve_memory_embedding_provider(mem.embedding_model)

        config = {
            "llm": llm_cfg,
            "embedder": embed_cfg,

            "vector_store": {
                "provider": "sqlite",
                "config": {
                    "database_path": mem.memory_db_path,
                    "collection_name": "velvet_memories",
                }
            },

            "intelligent_memory": {
                "enabled": True,
                "decay_rate": mem.decay_rate,
                "reinforcement_factor": mem.reinforcement_factor,
                "working_threshold": mem.working_threshold,
                "short_term_threshold": mem.short_term_threshold,
                "long_term_threshold": mem.long_term_threshold,
                "fallback_to_simple_add": True,
            },

            "agent_memory": {
                "enabled": True,
                "mode": "multi_agent",
                "default_scope": mem.agent_scope,
                "default_privacy_level": "standard",
                "default_collaboration_level": "collaborative",
                "enable_collaboration": True,
            },

            "custom_fact_extraction_prompt": (
                "You are Velvet, a personal AI assistant. Extract key facts from "
                "this conversation that are worth remembering long-term. Focus on: "
                "user preferences, routines, names, relationships, locations, "
                "device configurations, and stated goals. "
                "Output as a JSON list of facts."
            ),

            "custom_update_memory_prompt": (
                "You are Velvet. When updating a memory, preserve the user's "
                "preferences and correct factual information. If conflicting, "
                "prefer the newer information but note the change."
            ),

            "telemetry": {
                "enable_telemetry": False,
            },
        }

        # Graph store: handled by MemPalace KnowledgeGraph in Jing directly.
        # PowerMem's GraphStoreFactory only supports 'oceanbase' — not viable for
        # local-first. See NOTES_MEMPALACE_FUTURE.md for architecture context.

        # Query rewrite
        if mem.query_rewrite_enabled:
            config["query_rewrite"] = {
                "enabled": True,
                "model_override": None,
            }

        # Audit logging
        if mem.audit_enabled:
            config["audit"] = {
                "enabled": True,
                "log_file": str(Path(cfg.storage.data_dir) / "logs" / "memory_audit.log"),
                "retention_days": mem.audit_retention_days,
            }

        logger.info(
            f"[Polymath] Memory config built — "
            f"llm={llm_cfg.get('config', {}).get('model', '?')}, "
            f"embedder={embed_cfg.get('config', {}).get('model', '?')}, "
            f"graph={mem.graph_enabled}"
        )
        self._cached_memory_config = config
        return config

    def _resolve_memory_llm_provider(self) -> dict:
        """Resolve the best LLM provider for memory operations (mesh-aware)."""
        from velvet.config import get_config
        cfg = get_config()

        # Use the same Ollama config as the main LLM — mesh routes automatically
        return {
            "provider": "ollama",
            "config": {
                "model": cfg.llm.model,
                "ollama_base_url": cfg.llm.base_url,
                "temperature": 0.0,
            }
        }

    def _resolve_memory_embedding_provider(self, model: str) -> dict:
        """
        Self-healing embedding provider resolution.
        
        Waterfall (local-first, cloud as last resort):
        1. Ollama (if daemon is running and model available)
        2. vLLM (if /v1/embeddings endpoint responds)
        3. ONNX default (zero-dependency fallback, always works)
        4. Cloud embedding (if allow_cloud_adapters=true and API key present)
           — NVIDIA NIM or Google Gemini embedding endpoints
        """
        from velvet.config import get_config
        cfg = get_config()
        
        # 1. Try Ollama (local)
        if self._probe_ollama(cfg.llm.base_url, model):
            logger.info(f"[Polymath] Embedding: Ollama ({model})")
            return {
                "provider": "ollama",
                "config": {
                    "model": model,
                    "ollama_base_url": cfg.llm.base_url,
                }
            }
        
        # 2. Try vLLM embedding endpoint (local)
        vllm_url = getattr(cfg.llm, 'vllm_base_url', 'http://localhost:8000')
        if self._probe_vllm_embeddings(vllm_url):
            logger.info(f"[Polymath] Embedding: vLLM ({vllm_url})")
            return {
                "provider": "openai",  # vLLM uses OpenAI-compatible API
                "config": {
                    "model": model,
                    "openai_base_url": f"{vllm_url}/v1",
                }
            }
        
        # 3. ONNX fallback (local, zero deps)
        # Try ONNX first — if it works, prefer it over cloud
        try:
            # Quick sanity check: can we import the ONNX provider?
            from powermem.integrations.embeddings.pyseekdb_default import PyseekdbDefaultEmbedding
            logger.info("[Polymath] Embedding: ONNX default (all-MiniLM-L6-v2, 384d)")
            return {
                "provider": "default",
                "config": {
                    "model": "all-MiniLM-L6-v2",
                    "embedding_dims": 384,
                }
            }
        except ImportError:
            logger.warning("[Polymath] ONNX default embedder unavailable")
        
        # 4. Cloud embedding (only if security gate allows it)
        cloud_cfg = self._resolve_cloud_embedding(cfg)
        if cloud_cfg:
            return cloud_cfg
        
        # 5. Absolute last resort — ONNX without import check
        logger.warning("[Polymath] All probes failed. Falling back to ONNX default.")
        return {
            "provider": "default",
            "config": {
                "model": "all-MiniLM-L6-v2",
                "embedding_dims": 384,
            }
        }

    def _resolve_cloud_embedding(self, cfg) -> dict | None:
        """
        Try cloud embedding providers, respecting security gate.
        
        Only called when ALL local providers have failed.
        Uses PowerMem's built-in OpenAI-compatible and Gemini embedding classes.
        """
        import os
        
        # Backward-compatible check for allow_cloud_adapters or old allow_google_adapter
        allow_cloud = getattr(cfg.security, 'allow_cloud_adapters', False) or getattr(cfg.security, 'allow_google_adapter', False)
        if not allow_cloud:
            logger.info("[Polymath] Cloud embeddings blocked by security policy")
            return None
        
        # 4a. NVIDIA NIM /v1/embeddings (OpenAI-compatible)
        nvidia_key = os.environ.get("VELVET_LLM_NVIDIA_API_KEY")
        if nvidia_key:
            logger.info("[Polymath] Embedding: NVIDIA NIM (cloud, OpenAI-compat)")
            return {
                "provider": "openai",
                "config": {
                    "model": "nvidia/nv-embedqa-e5-v5",
                    "openai_base_url": "https://integrate.api.nvidia.com/v1",
                    "api_key": nvidia_key,
                    "embedding_dims": 1024,
                    "pass_dimensions": False,  # NIM may not support dim override
                }
            }
        
        # 4b. Google Gemini embedding
        google_key = os.environ.get("VELVET_LLM_GOOGLE_API_KEY")
        if google_key:
            logger.info("[Polymath] Embedding: Google Gemini (cloud)")
            return {
                "provider": "gemini",
                "config": {
                    "model": "models/text-embedding-004",
                    "api_key": google_key,
                    "embedding_dims": 768,
                }
            }
        
        # 4c. OpenRouter /v1/embeddings (OpenAI-compatible)
        openrouter_key = os.environ.get("VELVET_LLM_OPENROUTER_API_KEY")
        if openrouter_key:
            logger.info("[Polymath] Embedding: OpenRouter (cloud, OpenAI-compat)")
            return {
                "provider": "openai",
                "config": {
                    "model": "openai/text-embedding-3-small",
                    "openai_base_url": "https://openrouter.ai/api/v1",
                    "api_key": openrouter_key,
                    "embedding_dims": 1536,
                }
            }
        
        logger.info("[Polymath] Cloud adapters enabled but no API keys found")
        return None

    def _probe_ollama(self, base_url: str, model: str) -> bool:
        """Check if Ollama daemon is running and embedding model is available."""
        import urllib.request
        try:
            req = urllib.request.Request(f"{base_url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=2) as resp:
                import json
                data = json.loads(resp.read())
                models = data.get("models", [])
                # Handle both dict and object formats
                names = []
                for m in models:
                    if isinstance(m, dict):
                        names.append(m.get("name", ""))
                        names.append(m.get("model", ""))
                    else:
                        names.append(getattr(m, "name", ""))
                        names.append(getattr(m, "model", ""))
                return any(model in n for n in names if n)
        except Exception:
            return False

    def _probe_vllm_embeddings(self, base_url: str) -> bool:
        """Check if vLLM embeddings endpoint is responsive."""
        import urllib.request
        try:
            req = urllib.request.Request(f"{base_url}/v1/models", method="GET")
            with urllib.request.urlopen(req, timeout=2) as resp:
                return resp.status == 200
        except Exception:
            return False

    # =========================================================================
    # Summary
    # =========================================================================

    def summary(self) -> dict:
        """Full capabilities report."""
        return {
            "hardware": self.profile.type.value,
            "gpu": self.profile.gpu_name or "None",
            "vram_gb": self.profile.vram_gb,
            "ram_gb": self.profile.ram_gb,
            "os": self.profile.os,
            "is_jetson": self.profile.type == HardwareType.JETSON_ORIN,
            "tts_provider": self.tts_provider,
            "stt_provider": self.stt_provider,
            "wake_word_framework": self.wake_word_framework,
            "inference_backend": self.inference_backend,
        }


# ============================================================================
# Singleton
# ============================================================================

_instance: Polymath | None = None


def get_polymath(device=None) -> Polymath:
    """Get or create the global Polymath instance."""
    global _instance
    if _instance is None:
        _instance = Polymath(device=device)
    return _instance
