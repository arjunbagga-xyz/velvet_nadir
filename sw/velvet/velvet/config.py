"""
Core configuration using Pydantic Settings.
Supports environment variables and .env files.
"""

__all__ = [
    "ZenohConfig",
    "SecurityConfig",
    "AudioConfig",
    "LLMConfig",
    "ShenConfig",
    "ContextConfig",
    "StorageConfig",
    "GatewayConfig",
    "MemoryConfig",
    "XiConfig",
    "VisionConfig",
    "VelvetConfig",
    "get_config",
    "load_config",
]

from pathlib import Path
from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None


class ZenohConfig(BaseSettings):
    """Zenoh communication settings."""
    model_config = SettingsConfigDict(env_prefix="VELVET_ZENOH_")
    
    device_id: str = "velvet-dev"  # Unique ID for this node on the mesh
    mode: Literal["peer", "client", "router"] = "peer"
    connect: list[str] = Field(default_factory=list)  # e.g., ["tcp/192.168.1.100:7447"]
    listen: list[str] = Field(default_factory=list)   # e.g., ["tcp/0.0.0.0:7447"]
    
    # TLS / mTLS transport security
    tls_enabled: bool = False
    tls_root_ca: str = ""               # Path to CA cert (PEM)
    tls_server_cert: str = ""           # Path to this node's cert (PEM)
    tls_server_key: str = ""            # Path to this node's private key (PEM)
    tls_mtls_enabled: bool = False      # Require client certs for mutual auth
    tls_close_on_expiry: bool = True    # Close links when cert expires


class SecurityConfig(BaseSettings):
    """Mesh-wide security policy."""
    model_config = SettingsConfigDict(env_prefix="VELVET_SECURITY_")
    
    allow_google_adapter: bool = False        # Explicit opt-in for cloud LLM
    mesh_secret: str = ""                     # Shared secret for HMAC message signing
    require_signed_messages: bool = True      # HMAC on VelvetMessage (default: on)
    certs_dir: str = "~/.velvet/certs"        # TLS certificate storage directory


class AudioConfig(BaseSettings):
    """Audio processing settings."""
    model_config = SettingsConfigDict(env_prefix="VELVET_AUDIO_")
    
    enabled: bool = True
    wake_word: str = "hey_jarvis"
    sample_rate: int = 16000
    vad_threshold: float = 0.5
    silence_duration_ms: int = 1000
    
    # Provider selection — plug-and-play engine swap
    tts_provider: str = "pyttsx3"       # "piper" | "google" | "riva" | "pyttsx3"
    stt_provider: str = "google"        # "whisper" | "google" | "riva"
    
    # Real audio pipeline — model file paths (empty = mock mode)
    use_real_audio: bool = False         # VELVET_AUDIO_USE_REAL_AUDIO
    whisper_model_path: str = ""         # VELVET_AUDIO_WHISPER_MODEL_PATH
    tts_model_path: str = ""             # VELVET_AUDIO_TTS_MODEL_PATH
    wake_model_path: str = ""            # VELVET_AUDIO_WAKE_MODEL_PATH


class LLMConfig(BaseSettings):
    """LLM inference settings."""
    model_config = SettingsConfigDict(env_prefix="VELVET_LLM_")
    
    # Adapter selection: "ollama", "llama.cpp", "vllm", or "google"
    adapter: str = "ollama"
    model: str = "llama3.1:8b"
    vision_model: str = "moondream" # Model used for multimodal tasks
    base_url: str = "http://localhost:11434"  # Ollama default; vLLM uses :8000
    google_api_key: str | None = None  # For GoogleAIAdapter
    
    # Resilience
    timeout_sec: int = 30        # Max seconds for a single LLM call
    stream_by_default: bool = True  # Use streaming for LLM responses
    
    # Manager model (for llama.cpp direct loading)
    manager_model_path: Path | None = None
    manager_context_length: int = 8192
    manager_gpu_layers: int = -1  # -1 = all layers on GPU
    
    # Fast model
    fast_model_path: Path | None = None
    fast_context_length: int = 2048
    fast_gpu_layers: int = -1


class ShenConfig(BaseSettings):
    """Configuration for Project Shen (Cognitive Layer)."""
    model_config = SettingsConfigDict(env_prefix="VELVET_SHEN_")

    # Po (Edge) Models
    po_reflex_model: Path | None = None  # e.g., Mistral-Nemo-12B
    po_vision_model: Path | None = None  # e.g., LLaVA-v1.6

    # Hun (Host) Models
    hun_reasoning_model: Path | None = None # e.g., Nemotron-70B

    # Inference settings
    gpu_layers: int = -1  # Default to full GPU offload where possible


class ContextConfig(BaseSettings):
    """Context management settings."""
    model_config = SettingsConfigDict(env_prefix="VELVET_CONTEXT_")
    
    # Track types to enable
    tracks: list[str] = Field(
        default_factory=lambda: ["personal", "spatial", "project", "business", "agent"]
    )
    
    # Memory settings
    working_memory_ttl_sec: int = 300  # 5 minutes
    session_memory_ttl_sec: int = 86400  # 24 hours


class StorageConfig(BaseSettings):
    """Storage paths and settings."""
    model_config = SettingsConfigDict(env_prefix="VELVET_STORAGE_")
    
    data_dir: Path = Field(default_factory=lambda: Path.home() / ".velvet")
    vector_db_path: Path | None = None  # Defaults to data_dir / "vector_db"
    sqlite_path: Path | None = None  # Defaults to data_dir / "velvet.db"


class GatewayConfig(BaseSettings):
    """Gateway orchestrator settings."""
    model_config = SettingsConfigDict(env_prefix="VELVET_GATEWAY_")
    
    max_workers: int = 2              # Concurrent request workers
    autonomy_level: int = 2           # 0=read-only, 1=info, 2=ask, 3=auto, 4=full auto
    tts_overlap: bool = False         # If True, allow overlapping TTS (no lock)


class MemoryConfig(BaseSettings):
    """Memory system settings (PowerMem + Tartarus cold store)."""
    model_config = SettingsConfigDict(env_prefix="VELVET_MEMORY_")

    # Embedding
    embedding_model: str = "mxbai-embed-large"

    # Storage paths (defaults derived from storage.data_dir at runtime)
    memory_db_path: str = ""             # Default: ~/.velvet/memory.db
    tartarus_db_path: str = ""           # Default: ~/.velvet/tartarus.db

    # Graph store
    graph_enabled: bool = True

    # Intelligent memory (Ebbinghaus)
    decay_rate: float = 0.1
    reinforcement_factor: float = 0.3
    working_threshold: float = 0.3
    short_term_threshold: float = 0.6
    long_term_threshold: float = 0.8

    # Agent memory
    agent_scope: str = "public"          # Default scope for mesh-wide sharing

    # Query rewrite
    query_rewrite_enabled: bool = True

    # Audit
    audit_enabled: bool = True
    audit_retention_days: int = 90


class XiConfig(BaseSettings):
    """Xi (息) background task manager settings."""
    model_config = SettingsConfigDict(env_prefix="VELVET_XI_")

    journal_path: str = ""               # Default: ~/.velvet/xi_journal.jsonl
    journal_max_processed: int = 1000    # Keep last N processed for debugging
    flush_on_shutdown: bool = True


class VisionConfig(BaseSettings):
    """Vision processing settings — all thresholds configurable."""
    model_config = SettingsConfigDict(env_prefix="VELVET_VISION_")
    
    enabled: bool = True
    motion_threshold: int = 30000       # Pixel change score to trigger event
    rate_limit_sec: float = 2.0         # Max 1 vision event per N seconds
    camera_index: int = 0               # OpenCV camera index
    fps: float = 2.0                    # Monitor frame rate
    log_level: str = "DEBUG"            # "DEBUG" or "INFO" for motion events


class VelvetConfig(BaseSettings):
    """Main configuration aggregating all subsystems."""
    model_config = SettingsConfigDict(
        env_prefix="VELVET_",
        env_nested_delimiter="__",
    )
    
    # Subsystem configs
    zenoh: ZenohConfig = Field(default_factory=ZenohConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    shen: ShenConfig = Field(default_factory=ShenConfig)
    context: ContextConfig = Field(default_factory=ContextConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    vision: VisionConfig = Field(default_factory=VisionConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    xi: XiConfig = Field(default_factory=XiConfig)
    
    # Global settings
    debug: bool = False
    log_level: str = "INFO"
    device_id: str = "velvet-dev"
    device_name: str = "Velvet Development"
    
    def ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        self.storage.data_dir.mkdir(parents=True, exist_ok=True)
        
        if self.storage.vector_db_path is None:
            self.storage.vector_db_path = self.storage.data_dir / "vector_db"
        self.storage.vector_db_path.mkdir(parents=True, exist_ok=True)
        
        if self.storage.sqlite_path is None:
            self.storage.sqlite_path = self.storage.data_dir / "velvet.db"
        
        # Memory paths
        if not self.memory.memory_db_path:
            self.memory.memory_db_path = str(self.storage.data_dir / "memory.db")
        if not self.memory.tartarus_db_path:
            self.memory.tartarus_db_path = str(self.storage.data_dir / "tartarus.db")
        if not self.xi.journal_path:
            self.xi.journal_path = str(self.storage.data_dir / "xi_journal.jsonl")
        
        # Logs directory for audit
        logs_dir = self.storage.data_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)


# Global config instance (lazy loaded)
_config: VelvetConfig | None = None


def get_config() -> VelvetConfig:
    """Get or create the global configuration instance."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def load_config(config_path: Path | None = None, **overrides) -> VelvetConfig:
    """
    Load configuration from file and/or environment.
    If config_path is None, looks for 'velvet.toml' in current directory.
    """
    global _config
    
    file_data = {}
    
    # 1. Search for config file
    if config_path is None:
        potential_path = Path("velvet.toml")
        if potential_path.exists():
            config_path = potential_path

    # 2. Load TOML if available
    if config_path and tomllib:
        try:
            with open(config_path, "rb") as f:
                file_data = tomllib.load(f)
            # Flatten one level if it's nested under 'velvet' key
            if "velvet" in file_data and len(file_data) == 1:
                file_data = file_data["velvet"]
        except Exception as e:
            # Non-fatal, we still have env vars
            from loguru import logger
            logger.warning(f"Failed to load config file {config_path}: {e}")

    # 3. Create config (Overrides > Env Vars > File > Defaults)
    # Priority 1 (Lowest): Defaults (from VelvetConfig definition)
    # Priority 2: Config File
    # Priority 3: Environment Variables
    # Priority 4 (Highest): Manual overrides
    
    # Step A: Load defaults + File
    temp_cfg = VelvetConfig(**file_data)
    
    # Step B: Merge with Env Vars (Pydantic naturally reads these)
    # We create an instance with NO arguments so it only has Defaults + Env
    # and use exclude_unset=True to get only what was actually in Env
    env_data = VelvetConfig().model_dump(exclude_unset=True)
    
    # Step C: Combine everything using deep update
    def _deep_update(d, u):
        for k, v in u.items():
            if isinstance(v, dict) and k in d and isinstance(d[k], dict):
                _deep_update(d[k], v)
            else:
                d[k] = v
        return d
        
    final_data = temp_cfg.model_dump()
    _deep_update(final_data, env_data)
    _deep_update(final_data, overrides)
    
    _config = VelvetConfig(**final_data)
    _config.ensure_directories()
    return _config
