# Architectural Notes & Developer Documentation

## Velvet Nadir Architecture Overview

Velvet Nadir is a personal, decentralized AI system built around local hardware, privacy preservation, and an invisible, audio-first user interaction philosophy (*"The best interface is no interface. The best AI is invisible until needed."*).

---

## 1. Shen Cognitive Subsystems & Dynamic Router (`Yi`)

The cognitive core is divided into specialized daemons inspired by Eastern philosophy rather than generic monolithic agents:

- **Yi (Intent & State Router)**: 
  - Dynamic State Router returning structured `DispatchResult`.
  - Evaluates `UI_Score = D + (V × 1.5) + (M × 2) + S` to determine output modality.
  - Implements **Reverse Escalation**: If a worker or reflex daemon emits a `ReasoningDemand`, control is passed to `Hun` with the intermediate state preserved.
- **Hun (Deep Reasoning)**:
  - High-capacity LLM engine for multi-step reasoning, plan synthesis, and complex ambiguity resolution.
  - Integrated with `ModelAffinityTracker` for recording latency and task quality ELO scores.
- **Po (Reflex Engine)**:
  - Fast, low-latency reflex responder for voice/audio interactions and instant single-turn actions.
- **Jing (MemPalace & Knowledge Graph)**:
  - Ephemeral & persistent memory layer with P2P Zenoh mesh replication (`MeshMemorySync`).
- **Xi (Background Task & Locus Tracking)**:
  - Manages spatial coordinates (`LocusEngine`), spatial centroid clustering for geofence discovery (`TriangulationTask`), and background scheduler loops.

---

## 2. Context-Aware Modality & Display Routing

UI is generated **only** when `UI_Score ≥ 4` **AND** a suitable display is nearby.

### Output Modality Levels:
1. **LEVEL 0 (`ZERO_UI`)**: Pure voice/audio response. System remains invisible.
2. **LEVEL 1 (`MICRO_UI`)**: HUD overlay / toast notification on smart glasses or smart displays.
3. **LEVEL 2 (`WIDGET_UI`)**: Compact interactive floating widget for media playback, 3D model manipulation, or quick approval.
4. **LEVEL 3 (`MACRO_UI`)**: Full workspace takeover for complex multi-file management or deep visualization.

### Direct Manipulation Handlers:
- **Media Controller**: Timeline scrubbing, play/pause, rewind/forward.
- **3D Model Inspector**: Click-and-drag 360° wireframe/mesh spin and zoom controls.
- **File Explorer**: Real-time Zenoh P2P directory browsing and remote file editing/saving (`device.files.list`, `device.files.save`).
- **Device Commandeering & Sensors**: Toggle camera/mic streams and commandeer remote compute nodes (`device.commandeer`, `device.stream.toggle`).

---

## 3. Key Un-deferred Subsystems & Remediations

1. **`ModelAffinityTracker`**: Real-time ELO scoring and online capability mapping for LLM model routing based on task domain.
2. **`TriangulationTask`**: Spatial centroid clustering on coordinate traces to automatically discover home/work/frequently visited geofences.
3. **`MarkdownSkill`**: Dynamic rendering of `.md` skill bundles directly into LLM prompt contexts.
4. **`basilisk_authenticate`**: P2P biometric authentication handlers registered over the Zenoh mesh.
5. **Data Integrity & Concurrency**: Fail-closed HMAC verification, SQLite `asyncio.Lock()` write serialization, and lossless context summarization buffer snapshots.

---

## 4. Future Roadmap Notes

- **Gaming Support**: Device commandeering infrastructure will be extended to support ultra-low-latency game streaming (< 10ms). Capture/encode/stream pipeline must support hardware-accelerated codecs (H.264/HEVC/AV1 via NVENC/AMF/VAAPI). Gaming controller input passthrough via WebRTC data channels. Research: Sunshine/Moonlight protocol, scrcpy for mobile, WebRTC-native capture.
- **Hardware Platform Flexibility**: System must remain hardware-agnostic. Target devices include desktop GPUs (NVIDIA RTX, AMD), ARM64 edge devices (NVIDIA Jetson, Raspberry Pi), DGX clusters, phones, tablets, headless servers, and wearables. One capture/commandeer solution must work universally.
- **Speculative Decoding (Xiān 先)**: Small draft models (1-3B) paired with main models for 2-3x inference speedup. Managed by Polymath.
- **Model Merging**: Mergekit-based domain model fusion (SLERP/TIES/DARE). Approval-based like skill approval. Background Xi breath task.
- **Financial Infrastructure**: Two domains — Agent Economy (internal wallets for AI expenditure) and Business Finance (real money, trading, payments). Strict terminology separation to avoid confusion with LLM tokens.

- Sunshine/Moonlight should remain a first-class option. Velvet will not always be constrained to a browser tab. Native desktop/mobile apps in the future can act as direct Moonlight clients to leverage its ultra-low latency and controller passthrough.
- **Velvet as an Operating System**: The ultimate long-term vision is to convert Velvet from a Python applet into a full-blown, universal Operating System. It will grow into that eventually; for now, we keep the architecture flexible but maintain the applet scope.
- **Bulletproof Cryptography & Secrets**: Secret management and agent wallets are fortified by `MirageProtocol` (in-memory log scrubbing), `BasiliskEnclave` (ephemeral key assembly), and Fractal Key Sharding (threshold cryptography across the mesh). Agents cannot accidentally delete shards.
- **Hierarchical Roster**: The `BusinessParadigmSkill` defines a powerful C-Suite roster. The CEO agent orchestrates tasks via `TaskGraph` and sub-agents can dynamically request delegation or budget from the CEO/Treasury.
- **Gateway Single-Turn LLM Loop**: *[To be assessed later]* Currently, `_handle_llm_response` in `gateway.py` exits immediately after executing a tool, rather than looping back to the LLM. This is a deliberate design choice to preserve ultra-low latency for the Audio-First voice UI (e.g. "turn off the lights" should not pause). Multi-step deep reasoning tasks should instead be routed to asynchronous `AgentOrchestrator` workers.
