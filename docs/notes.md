# Velvet Nadir — Future Work Notes

Living document for deferred features, design ideas, and items not in the current sprint scope.

---

## 🚀 Session Handoff (July 7, 2026) -> Next Agent

**Current State (End of Sprint 18):**
- **Sprint 18 COMPLETE** — Feature Expansion, Specializations & Zenoh Polishes:
  - **Skills Refactor & Armature Preprocessor (Phase 1):** Consolidated skills under `velvet/skills`, resolved circular import paths using `base.py`, implemented L0/L1 progressive loaders for Markdown skills, and built the Armature preprocessor to interpolate environment variables and configuration properties at runtime.
  - **Context Compression & Mirage Gates (Phase 2):** Wired 50% token window compression check using local model summarization in `context.py`, routing cloud calls through Mirage proxy scrambling and local calls raw. Blocked cloud compression when `PROJECT`/`BUSINESS` tracks are active or code/paths are present.
  - **Limen Gateway & Parallel MCP (Phase 3):** Created `LimenGateway` for external A2A agents and remote MCP servers, applying parameter scrambling/rehydration by default, while exempting local stdio/localhost MCP servers from scrambling.
  - **Anamnesis Reconnection & Syzygy (Phase 4):** Implemented causal transaction logging (`Sutra`) using SHA-256 Merkle hashes, and created HMAC-signed version vector exchanges (`Tín Phù`) via Zenoh sync topics to execute structural Syzygy merge.
  - **Occam's Razor Conflict Arbitration (Phase 5):** Updated SQLite schema in `tartarus.py` to support composite keys `(id, hash)` to store conflicting rows concurrently, and implemented LLM-mediated `OccamsRazorTask` to reconcile logical database conflicts asynchronously.
  - **Credential Pool & CUA OS Sandbox (Phase 6):** Created `credentials.py` implementing key rotation and rate-limiting cooldowns. Built `cua_skill.py` auto-registering standard click/type/screenshot execution inside sandboxed environments.
  - **Model Specializations & Zenoh Polishes (Phase 7):** Integrated Chatbot Arena ELO leaderboard data fetched from `api.wulong.dev` with a local database cache `model_benchmarks.json`. Multiplied candidates score in `best_device_for` by normalized ELO scores to route queries to specialized models (e.g. `code` or `text`). Wired real-time Zenoh event broadcasts for fallback downgrades, upgrades recovery, instant conflict resolutions, and dynamic MCP announcements.
- **Robust Test Coverage:** 120 tests passing, covering skills, context compression, limen gateway, reconnection protocols, ELO routing, fallback broadcasts, and Occam conflict resolutions.

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

---

## 🌐 Geopolitical Reference Notes: Stealth Networking & Tunnels

Operating a peer-to-peer (P2P) mesh network across national borders where internet traffic is heavily restricted—such as within China (Great Firewall / GFW), Russia (TSPU / Sovereign Internet), or Iran (filternet)—requires advanced transport obfuscation. Standard encrypted protocols like raw TLS, SSH, or WireGuard are easily detected and blocked.

### 1. Geopolitical Censorship Context

#### The Great Firewall of China (GFW)
The GFW is the most technologically advanced censorship system in the world. It employs active and passive countermeasures:
- **DPI (Deep Packet Inspection)**: Analyzes packet headers and traffic signatures. High-entropy packets (typical of raw P2P protocols like Zenoh, IPFS, or custom binary RPCs) are flagged as suspicious.
- **Active Probing**: When a GFW node detects an unknown protocol wrapped in TLS, it connects back to the source server mimicking different client handshakes. If the server responds in a way that reveals a proxy or VPN daemon, the IP/port is instantly blocked.
- **SNI-Based Blocking**: The GFW matches the Server Name Indication (SNI) in the TLS Client Hello. If the destination domain is blacklisted, the handshake is dropped.
- **Machine Learning & Entropy Analysis**: The GFW measures packet sizes and intervals. Long-lived, symmetric high-bandwidth streams (like model transfers or P2P context synchronization) are flagged as VPN proxies and blocked.

#### Russia's TSPU (Technical Measures for Threat Counteraction)
Implemented under the Russian "Sovereign Internet" law, TSPU devices are installed at all major ISP choke points:
- Focuses on deep DPI signature blocking (e.g. WireGuard, OpenVPN, IPSec, shadowsocks).
- Employs port-throttling and regional internet isolation ("Runet" switch off).

#### Iran's Filternet
- Relies heavily on DNS spoofing, protocol whitelisting, and severe bandwidth throttling of non-whitelisted TLS handshakes.
- Frequently shuts down international gateways during high-alert events, necessitating local-only mesh fallback loops.

---

### 2. Stealth Protocol Implementations

To survive these environments, the P2P transport layer must hide in plain sight by mimicking standard web traffic:

```
┌─────────────────────────────────────────────────────────────┐
│                    GFW Censorship Stack                     │
│                                                             │
│  [Deep Packet Inspection (DPI)] ──▶ Blocks known TLS SNIs   │
│  [Active Probing] ───────────────▶ Tests server endpoints   │
│  [Entropy/Timing Attacks] ───────▶ Blocks high-entropy P2P  │
│  [IP & Port Blockades] ──────────▶ Nullroutes peer IPs      │
└─────────────────────────────┬───────────────────────────────┘
                              │
                    Requires evasion via
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 Stealth Transport Engine                    │
│                                                             │
│  • VLESS + XTLS-Reality: Mimics trusted server certs        │
│  • Trojan + WS + TLS: Encapsulates packets inside WebSockets│
│  • Domain Fronting / CDN Spoofing: Routes via Cloudflare    │
│  • Traffic Padding: Adds jitter to mimic video streams       │
└─────────────────────────────────────────────────────────────┘
```

#### A. VLESS + XTLS-Reality (Zero-Certificate Stealth)
- **Problem with standard TLS**: A proxy server requires a TLS certificate. If we use a self-signed or Let's Encrypt certificate, active probes will detect it because the certificate has no legitimate web presence.
- **The Reality Solution**: XTLS-Reality eliminates the proxy's own TLS certificate entirely. Instead, the proxy "steals" the TLS certificate of a highly trusted, popular website (e.g. apple.com, microsoft.com, yahoo.com) that is already whitelisted by the GFW.
- **Handshake Verification**:
  1. The client sends a Client Hello with the SNI pointing to the decoy site.
  2. The proxy intercepts the handshake. It forwards the request to the real decoy site, receives its real certificate, and passes it to the client.
  3. The client and proxy perform a cryptographic handshake using a private pre-shared key. 
  4. If an active probe connects to the proxy, the proxy forwards it directly to the real decoy site. The probe receives a perfectly valid website handshake, bypassing the censor.

#### B. Trojan-GFW (WebSocket + TLS)
- Trojan encapsulates the custom P2P protocol inside normal WebSocket connections (`wss://`).
- The traffic looks identical to standard web application traffic (such as live chat, notification feeds, or web browser connections).
- Can be fronted by major CDNs (Cloudflare, AWS CloudFront) to conceal the target server IP.

#### C. Domain Fronting & SNI Spoofing
- Routes traffic through CDN services (e.g., Cloudflare, CloudFront).
- The outer SNI header in the TLS handshake points to a popular whitelisted site hosted on the same CDN (e.g., `images.cloudflare.com`).
- The inner HTTP request (encrypted inside TLS) points to our private mesh node. The CDN decrypts the header and routes the packet to our server, while the GFW only sees traffic to Cloudflare.

#### D. Traffic Padding & Timing Obfuscation
- **Constant Bitrate**: Inject dummy packets (padding) to make the upload/download bandwidth look like constant, flat streaming (e.g. mimicking a 1080p video call or VoIP stream).
- **Jitter Injection**: Add random delays to packet intervals to defeat entropy-based timing analysis.
- **Zenoh Broadcast Suppression**: Disable all P2P discovery broadcasts (mDNS/IP multicast) over the physical network. Peers must use static, pre-arranged tunnel endpoints to prevent local network discovery profiling.

#### E. Redundant Multi-Path Mesh
- **Multi-Transport Routing**: Run Zenoh over multiple physical and virtual transports simultaneously (e.g. QUIC for speed, WebSocket for firewall evasion, TCP for reliability, and WebRTC for direct peer-to-peer NAT traversal).
- **Path Selection Heuristic**: Dynamically monitor and switch routes based on real-time latency, jitter, packet loss, and connection throughput.
- **Automatic Failover**: Instantly re-route messages if a specific connection path is blocked or degraded.

#### F. Proxy-Aware Zenoh
- **In-Fabric Proxying**: Add built-in support for SOCKS5 and HTTP/HTTPS client proxies inside Zenoh endpoint configurations (`connect` and `listen`).
- **Proxy Auto-Detection**: Interrogate system settings or read PAC (Proxy Auto-Config) files dynamically to automatically determine outbound routing configurations.

---

## 🚀 Velvet OS & Future Vision (August 2026)

- **Velvet as an Operating System**: The ultimate long-term vision is to convert Velvet from a Python applet into a full-blown, universal Operating System. It will grow into that eventually; for now, we keep the architecture flexible but maintain the applet scope.
- **Gaming & Media First-Class Support**: Sunshine/Moonlight should remain a first-class option. Velvet will not always be constrained to a browser tab. Native desktop/mobile apps in the future can act as direct Moonlight clients to leverage its ultra-low latency and controller passthrough.
- **Bulletproof Cryptography & Secrets**: Secret management and agent wallets are fortified by `MirageProtocol` (in-memory log scrubbing), `BasiliskEnclave` (ephemeral key assembly), and Fractal Key Sharding (threshold cryptography across the mesh). Agents cannot accidentally delete shards.
- **Hierarchical Roster**: The `BusinessParadigmSkill` defines a powerful C-Suite roster. The CEO agent orchestrates tasks via `TaskGraph` and sub-agents can dynamically request delegation or budget from the CEO/Treasury.

---

## 🔌 Architectural Decision: Zenoh Transport & Hardware Bridging

- **Hardware Buses (CAN/Serial) via Zenoh:** Zenoh is the universal nervous system. Physical hardware buses cannot speak Zenoh natively without a bridge. Thus, `bus_drivers.py` acts as our Zenoh Hardware Plugin, listening to physical wiring and publishing to `hardware/event/...`. For microcontrollers (e.g. ESP32), we aim to deploy `zenoh-pico` directly on the firmware so they can publish to Zenoh natively without needing a serial bridge at all.
- **Commandeering (Media vs Signaling):** Zenoh manages the Control Plane (session broker, discovery, `BasiliskEnclave` SDP key exchange). Sunshine/WebRTC manages the Data Plane (raw 60fps UDP video frames). Wrapping 4K video frames inside standard Zenoh messages would add memory copy overhead; thus, the dual-plane architecture is intentional.

---

## 🚀 Sprint 22 Implementation Notes: Execution Architecture

- **Dynamic Worker Delegation (CEO Framework)**: `AgentOrchestrator` (`agents.py`) dynamically registers ad-hoc `AgentIdentity` nodes and spawns concurrent `asyncio` task loops on demand. Sub-agents communicate back to the CEO via `agent/ceo/delegation_request` over Zenoh to request budget or sub-delegation.
- **Firmware Vault & Zenoh-Pico Mesh Distribution**: Pre-compiled `zenoh-pico` binaries for MCUs (ESP32, RP2040) are held in `sw/velvet/firmware_vault/` and shared across the mesh via Zenoh queryables (`velvet/firmware/...`). Flashing is executed via `firmware_ops.py` wrapping `esptool`.
- **Seeding & TrustGate Protocol Integration**: New host nodes are seeded with the full Velvet core payload, booting as `TrustLevel.UNTRUSTED`. No secrets, keys, or sharded credentials are shared until the user completes a biometric authentication (Face/Voice via `TrustGate`) to trigger a `TrustChangeRequest` promotion.
- **Context-Aware Spatial UI Router**: `display.py` integrates `shen/locus.py` spatial coordinates and active sensor inputs (mics/cameras) into an AI/heuristic decision layer to select the optimal physical display for emitting `MACRO_UI` widgets.
- **Gateway Single-Turn LLM Loop**: *[To be assessed later]* Currently, `_handle_llm_response` in `gateway.py` exits immediately after executing a tool, rather than looping back to the LLM. This is a deliberate design choice to preserve ultra-low latency for the Audio-First voice UI (e.g. "turn off the lights" should not pause). Multi-step deep reasoning tasks should instead be routed to asynchronous `AgentOrchestrator` workers.


