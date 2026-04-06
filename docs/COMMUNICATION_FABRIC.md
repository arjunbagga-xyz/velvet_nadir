# 📡 Communication Fabric: Zenoh Mesh

> Technical details of the peer-to-peer inter-device communication patterns for Velvet Nadir

---

## 🎯 Architecture Decision: Zenoh

Instead of MQTT (central broker failure point), gRPC (point-to-point only without pub/sub), or WebSockets (custom routing overhead), Velvet uses **Zenoh**. 

Zenoh offers a high-performance, decentralized data-centric publish/subscribe model that perfectly matches the offline-first, distributed topology of our mesh.

### Core Benefits
- **Brokerless Pub/Sub**: No central server. Devices discover each other locally over the network.
- **Data-Centric**: Nodes subscribe to specific structured topics (`mesh/device/id`, `audio/wake`).
- **Offline Resilient**: Functions perfectly on a completely disconnected LAN.
- **Low Latency**: Capable of routing real-time voice and high-bandwidth vision streams locally.

---

## 🌐 The Velvet Mesh

### Device Discovery & Heartbeats
Devices register into the mesh by publishing continuous `mesh/device/heartbeat` events (every 10 seconds).

The payload contains critical capabilities used for dynamic scheduling:
```json
{
  "device_id": "thor_gpu_01",
  "capabilities": ["llm", "vision_compute", "storage"],
  "trust_level": 1,
  "load": 0.45,
  "battery": 100
}
```

### Trust Engine and `PrivacyGuard`
Not all Zenoh messages traverse all nodes freely.
- `PrivacyGuard` filters ingress and egress messaging ensuring data tagged as restricted never passes the `Internet` network boundary or to `Untrusted` nodes.
- `TrustEngine` tracks the success rate of a node's responses. If an `audio` node continually drops packets or sends malformed transcripts, its trust EMA degrades.

---

## 📊 Topic Structure

The Zenoh topics are namespaced by subsystem:

### Audio & Sensory
- `audio/wake` → Triggered by OpenWakeWord edge models.
- `audio/transcript` → Output from Whisper running on node.
- `audio/tts_request` → Request a spoken output.
- `audio/vad_event` → Raw Voice Activity Detection segments.

### Mesh Topology
- `mesh/device/announce`
- `mesh/device/heartbeat`
- `mesh/device/leave`

### Reasoning & Skills
- `skill/request` → Commands pushed from the Gateway to execute a tool.
- `skill/response` → Output of the tool execution (JSON balanced payload).
- `llm/request` → A prompt sent out for `MeshLLMAdapter` routing.
- `llm/response` → The inference output text stream.

### Cognitive Synchronization
- `mesh/memory/sync` → The Hive Mind replication channel. When an important memory is added to `Jing` on Node A, it pushes via Zenoh to Node B.

---

## 📡 Edge Connections

For clients that cannot natively run a Zenoh router (like an iOS web browser), Velvet supports bridge adapters:

- **WebSocket Phone Bridge** (`phone.py`): Receives GPS, raw audio tracks, and user UI taps over a FastApi WebSocket interface, subsequently mapping them onto standard Zenoh mesh topics so the core cognitive engine (Project Shen) treats a phone browser as simply another set of sensors.

---

*Because of Zenoh, Velvet is naturally resilient to device drop-outs and seamlessly distributes load whenever a capable new Jetson, Phone, or Desktop joins the mesh.*
