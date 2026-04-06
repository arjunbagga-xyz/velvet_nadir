# 🟣 Velvet Nadir

> Personal AI assistant with distributed sensing, multi-LLM orchestration, and universal device mesh

## Quick Start

```bash
# Install core dependencies
pip install -e .

# Test the framework
python test_velvet.py
python test_registries.py

# Start interactive console (text mode)
python -m velvet.main console

# Start live audio mode (requires audio deps)
pip install pyaudio faster-whisper openwakeword piper-tts
python -m velvet.main live --llm llama3.1:8b
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `python -m velvet.main console` | Interactive text console |
| `python -m velvet.main live` | Real microphone + speaker |
| `python -m velvet.main live --llm llama3.1:8b` | Live with LLM responses |
| `python -m velvet.main run` | Background service mode |

### Options
- `--debug` - Enable debug logging
- `--llm MODEL` - Enable LLM (e.g., `llama3.1:8b`)
- `--whisper SIZE` - Whisper model: tiny, base, small, medium, large

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          VELVET NADIR                                     │
├──────────────────────────────────────────────────────────────────────────┤
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                    AUDIO PIPELINE (audio.py)                       │  │
│  │  Mic → WakeWord → VAD → STT → Gateway → TTS → Speaker              │  │
│  └────────────────────────────┬───────────────────────────────────────┘  │
│                               ▼                                           │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │               GATEWAY + LLM (gateway.py, llm.py)                   │  │
│  │  Events → Context → Tool Parsing → Ollama/llama.cpp → Skills       │  │
│  └────────────────────────────┬───────────────────────────────────────┘  │
│                               ▼                                           │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                   DEVICE MESH (devices.py, models.py)              │  │
│  │  Registry → 12 Connection Methods → Distributed Inference          │  │
│  └────────────────────────────┬───────────────────────────────────────┘  │
│                               ▼                                           │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                    INFERENCE BACKENDS (inference.py)               │  │
│  │  llama.cpp (GGUF) │ ONNX (Universal) │ Ollama (API)                │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
```

## Environment Variables

```bash
VELVET_DEBUG=true
VELVET_DEVICE_ID=my-jetson
VELVET_AUDIO__WAKE_WORD="hey velvet"
VELVET_ZENOH__MODE=peer
```

## Project Structure

```
velvet/
├── config.py         # Pydantic settings
├── fabric.py         # Zenoh communication fabric
├── context.py        # Context tracks & working memory
├── memory.py         # Persistent memory (ChromaDB + SQLite)
├── skills.py         # Skill plugin system
├── gateway.py        # Central orchestrator + tool parsing
├── monitors.py       # Audio/vision stream monitors
├── audio.py          # Real audio pipeline (VAD, STT, TTS)
├── llm.py            # LLM adapters (Ollama, llama.cpp)
├── devices.py        # Device registry + 12 connection methods
├── models.py         # Model registry + inference routing
├── inference.py      # Multi-backend inference (llama.cpp, ONNX, Ollama)
├── phone.py          # Phone sensor bridge (WebSocket)
├── main.py           # CLI entry point
└── example_skills/
    ├── builtin.py    # Core skills (time, status, memory)
    └── mesh.py       # Device mesh skills (list, add, remove)
```

## Connection Methods

Velvet is hardware-agnostic. Devices can connect via:

| Method | Use Case |
|--------|----------|
| `zenoh` | Native mesh communication |
| `websocket` | Phone/browser apps |
| `ssh` | Remote machines |
| `bluetooth` | Wearables, peripherals |
| `usb` / `serial` | Arduino, embedded devices |
| `ir` | Remote control devices |
| `http_api` | REST-based IoT |
| `mqtt` / `zigbee` | Smart home protocols |
| `can` | Vehicle bus |
| `custom` | Scripts (Rubber Ducky, etc.) |

## Adding Skills

```python
from velvet.skills import skill, SkillCategory, SkillParameter, SkillResult

@skill(
    name="my_skill",
    description="Does something useful",
    category=SkillCategory.DIGITAL,
    parameters=[
        SkillParameter("arg1", "string", "Description"),
    ],
    tags=["custom"],
)
async def my_skill(arg1: str) -> SkillResult:
    # Your logic here
    return SkillResult.ok(speak="Done!")
```

## Adding Devices

```python
from velvet.devices import Device, DeviceType, ConnectionInfo, ConnectionMethod

# SSH device
device = Device(
    device_id="gpu-server",
    name="Home GPU Server",
    device_type=DeviceType.COMPUTE,
    connection=ConnectionInfo(
        method=ConnectionMethod.SSH,
        address="192.168.1.100",
        username="user",
    ),
    capabilities=["inference", "tts"],
)

# Register
registry = HardwareRegistry()
await registry.register(device)
```

## Dependencies

### Core
- `loguru` - Logging
- `zenoh` - P2P communication
- `chromadb` - Vector memory
- `aiohttp` - Async HTTP

### Audio (optional)
- `pyaudio` - Mic capture
- `openwakeword` - Wake word detection
- `faster-whisper` - Speech-to-text
- `piper-tts` - Text-to-speech

### LLM (optional)
- `llama-cpp-python` - Local inference
- `onnxruntime` - ONNX models
- `httpx` - Ollama API

## License

MIT
