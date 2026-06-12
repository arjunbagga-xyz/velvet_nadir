# Velvet Nadir - Progress Report

> Comprehensive documentation of all work completed on the personal AI system

**Last Updated:** June 12, 2026  
**Overall Progress:** ~98% to MVP, ~75% to Full Vision

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Sprint History](#sprint-history)
3. [Architecture Decisions](#architecture-decisions)
4. [Modules Implemented](#modules-implemented)
5. [Design Patterns](#design-patterns)
6. [Test Coverage](#test-coverage)
7. [Known Limitations](#known-limitations)
8. [Remaining Work](#remaining-work)
9. [File Reference](#file-reference)

---

## Executive Summary

Velvet Nadir is a personal AI assistant designed to run entirely on local hardware with distributed sensing capabilities. The system has reached a functional prototype stage with cognitive background processing.

### ✅ Completed

| Capability | Implementation |
|------------|----------------|
| Voice interaction | Wake word → STT → LLM → TTS pipeline |
| Universal Audio I/O | Cross-platform PyAudio integration |
| Unified Hardware Intel | `Polymath` singleton for GPU/RAM/OS/provider selection |
| Local LLM | Ollama and llama.cpp adapters |
| Mesh LLM routing | `MeshLLMAdapter` for distributed inference across mesh |
| Tool calling | JSON parsing + execution (wired in Sprint 16) |
| Context awareness | Parallel context tracks (Personal, Workshop, Business) |
| Persistent memory | PowerMem integration with tiered storage (Aether/Mnemosyne/Tartarus) |
| Memory consolidation | Xi scheduler + Fuxi (embed to Jing) + Agni (archive/promote/purify) |
| Mesh memory sync | Hive mind replication via MeshMemorySync + PrivacyGuard |
| Device mesh | Registry supporting 12 connection methods + heartbeats |
| Distributed inference | Mesh-aware dynamic routing to LlamaCpp/Ollama/ONNX nodes |
| Phone integration | WebSocket bridge for audio/video/GPS |
| P2P communication | Zenoh-based message fabric |
| Cognitive architecture | Project Shen — Yi/Po/Hun/Jing taxonomy (unified Po in Sprint 16) |
| Background tasks | Xi scheduler with 6 BreathTasks (Fuxi, Agni, Inari, DeviceWatchdog, Saraswati, SkillApproval) |
| Device trust | TrustEngine with hot cache + confidence EMA |
| Agent hierarchy | AgentOrchestrator with roles + directed channels |
| Model affinity | ModelAffinityTracker for model-task quality ranking (Mesh-wired in Sprint 16) |
| Skill learning | Saraswati pipeline (Shruti → Smriti → Vidya) |
| Learned reflexes | Po pattern learning with JSON persistence |
| Privacy model | Dual perimeter: mesh/internet + trusted/untrusted |
| Cold storage | Tartarus (SQLite FTS5 archive) |
| Vision | Po VisionMonitor (Xiàng-wired in Sprint 16) + VisionEngine (VLM-based) |
| Zenoh Security | Auto-provisioned mTLS and HMAC-SHA256 message signing |
| Multi-Node Deployment | `NativeDriver` asyncssh deployment and multi-node discovery |
| Mesh Memory Fan-out | `mesh_recall` distributed recall across mesh |
| People Recognition | Xiàng facial/voice recognition integration (VisionMonitor-wired in Sprint 16) |
| Spatial Awareness | Locus engine + Triangulation geofence learning |
| Biometric Security Gate | Non-agentic `TrustGate` enforcement for device trust |
| Resilient Embeddings | Self-healing embedding waterfall (Ollama -> vLLM -> ONNX -> Cloud) (Sprint 16) |
| Universal Cloud LLM | Unified Google/NVIDIA/OpenRouter adapter under Security Config gate (Sprint 16) |

### ⚠️ In Progress / Partial

- Custom "Hey Velvet" wake word training
- Start discovery service by default
- 4-level privacy classification (currently 2-level perimeter in PrivacyGuard)

### ❌ Not Started

- Display routing (multi-display coordination)
- TensorRT-LLM for Jetson
- Smart home integrations
- Vehicle integration (CAN bus)

---

## Sprint History

| Sprint | Focus | Status |
|--------|-------|--------|
| 1-2 | Audio pipeline, basic gateway | ✅ Complete |
| 3 | Device mesh, trust levels | ✅ Complete |
| 4 | Test infrastructure, mock layer | ✅ Complete |
| 5 | Reasoning engine prep | ✅ Complete |
| 6 | Stabilization (audio + mesh registration) | ✅ Complete |
| 7 | Utility skills, vision pipeline | ✅ Complete |
| 8 | Agentic tool system (deferred → Sprint 10) | ✅ Complete (as Saraswati) |
| 9 | Mesh LLM routing, device heartbeats | ✅ Complete |
| 10 | Hive Mind memory + Xi + Trust + Saraswati | ✅ Complete |
| 10.5 | Local plug-and-play persistent memory | ✅ Complete (in Sprint 10 Phase 1) |
| 11 | Cleanup | ✅ Complete |
| 12 | Security & Multi-Node | ✅ Complete |
| 13 | Perception & Intelligence (Face, Voice, Location, TrustGate) | ✅ Complete |
| 14 | Basilisk Protocol (Secure P2P RPC) | ✅ Complete |
| 15 | UI Dashboard & Zenoh Wildcard Routing | ✅ Complete |
| 16 | Cognitive Repair, Self-Healing Embeddings & Cloud LLM | ✅ Complete |

---

## Architecture Decisions

### 1. Project Shen — Cognitive Architecture

**Decision:** Implement a Chinese philosophy-inspired cognitive taxonomy.

**Components:**
- **Yi (意)** — Intent Router: classifies input and routes to Po or Hun
- **Po (魄)** — Corporeal Soul: fast reflexes (regex + learned), vision, motor control
- **Hun (魂)** — Ethereal Soul: deep reasoning via LLM + tool orchestration
- **Jing (精)** — Essence: persistent memory (PowerMem with tiered recall)
- **Xi (息)** — Breath: background scheduler running BreathTasks between conversations
- **Polymath** — Hardware intel singleton for device-aware configuration

### 2. Xi BreathTask System

**Decision:** Process background cognitive tasks between conversations, not continuously.

**BreathTask chain (by priority):**
1. `Fuxi` (3) — consolidate turns into Jing, teach Po reflexes
2. `Agni` (5) — archive cold memories, promote hot ones, compact
3. `Inari` (7) — refresh TrustEngine + ModelAffinityTracker caches
4. `DeviceWatchdog` (8) — monitor device health, suggest trust promotions
5. `Saraswati` (9) — observe patterns, generate+validate skills, deploy

### 3. Tiered Memory (Aether/Mnemosyne/Tartarus)

**Decision:** Three temperature tiers for memory recall.

- **Aether** — hot: recent, high-relevance memories (PowerMem RAM cache)
- **Mnemosyne** — warm: older but relevant (PowerMem vector search)
- **Tartarus** — cold: archived, FTS5-searchable (SQLite cold store)

### 4. Dual Privacy Perimeter

**Decision:** Two orthogonal trust boundaries.

- **Mesh ↔ Internet**: no data leaves the mesh without explicit approval
- **Trusted ↔ Untrusted devices**: untrusted devices can be used for compute but receive no data

### 5. Other Decisions

- **Zenoh** instead of MQTT/gRPC (peer-to-peer, no broker)
- **Audio-first** design (voice is primary interface)
- **`@skill` decorator** for plugin registration
- **Autonomy levels** (0-3: passive → informative → suggestive → autonomous)

### 6. MemPalace Architecture Integration (Sprint 15)

**Decision:** Integrate only the **Knowledge Graph** into Jing, deferring/skipping all other features:
- **Contradiction Detection** — *Deferred* to Agni purification layer until KG data is sufficient.
- **AAAK Dialect** — *Deferred* until edge hardware imposes strict context limits.
- **Memory Stack (L0-L3)** — *Skipped*, perfectly overlaps with existing Aether/Mnemosyne/Tartarus.
- **Palace Graph** — *Skipped*, perfectly overlaps with existing ContextWorkspace spatial models.
- **MCP Server** — *Deferred* until external tool interop (Claude/Gemini) is required.

---

## Modules Implemented

### Core Modules (16)

| Module | Lines | Purpose |
|--------|-------|---------|
| `fabric.py` | ~350 | Zenoh communication + message types |
| `context.py` | ~350 | Context tracks + engagement levels |
| `memory.py` | ~530 | ChromaDB vectors + SQLite structured storage |
| `skills.py` | ~260 | Skill framework + registry |
| `gateway.py` | ~530 | Central orchestrator + tool parsing + Xi lifecycle |
| `monitors.py` | ~290 | Stream monitors (mock + real) |
| `audio.py` | ~580 | Audio pipeline (VAD, STT, TTS) |
| `llm.py` | ~370 | LLM adapters (Ollama, llama.cpp, Mesh) |
| `devices.py` | ~550 | Device registry + connections |
| `models.py` | ~400 | Model registry + inference routing |
| `inference.py` | ~700 | Multi-backend inference (LlamaCpp, ONNX, Ollama) |
| `main.py` | ~480 | Core mesh startup and subsystem orchestrator |
| `config.py` | ~200 | Pydantic config + MemoryConfig + XiConfig |
| `main.py` | ~230 | CLI entry point |
| `privacy.py` | ~115 | PrivacyGuard (dual perimeter) |
| `agents.py` | ~270 | AgentOrchestrator (hierarchy + channels) |

### Project Shen Modules (14)

| Module | Lines | Purpose |
|--------|-------|---------|
| `shen/yi.py` | ~70 | Intent router (reflex vs. reasoning) |
| `shen/po.py` | ~365 | Reflexes (regex + learned) + vision |
| `shen/hun.py` | ~120 | Deep reasoning via LLM |
| `shen/jing.py` | ~180 | PowerMem memory (tiered recall + graph) |
| `shen/polymath.py` | ~400 | Hardware intel + memory config builder |
| `shen/tartarus.py` | ~220 | Cold storage archive (SQLite FTS5) |
| `shen/mesh_memory.py` | ~130 | Hive mind sync via Zenoh |
| `shen/xi.py` | ~260 | BreathTask ABC + scheduler + journal |
| `shen/fuxi.py` | ~130 | Consolidation BreathTask |
| `shen/agni.py` | ~185 | Purification BreathTask |
| `shen/trust.py` | ~275 | TrustEngine (hot cache + Jing backing) |
| `shen/affinity.py` | ~240 | ModelAffinityTracker |
| `shen/inari.py` | ~100 | Cache refresh BreathTask |
| `shen/device_watchdog.py` | ~170 | Health monitoring BreathTask |
| `shen/saraswati.py` | ~340 | Skill learning pipeline (Shruti/Smriti/Vidya) |

### Skills (5 files)

| File | Skills |
|------|--------|
| `example_skills/builtin.py` | get_time, system_status, remember, recall, set_engagement, list_skills |
| `example_skills/mesh.py` | list_devices, list_models, add_device, remove_device, device_info, find_compute |
| `skills/__init__.py` | @skill decorator, SkillRegistry, hot-load support |
| `skills/network_ops.py` | Network operations skill |
| `skills/vision_skill.py` | Vision-based skills |

---

## Test Coverage

### Test Suites (247 tests, 245 passed, 2 skipped)

| Suite | Tests | Coverage |
|-------|-------|----------|
| `test_phase1_memory.py` | 33 | Tartarus, PrivacyGuard, Jing, Config |
| `test_phase2_xi.py` | 30 | ConversationTurn, XiJournal, ComputeBudget, Xi, Fuxi, Agni |
| `test_phase3_trust.py` | 27 | TrustEngine, AgentOrchestrator, ModelAffinityTracker, Inari, DeviceWatchdog |
| `test_phase4_saraswati.py` | 26 | Vidya AST validation, Shruti parsing, Smriti extraction, Pipeline |
| `test_po_reflexes.py` | 12 | LearnedReflex serialization, Po learning/matching/persistence |

### Additional Test Files (pre-Sprint 10)

| File | Coverage |
|------|----------|
| `test_tool_parsing.py` | Tool call parsing |
| `test_monitors.py` | Stream monitors |
| `test_audio.py` | Audio pipeline |
| `test_polymath.py` | Hardware detection |
| `test_hun_agentic.py` | Agentic reasoning |
| And 12 others | Various integration tests |

---

## Known Limitations

1. **Wake Word**: Uses "hey jarvis" from OpenWakeWord. Custom "Hey Velvet" requires training.
2. **ONNX Generation**: `generate()` raises `NotImplementedError` (needs model-specific tokenization).
3. **Security (Track A)**: Enforce mTLS, sign messages, auto-provision certs.
4. **Privacy Levels**: PrivacyGuard implements 2-level (trusted/untrusted) vs. vision's 4-level classification.
5. **Display Routing**: Not implemented — TTS-only output currently.
6. **People Recognition**: No face/voice embedding system yet.

---

## Remaining Work

### Sprint 13: PERCEPTION & INTELLIGENCE MVP COMPLETE ✅

Finalized the core intelligence architecture connecting perception to memory and security.
- **236/236 regression tests passing**.
- **Phase 1: TrustGate** — Strictly non-agentic biometric security perimeter that guards device trust promotions with `TrustGateError`.
- **Phase 2: Xiàng (相)** — People Recognition layer capable of matching facial/voice embeddings to identities stored in Jing memory.
- **Phase 3: Locus + Triangulation** — Spatial tracking using haversine math and automatic learning of frequent geofences via Xi `TriangulationTask`.
- **Privacy Perimeter upgrade** — `PrivacyGuard` strictly blocks distribution of raw biometric embeddings (`tensor_data`, `biometrics`) across the mesh, isolating sensitive data locally.

### Sprint 14: THE BASILISK PROTOCOL COMPLETE (PHASE 1) ✅

Implemented secure ephemeral P2P communication and RAM isolation.
- **240/240 regression tests passing**.
- **Phase 1: Basilisk Protocol** — Ephemeral RAM enclaves for secure P2P RPC without long-term persistence.
- **Basilisk Auth** — One-time biometric authentication over secure tunnels.
- **Basilisk Skill** — Generic P2P secure query tool (PASSIVE autonomy, owner-invoked only).
- **Fabric RPC** — Extended Zenoh fabric to support 1:1 Request/Response (Queryables).

### Sprint 15: UI DASHBOARD & ZENOH WILDCARD ROUTING COMPLETE ✅

Resolved deep architectural communication issues and brought the UI online.
- **Display Bridge & UI Connectivity** — React-based WebSocket UI now connects to `display.py` for monitoring.
- **Zenoh Wildcard Pattern Matching** — `_dispatch_local` now fully supports standard `*` and `**` routing, allowing broad local subscriptions (like `sys/**` for the Noise tab) to perfectly catch local heartbeats and events in real-time.
- **System Stability** — Restored accidentally overwritten `MessageType` enums (e.g. `BASILISK_AUTH`, `TRUST_CHANGE_REQUEST`) ensuring error-free boot sequences.
- **Vision Affirmation** — Despite adding the Display UI, the system strictly remains **Audio-First** and **Local-First**. The UI is purely an optional contextual monitor. The current reliance on the Google AI adapter / `gemini-3-flash-preview` is **strictly patchwork for testing** and will be replaced by fully local models (Ollama/Llama.cpp) once hardware constraints are resolved.

| Skill approval queue (Saraswati) | Medium | ✅ Done |
| Remove `GoogleAIAdapter` (privacy violation) | High | ⏳ Deferred (Sprint 16) |

### Sprint 12: Security & Multi-Node (COMPLETE ✅)

| Task | Priority | Status |
|------|----------|--------|
| Core Mesh Security Model (`CertManager`, HMAC) | High | ✅ Done |
| Zenoh security (mTLS integration) | High | ✅ Done |
| NativeDriver `asyncssh` transition | Medium | ✅ Done |
| MeshMemorySync `mesh_recall` fan-out | Medium | ✅ Done |
| Comprehensive Multi-Node Scanning (Nmap fallback) | Low | ✅ Done |

### Sprint 16 / Immediate Next Steps

| Task | Notes |
|------|-------|
| Train "Hey Velvet" wake word | 2-4 hours |
| End-to-end live integration test (live Ollama) | 2-4 hours |
| Restore Local Embedding Pipeline | Fix Ollama validation error in `Jing` |
| Remove `GoogleAIAdapter` | Enforce local-first mandate |

### Full Vision (Future)

| Task | Notes |
|------|-------|
| Deploy on Jetson Thor | Requires hardware |
| TensorRT-LLM adapter | Jetson-specific |
| Display routing | Multi-display coordination |
| People recognition | Face/voice embeddings |
| Spatial awareness | Geofence context merging |
| Smart home integrations | Home Assistant |
| Vehicle integration | CAN bus, OBD-II |

---

## File Reference

### Source Files (42 total)

```
d:\Open Projects\seamless_computing\sw\velvet\
├── velvet/
│   ├── __init__.py
│   ├── agents.py          # Agent hierarchy + orchestration
│   ├── audio.py           # Audio pipeline (VAD, STT, TTS)
│   ├── config.py          # Pydantic config + MemoryConfig + XiConfig
│   ├── context.py         # Context management
│   ├── devices.py         # Device registry
│   ├── drivers.py         # Hardware drivers
│   ├── fabric.py          # Zenoh fabric
│   ├── gateway.py         # Central gateway + Xi lifecycle
│   ├── inference.py       # Multi-backend inference
│   ├── llm.py             # LLM adapters
│   ├── main.py            # CLI entry point
│   ├── memory.py          # Legacy memory (ChromaDB + SQLite)
│   ├── models.py          # Model registry
│   ├── monitors.py        # Stream monitors
│   ├── onboarding.py      # Device onboarding
│   ├── devices.py         # Hardware registry
│   ├── privacy.py         # PrivacyGuard
│   ├── scan.py            # Network scanning
│   ├── tool_parsing.py    # Tool call parsing
│   ├── example_skills/
│   │   ├── builtin.py     # Core skills
│   │   └── mesh.py        # Mesh skills
│   ├── services/
│   │   ├── google_ai.py   # Google AI adapter (to be removed)
│   │   └── llm_service.py # LLM service layer
│   ├── shen/              # Project Shen (cognitive architecture)
│   │   ├── __init__.py    # Exports
│   │   ├── yi.py          # Intent router
│   │   ├── po.py          # Reflexes + vision + learned reflexes
│   │   ├── hun.py         # Deep reasoning
│   │   ├── jing.py        # Persistent memory (PowerMem)
│   │   ├── polymath.py    # Hardware intel
│   │   ├── tartarus.py    # Cold storage
│   │   ├── mesh_memory.py # Hive mind sync
│   │   ├── xi.py          # Background scheduler
│   │   ├── fuxi.py        # Consolidation task
│   │   ├── agni.py        # Purification task
│   │   ├── trust.py       # Trust engine
│   │   ├── affinity.py    # Model affinity tracker
│   │   ├── inari.py       # Cache refresh task
│   │   ├── device_watchdog.py # Health monitor task
│   │   └── saraswati.py   # Skill learning pipeline
│   └── skills/
│       ├── __init__.py    # @skill decorator + registry
│       ├── basilisk_skill.py # Secure P2P skills
│       ├── network_ops.py # Network skills
│       └── vision_skill.py # Vision skills
├── tests/                 # 22 test files, 128+ tests
└── pyproject.toml
```

### Documentation

```
d:\Open Projects\seamless_computing\docs\
├── VISION.md                     # Project vision (aspirational)
├── ARCHITECTURE.md               # System architecture (aspirational)
├── COMMUNICATION_FABRIC.md       # Protocol comparison (aspirational)
├── COMMUNICATION_FABRIC_v1.2.md  # Updated fabric design
├── CONTEXT_MEMORY.md             # Memory design (aspirational)
├── CONTEXT_MEMORY_v1.2.md        # Updated memory design
├── EXTENSIBILITY.md              # Plugin system (aspirational)
├── UI_DESIGN_SYSTEM.md           # UI guidelines
├── PROGRESS.md                   # This file
├── handoff.md                    # Session handoff
└── notes.md                      # Deferred work + ideas
```

---

**The architecture is solid. The cognitive layer is deep. What remains is polish, security, and hardware deployment.**
