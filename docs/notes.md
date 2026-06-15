# Velvet Nadir — Future Work Notes

Living document for deferred features, design ideas, and items not in the current sprint scope.

---

## 🚀 Session Handoff (June 15, 2026) -> Next Agent

**Current State (End of Sprint 17):**
- **Sprint 17 COMPLETE** — MVP Polish & Post-MVP Security Hardening:
  - **The Mirage Protocol (`MirageProxy`):** Implemented in [mirage.py](file:///d:/Open%20Projects/seamless_computing/sw/velvet/velvet/mirage.py). Automatically scrambles personally identifiable information (PII) and sensitive fields (e.g. names, phone numbers, emails) before cloud LLM transmission, replacing them with semantically-consistent synthetic equivalents (e.g. Dr. Amara Singh -> Dr. Elena Novak). It dynamically rehydrates (restores) the original values on response from the cloud.
  - **4-Level Privacy Classification:** Implemented in [privacy.py](file:///d:/Open%20Projects/seamless_computing/sw/velvet/velvet/privacy.py). Data classified into `PUBLIC`, `PERSONAL`, `SENSITIVE`, and `RESTRICTED`. Tagged outgoing and incoming messages via `VelvetMessage`.
  - **Aadhaar & Passport Support:** Added regular expressions and keyword pattern matching in the `PrivacyClassifier` for Aadhaar card and Passport detection, categorizing them under `SENSITIVE`.
  - **Basilisk Protocol RAM Enclave Integration:** Integrated `BasiliskEnclave` inside [universal_llm.py](file:///d:/Open%20Projects/seamless_computing/sw/velvet/velvet/services/universal_llm.py) to manage temporary mapping buffers in RAM for `PERSONAL` and `SENSITIVE` data processed via the Mirage Protocol.
  - **Device-Bound Restricted Memory Sync:** Configured memory sync in [mesh_memory.py](file:///d:/Open%20Projects/seamless_computing/sw/velvet/velvet/shen/mesh_memory.py) to ensure that `RESTRICTED` data stays on the local device forever and is never shared across peers or cloud vectors. Gated Aether vector database insert/recall so that if cloud embedding is active, sensitive data routes only to local `Tartarus` FTS5 database to prevent cloud leak.
  - **Hey Velvet Wake Word default:** Updated configurations to default to `"Hey Velvet"` as the zero-training wake word.
- **Robust Test Coverage:** 90 tests passing, covering security, gateway routing, audio-vision, fabric routing, and memory.

- **Notes/Future work - sync for RESTRICTED data:** We need to circle back and check if RESTRICTED data never leaves the device, or we have protocols for data sharing within the mesh. If backing up isn't enabled, this can cause the system to lose data if a device gets damaged. Perhaps we need to brainstorm a data sharing/backup sysyem, but first audit what we currently have.


---

## 🚀 Session Handoff (June 12, 2026) -> Next Agent

**Current State (End of Sprint 16):**
- **Sprint 16 COMPLETE** — Cognitive loop desynchronizations resolved:
  - **Tool execution wired:** `_process_input` in Gateway now calls `_handle_llm_response`, executing tools and adding responses to the context buffer correctly.
  - **get_llm_adapter singleton implemented:** Fixed broken imports in `saraswati.py` and `jing.py`, restoring keyword semantic query expansion and background skill observation/generation.
  - **Unified Po/Jing instances:** Fuxi background task now consolidates directly into Yi's live Po/Jing.
  - **Wired VisionMonitor:** Injected `XiangEngine` into `VisionMonitor` in `Po.__init__` enabling facial/voice recognition.
  - **Model Affinity & Trust wired:** Mesh node selection now scores devices based on ModelAffinity rankings, and Gateway resolves pending actions back to the `TrustEngine` feedback loop.
- **Resilient Self-Healing Embedding Pipeline:** Implemented a waterfall resolver in `Polymath` that probes Ollama, then vLLM, then ONNX, before falling back to cloud (NVIDIA/Gemini/OpenRouter) only if gated by `allow_cloud_adapters=True` and API keys are present.
- **Universal Cloud LLM Adapter:** Created `UniversalCloudLLMAdapter` supporting Google Gemini, NVIDIA NIM, and OpenRouter, all gated behind a unified `allow_cloud_adapters` security setting. The legacy `allow_google_adapter` was deprecated gracefully.
- **Saraswati Skill Approval System:** Added `SkillApprovalTask` in Xi to check pending skills and proactively prompt the user, along with a GET/POST REST API in the `DisplayBridge` `/api/skills/pending`.

**Note on Security & Privacy Drift:**
- Outbound API calls to Google Gemini, NVIDIA integrate, and OpenRouter are strictly opt-in and restricted.
- The `PrivacyGuard` must be extended in future sprints to enforce strict data filtering on outbound cloud requests, ensuring personal conversational data never leaks.

---

## 🚀 Session Handoff (May 11, 2026) -> Next Agent

**Current State (End of Sprint 15):**
- **Sprint 15 COMPLETE** — UI Dashboard brought online, Zenoh wildcard routing fully operational (`*` and `**`), and `MessageType` enums restored for a clean boot.
- **Sprint 14 COMPLETE** — The Basilisk Protocol (Phase 1) implemented for secure P2P RPC and ephemeral RAM enclaves.
- **Sprint 13 COMPLETE** — Perception & Intelligence MVP (TrustGate, Xiàng, Locus).
- **Vision Affirmation** — **CRITICAL NOTE FOR NEXT AGENT**: Despite significant work on the React UI dashboard and `display.py`, **the system remains strictly AUDIO-FIRST and LOCAL-FIRST**. The UI is purely an optional contextual monitor. Do not drift into making this a screen-first application.
- **API Patchwork** — The current reliance on `GoogleAIAdapter` and `gemini-3-flash-preview` is **strictly patchwork for testing speed**. The core mission mandates no cloud dependency. The Ollama embedding validation error in `Jing` must be fixed to restore the fully local pipeline.

---

## 🚀 Session Handoff (March 25, 2026) -> Previous Agent

**Current State (End of Sprint 11):**
- **Verification COMPLETE** — 171/171 regression tests passing.
- **Sprint 11 COMPLETE** — Major code cleanup, `__all__` exports, `DeviceScript` sandboxing, error hierarchy, and documentation updates.
- **Sprint 10 COMPLETE** — Hive Mind memory (Phase 1), Xi background tasks (Phase 2), Trust + Agents + Affinity (Phase 3), Saraswati skill learning (Phase 4).
- **Architecture Refined** — Polymath now serves as hardware authority for `LLMService`. TOML config and skill approval queue added.

**~~Sprint 10.5: Local Plug-and-Play Persistent Memory~~ ✅ DONE**

**~~Sprint 10: Tool Creation System + Po Macros~~ ✅ DONE**

---

## 🛠️ Deferred: Agentic Tool Creation (Sprint 8 Proposal)

*Status: Deferred on Feb 14, 2026 to focus on Sprint 7 (Utility & Vision).*

## ⚠️ Deviation Report (Sprint 9)

**Issue**: LLM Selection is Static, not Dynamic.
**Vision**: "Any node can offer LLM services. The Gateway queries the mesh for `capability:llm` and picks the best one."
**Current Implementation**: `MeshLLMAdapter` (Sprint 9) routes to best mesh node. `ModelAffinityTracker` (Sprint 10) learns which models are best per task type.
**Status**: ✅ Mostly resolved. Dynamic discovery via heartbeats + `Polymath` scoring.

**Goal:** Allow the AI to autonomously create and integrate new tools into its own mesh.
**Conceptual Flow:**
1.  **Detection:** AI identifies a missing capability (e.g., "I wish I could control the smart blinds").
2.  **Creation:** AI writes a Python script using the `@skill` decorator.
3.  **Deployment:** Script is saved to `~/.velvet/skills/` or a plugin directory.
4.  **Integration:** Registry hot-loads the new skill.
5.  **Validation:** AI runs a test to verify the tool works.

---

## 🔒 Deferred: Zenoh Security (Sprint 7 Proposal)

*Status: Deferred on Feb 14, 2026 to focus on MVP.*

**Goal:** Secure the peer-to-peer fabric.
**Plan:**
1.  **Cleanup**: Remove `GoogleAIAdapter` (added in Sprint 9 for testing speed). Codebase should rely solely on local models for privacy.
2.  **Config:** Add `user`/`password` to `ZenohConfig`.
2.  **Fabric:** In `init_fabric`, pass credentials to `zenoh.Config()`:
    ```python
    config.insert_json5("user", f'"{cfg.user}"')
    config.insert_json5("password", f'"{cfg.password}"')
    ```
3.  **Validation:** Ensure all nodes (Host, Phone, Jetson) share these credentials.

---

## Deferred Features (from Original Vision)

These are part of the full architecture but not prioritized for the current implementation sprints.

### Display Routing

Multi-display coordination: smart glasses, phone, workshop screen, desktop monitor.

- **Why deferred:** No display hardware available yet. The output system is currently TTS-only.
- **When to revisit:** When we have a second output device (phone app, web dashboard, glasses).
- **Design direction:** The original vision has a Display Selector (rules-based routing) + UI Generator + Display Adapters. Start simple with a WebSocket-based web dashboard before going multi-display.

### Privacy Classification

4-level data classification (Public → Personal → Sensitive → Restricted) with per-level processing rules.

- **Why deferred:** Single-device, single-user for now. No risk of data leaving the device.
- **When to revisit:** Before multi-device deployment (Sprint 3+). Once data flows between devices, classification is critical.
- **Design direction:** Tag every `VelvetMessage` with a privacy level. The fabric enforces routing rules — e.g., RESTRICTED data never leaves the source device.

### Edge Processing (TinyML)

Lightweight models on sensor devices for pre-filtering (is this speech? motion? silence?).

- **Why deferred:** Need physical sensor hardware (cameras, mics on separate devices from compute).
- **When to revisit:** When we have dedicated sensor nodes separate from the main compute.
- **Design direction:** The stream processing pipeline (Edge → Analysis → Aggregation) is well-defined in `ARCHITECTURE.md`. The `monitors.py` mock implementations are the placeholder for this.

### ~~Plugin Hot-Plug~~ ✅ IMPLEMENTED

Implemented as Saraswati/Vidya in Sprint 10:
- **Vidya** validates generated skill code via AST analysis (banned calls/imports) and deploys safe `.py` files to `~/.velvet/skills/`.
- Hot-loading via `importlib.import_module()` in `skills/__init__.py`.
- Saraswati pipeline: Shruti (observe patterns) → Smriti (generate code) → Vidya (validate + deploy).

### Context Merging (Location-Aware)

Automatic context switching based on location — e.g., entering the workshop merges personal + workshop contexts.

- **Why deferred:** Needs GPS/geofence hardware and location-aware triggers.
- **When to revisit:** After real audio pipeline is working and we have at least one spatial sensor.
- **Design direction:** Define geofence zones in config. When `context/location` events fire, the ContextManager merges appropriate tracks.

### ~~Memory Consolidation ("Nightly")~~ ✅ IMPLEMENTED

Implemented as Xi BreathTasks in Sprint 10:
- **Fuxi** (priority 3): Embeds conversation turns into Jing, identifies patterns for Po reflexes.
- **Agni** (priority 5): Archives cold memories to Tartarus, reinforces important ones, promotes hot memories, compacts storage.
- Runs automatically at conversation boundaries via `Gateway._xi_breathe_safe()`.

---

## Design Ideas (Brainstorming)

### LLM Timeout + Cancellation (Sprint 1)

**Problem:** If an LLM server hangs or is unreachable, the worker blocks forever.

**Approaches:**
1. `asyncio.wait_for()` — simple timeout wrapper
2. Cancellation token — `asyncio.Event` passed through the queue
3. Stream-based cancellation — abort mid-token by breaking the async generator
4. **Recommended:** All three combined — timeout (30s) + cancel command + streaming

**Config:** `VELVET_LLM_TIMEOUT_SEC=30`, `VELVET_LLM_STREAM_BY_DEFAULT=true`

### Agentic Device Seeding

**Status**: **Deferred**. Sprint 10 focused on Hive Mind memory and skill learning instead.

**Problem:** How do we add devices to the mesh that don't have Velvet installed?

**Concept:** A `seed_device` skill that:
1. Discovers devices on the network (mDNS/ARP scan)
2. Probes via SSH to detect hardware/OS
3. Deploys a minimal Velvet agent (fabric + heartbeat + model loader)
4. The agent announces itself on the Zenoh mesh

**Security:** Must require explicit user confirmation (AutonomyLevel.LEVEL_2). Phase 1 supports SSH with key-based auth only. Script execution on remote machines is sandboxed.

**Open questions:**
- What's the minimal agent package? Just `fabric.py` + `config.py` + heartbeat loop?
- How do we handle devices without Python (microcontrollers, IoT)?
  - Option A: cross-compiled Zenoh client in C/Rust
  - Option B: HTTP bridge — device communicates via REST, bridge translates to Zenoh
- How do we handle firmware updates on seeded devices?

---

## Minor Cleanup (Tracked) — Sprint 11 Target (COMPLETE ✅)

- [x] Add `__all__` exports to all `velvet/*.py` modules
- [x] `devices.py` has `DeviceScript.script` field — sandboxing implemented (AST + restricted globals)
- [x] Audit `import time` in hot paths — **no blocking `time.sleep` in async hot paths found**
- [x] `MessageType` — 11 unused variants identified. Grouped under `# Future Capabilities` comment block in `fabric.py`.
- [x] Standardize error handling across all adapters (new `errors.py`)
- [x] ~~Remove `GoogleAIAdapter`~~ — **DEFERRED** for prototype phase.
- [x] Add `custom_fields: dict` to `AgentIdentity` for UI agent config
- [x] Polymath integration for high-perf LLM backends (TensorRT/vLLM/llama.cpp)
- [x] TOML configuration loader support
- [x] Skill approval queue persistence + fabric notification in Saraswati

---

## ⏳ Deferred from Sprint 11 to Sprint 12+ (Hardware / Multi-Node)

The following items were identified during the Sprint 11 audit but explicitly deferred because they require specific hardware scenarios or complex multi-device network states that were out-of-scope for the stabilization sprint:

1. **Real SSH Connections (`drivers.py`)** — Replacing simulated async sleep with real Python `asyncssh` for device seeding.
2. **Zenoh Queryable Recall (`mesh_memory.py`)** — Implementing the Zenoh request/response protocol so nodes can actively query each other's vector memories, rather than just passively listening to sync broadcasts.
3. **Full `nmap` Wrapper (`scan.py`)** — Deep network fingerprinting for the Interrogator during onboarding (OS/service detection).
4. **TensorRT-LLM Backend (`polymath.py`)** — Integrating `TensorRT-LLM` via PyTriton for Jetson Orin optimized inference.
5. **vLLM Backend (`polymath.py`)** — Integrating `vLLM` for large Linux GPU continuous batching via `Polymath` auto-selection.
6. **Remove `GoogleAIAdapter`** — Still heavily utilized for local testing and debugging speed.
---

## 🧠 MemPalace Architecture Evaluation (Sprint 15)

During Sprint 15, we evaluated the MemPalace architecture for integration. We successfully integrated the **Knowledge Graph** into Jing, but explicitly deferred or skipped the following features:

### 1. Contradiction Detection
- **What**: Checking new assertions against existing KG facts (attribution conflicts, temporal errors).
- **Decision**: **DEFERRED**. Highly relevant for our multi-agent mesh where conflicting memories are inevitable. We will wire this into **Agni** (the purification layer) to flag contradictions during memory consolidation, but only after Agni is fully operational and we have enough KG data.

### 2. AAAK Dialect (Lossy Text Compression)
- **What**: ~40% token reduction via entity-aware abbreviation mappings.
- **Decision**: **DEFERRED**. We aren't hitting token limits yet. Will revisit when we deploy to edge devices (e.g., Jetson Thor) where context window pressure is high and compute/RAM is strictly limited.

### 3. Memory Stack (L0–L3 Progressive Loading)
- **What**: 4-layer memory metaphor (Identity, Story, Recall, Search).
- **Decision**: **SKIPPED**. Directly overlaps with our **Aether / Mnemosyne / Tartarus** tiered storage model. No value in replacing a working system. Revisit only if we deprecate PowerMem entirely.

### 4. MCP Server (29 External Tools)
- **What**: Full Model Context Protocol (MCP) tool suite for palace reads/writes and KG operations.
- **Decision**: **DEFERRED**. Built for external interop (Claude Code, Gemini CLI). Will revisit in the distant future when we want to build developer APIs or integrate Velvet with external standard agentic frameworks.

### 5. Palace Graph (Room-Based Navigation)
- **What**: Cross-wing navigation graph built from ChromaDB metadata.
- **Decision**: **SKIPPED**. Overlaps heavily with our **ContextWorkspace** spatial model and the **Locus** engine. Will only revisit if we need to discover "hidden tunnels" between completely unrelated workspaces.
