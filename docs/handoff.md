# Velvet Nadir Handoff Document

> Current state of the system after Sprint 17, for the next agent or session.

**Last Updated:** June 15, 2026

---

## 1. System State

### Sprint 17: COMPLETE ✅ (90 tests passing)

**MVP Polish & Post-MVP Security Hardening:**
- **The Mirage Protocol (`MirageProxy`):** Automatically scrambles PII/sensitive data (names, emails, phone numbers, Aadhaar, Passport) before cloud LLM transmission using synthetic equivalents (e.g. Dr. Amara Singh -> Dr. Elena Novak) and reverses the mapping on response.
- **4-Level Privacy Classification:** Upgraded system data flows to classify data into `PUBLIC`, `PERSONAL`, `SENSITIVE`, and `RESTRICTED` levels via `PrivacyClassifier` and tags `VelvetMessage`.
- **Aadhaar & Passport Support:** Added pattern/keyword recognition in `PrivacyClassifier` to catch Aadhaar cards and passports, classifying them as `SENSITIVE`.
- **Basilisk Protocol RAM Enclave Integration:** Plumbed `BasiliskEnclave` inside cloud completion pathways to process Mirage Protocol PII maps dynamically in RAM without persistence.
- **Device-Bound Restricted Memory Sync:** Configured memory sync inside `mesh_memory.py` so that `RESTRICTED` data stays on the local device forever and is never shared across peers or cloud vectors. Restricts local vector inserts/queries for `PERSONAL`/`SENSITIVE`/`RESTRICTED` to local FTS5 `Tartarus` store rather than Aether if a cloud embedding service is active, avoiding cloud vector leaks.
- **Hey Velvet Wake Word default:** Updated config/audio defaults to `"Hey Velvet"`.

### Sprint 16: COMPLETE ✅ (200+ tests passing)

**Cognitive Repair & Self-Healing Embeddings:**
- **Wired tool execution:** gateway.py `_process_input` now routes to `_handle_llm_response` to parse and execute tool calls.
- **get_llm_adapter singleton:** Resolved broken imports of `get_llm_adapter` in `saraswati.py` and `jing.py`, enabling semantic search expanders and skill observation.
- **Unified Po/Jing instances:** Modified gateway `_init_xi` to pass Yi's live Po and Jing instances to the Fuxi Consolidation BreathTask.
- **Wired VisionMonitor:** Injected `XiangEngine` into `VisionMonitor` in `Po.__init__` enabling facial/voice recognition.
- **Model Affinity & Trust feedback:** Mesh node routing scores candidates by ModelAffinity, and PendingAction resolutions update `TrustEngine` outcomes.
- **Self-Healing Embedding Waterfall:** Probes Ollama -> vLLM -> ONNX -> Cloud (Gemini/NVIDIA/OpenRouter) dynamically.
- **Universal Cloud LLM Adapter:** Replaced GoogleAIAdapter with a unified adapter for Gemini, NVIDIA NIM, and OpenRouter, gated by `allow_cloud_adapters` in SecurityConfig.
- **Saraswati Skill Approval:** Added `SkillApprovalTask` in Xi to check pending skills and proactively prompt the user, along with a GET/POST REST API in the `DisplayBridge` `/api/skills/pending`.

### Sprint 15: UI DASHBOARD & ZENOH WILDCARD ROUTING COMPLETE ✅
- **Display Bridge & UI Connectivity** — WebSocket UI dashboard syncs real-time events.
- **Zenoh Wildcard Pattern Matching** — Local wildcard routing (`*` and `**`) handles broad local subscriptions correctly.

### Sprint 14: THE BASILISK PROTOCOL COMPLETE (PHASE 1) ✅
- **Basilisk Protocol** — Ephemeral RAM enclaves for secure P2P RPC without long-term persistence.

### Sprint 13: PERCEPTION & INTELLIGENCE MVP COMPLETE ✅
- **TrustGate** — Non-agentic biometric security perimeter guarding device trust.
- **Xiàng (相)** — Facial/voice biometrics matching in Jing.
- **Locus + Triangulation** — Haversine spatial tracking and geofence learning.

---

## 2. Architecture Summary

### Cognitive Architecture (Project Shen)

```
User speaks → Gateway → Yi.dispatch() → Po/Hun → response
                                │
                          Yi._record_turn()
                                │
                         Xi journal (JSONL)
                                │
    ┌──────────┬────────┬───────┼──────────┬──────────────┬──────────────────┐
    ▼          ▼        ▼       ▼          ▼              ▼                  ▼
 Fuxi(3)    Agni(5)  Inari(7) Watchdog(8) Saraswati(9) SkillApproval(10) [future]
```

### Key Components

| Component | Module | Purpose |
|-----------|--------|---------|
| Yi | `shen/yi.py` | Intent routing (reflex vs. reasoning) |
| Po | `shen/po.py` | Fast reflexes + learned patterns + vision |
| Hun | `shen/hun.py` | Deep reasoning via LLM |
| Jing | `shen/jing.py` | Tiered memory (Aether/Mnemosyne/Tartarus) |
| Xiàng | `shen/xiang.py` | People recognition (facial/voice biometrics) |
| Locus | `shen/locus.py` | Spatial awareness and Geofence tracking |
| Xi | `shen/xi.py` | Background task scheduler |
| Polymath | `shen/polymath.py` | Hardware intel + config builder (resilient embeddings waterfall) |
| Universal LLM | `services/universal_llm.py` | Unified Cloud LLM (Gemini/NVIDIA/OpenRouter) |
| Gateway | `gateway.py` | Central orchestrator + Xi lifecycle + tool parsing |
| TrustEngine | `shen/trust.py` | Device trust with hot cache + confidence EMA |
| Basilisk | `basilisk.py` | Ephemeral RAM enclaves + Sanitization |
| PrivacyGuard | `privacy.py` | Dual perimeter (mesh/internet + trusted/untrusted) |
| Errors | `errors.py` | Centralized Velvet Error hierarchy |

---

## 3. File Structure (44 source files)

```
velvet/
├── gateway.py, config.py, main.py    # Core
├── fabric.py, devices.py, models.py  # Mesh
├── audio.py, monitors.py             # I/O
├── llm.py, inference.py              # LLM
├── context.py, memory.py             # Legacy memory
├── privacy.py, agents.py             # Security
├── skills/, example_skills/          # Tool system
├── services/                         # External adapters
│   ├── google_ai.py
│   └── universal_llm.py              # [NEW] Cloud completions
└── shen/                             # Cognitive (16 modules)
    ├── yi.py, po.py, hun.py, jing.py
    ├── xiang.py, locus.py, trust_gate.py
    ├── polymath.py, tartarus.py, mesh_memory.py
    ├── xi.py, fuxi.py, agni.py, triangulation.py
    ├── trust.py, affinity.py, skill_approval.py  # [NEW] Proactive approval BreathTask
    └── inari.py, device_watchdog.py, saraswati.py
```

---

## 4. Next Steps & Deferred Items

### Immediate Next Steps

- **End-to-end live integration test (with live Ollama and real audio)**
- **PrivacyGuard exfiltration filters:** Deepen the outbound security filter checks for cloud requests inside the PrivacyGuard.
- **Audit memory sync for RESTRICTED data:** We need to circle back and check if RESTRICTED data never leaves the device, or we have protocols for data sharing within the mesh. If backing up isn't enabled, this can cause the system to lose data if a device gets damaged. Perhaps we need to brainstorm a data sharing/backup sysyem, but first audit what we currently have.

### Deferred for Future (Post-MVP)

- **Audit memory sync for RESTRICTED data:** We need to circle back and check if RESTRICTED data never leaves the device, or we have protocols for data sharing within the mesh. If backing up isn't enabled, this can cause the system to lose data if a device gets damaged. Perhaps we need to brainstorm a data sharing/backup sysyem, but first audit what we currently have.
- **Context merging implementation** (deferred due to GPS/hardware requirements)
- **TensorRT-LLM adapter** for high-speed local inference on Jetson
- **Deploy on Jetson Thor hardware**
- **Smart home integrations** (Home Assistant)
- **Vehicle integration** (CAN bus, OBD-II)

---

## 5. Vision Docs vs. Reality

| Vision Feature | Status | Implementation |
|---------------|--------|----------------|
| 3-tier memory | ✅ | Aether/Mnemosyne/Tartarus via Jing |
| Memory consolidation | ✅ | Xi + Fuxi + Agni BreathTasks |
| Skill hot-plug | ✅ | Saraswati → Vidya → `~/.velvet/skills/` |
| Device mesh + heartbeats | ✅ | `devices.py` + `fabric.py` |
| Privacy model | ✅ | 4-level classification (PUBLIC/PERSONAL/SENSITIVE/RESTRICTED, Mirage Protocol, and device-bound restricted sync in Sprint 17) |
| Model routing | ✅ | MeshLLMAdapter + ModelAffinityTracker (wired in Sprint 16) |
| Display routing | ❌ | TTS-only output (Target: Sprint 15) |
| People recognition | ✅ | Xiàng facial/voice recognition integration (wired in Po in Sprint 16) |
| Spatial awareness | ✅ | Locus + Triangulation geofence learning (Sprint 13) |
| Context merging | ❌ | Deferred due to hardware constraints |
| Secure P2P RPC | ✅ | Basilisk Protocol (Sprint 14) |

---

## 6. Running the System

```bash
# Tests
cd sw/velvet
python -m pytest tests/ -v

# Run system (requires Ollama)
python -m velvet.main
```

---

*The hardest part — the cognitive architecture — is done. What remains is security, polish, and hardware deployment.*
