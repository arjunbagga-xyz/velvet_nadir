# 📡 Communication Fabric v1.2

> Simplified, practical communication architecture addressing critique feedback

---

## 📋 Revision Notes

**v1.2 Changes (2026-02-03):**
- Dropped hybrid MQTT+gRPC recommendation for single unified fabric
- Simplified to Zenoh-primary architecture
- Phone is sensor source only, not compute node
- Added hardware topology reality check

---

## 🎯 Design Philosophy

### Core Principles

| Principle | v1.1 Approach | v1.2 Approach | Rationale |
|-----------|---------------|---------------|-----------|
| **Protocol Count** | 3 (MQTT + gRPC + WS) | 1 (Zenoh) + 1 bridge (WS) | Less moving parts = fewer failure modes |
| **Phone Role** | Fallback brain | Dumb sensor endpoint | Android kills background processes |
| **Discovery** | Multi-system | Native to protocol | One less thing to configure |
| **Broker** | Central required | Optional/Peer-to-peer | No single point of failure |

---

## 🏆 Unified Protocol: Zenoh

After reviewing the critique and re-evaluating options, **Zenoh** emerges as the best fit:

### Why Zenoh?

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              ZENOH OVERVIEW                                         │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│   "Zero Overhead Network Protocol"                                                 │
│   Originally from Eclipse Foundation, now at ZettaScale                            │
│                                                                                     │
│   ┌─────────────────────────────────────────────────────────────────────────────┐  │
│   │                                                                             │  │
│   │   ✅ PUB/SUB         Like MQTT but peer-to-peer capable                     │  │
│   │   ✅ RPC             Like gRPC but built-in, no separate system             │  │
│   │   ✅ STREAMING       Native high-bandwidth streams                          │  │
│   │   ✅ DISCOVERY       Zero-config on LAN, just works                         │  │
│   │   ✅ QoS             Reliability levels like MQTT                           │  │
│   │   ✅ DECENTRALIZED   No broker required (mesh topology)                     │  │
│   │   ✅ LOW LATENCY     Designed for robotics/real-time                        │  │
│   │   ✅ SMALL FOOTPRINT Runs on embedded devices                               │  │
│   │                                                                             │  │
│   └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
│   TOPOLOGY:                                                                        │
│   ┌─────────────────────────────────────────────────────────────────────────────┐  │
│   │                                                                             │  │
│   │         ┌─────────┐                           ┌─────────┐                   │  │
│   │         │ Laptop  │◀────────────────────────▶│ Jetson  │                   │  │
│   │         │ (Peer)  │         Zenoh             │ (Peer)  │                   │  │
│   │         └─────────┘         Protocol          └─────────┘                   │  │
│   │              ▲                                     ▲                        │  │
│   │              │                                     │                        │  │
│   │              ▼                                     ▼                        │  │
│   │         ┌─────────┐                           ┌─────────┐                   │  │
│   │         │ Phone   │                           │ Sensors │                   │  │
│   │         │ (Peer)  │                           │ (Peers) │                   │  │
│   │         └─────────┘                           └─────────┘                   │  │
│   │                                                                             │  │
│   │   All nodes are equal peers. No central broker to fail.                     │  │
│   │   Auto-discovery via multicast. Works even if one node is down.             │  │
│   │                                                                             │  │
│   └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### Zenoh vs Alternatives

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              PROTOCOL COMPARISON                                    │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│              │  Zenoh  │  ZeroMQ │  MQTT   │  gRPC   │  Hybrid │                   │
│  ────────────┼─────────┼─────────┼─────────┼─────────┼─────────│                   │
│  Broker-free │   ✅    │   ✅    │   ❌    │   N/A   │   ❌    │                   │
│  Pub/Sub     │   ✅    │   ✅    │   ✅    │   ❌    │   ✅    │                   │
│  RPC         │   ✅    │   ❌    │   ❌    │   ✅    │   ✅    │                   │
│  Streaming   │   ✅    │   ✅    │   ❌    │   ✅    │   ✅    │                   │
│  Discovery   │   ✅    │   ❌    │   ❌    │   ❌    │   ❌    │                   │
│  Low Latency │   ✅    │   ✅    │   ⚠️    │   ✅    │   ⚠️    │                   │
│  ────────────┼─────────┼─────────┼─────────┼─────────┼─────────│                   │
│  Complexity  │   LOW   │  MEDIUM │   LOW   │  MEDIUM │   HIGH  │                   │
│                                                                                     │
│  ✅ = Native support   ⚠️ = Limited   ❌ = Not supported / Requires workaround     │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘

VERDICT: Zenoh replaces the need for MQTT + gRPC with a single unified protocol.
```

---

## 🏗️ System Architecture v1.2

### Hardware Topology (Prototype Phase)

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                         PROTOTYPE HARDWARE TOPOLOGY                                 │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│   ┌─────────────────────────────────────────────────────────────────────────────┐  │
│   │                           STATIONARY COMPUTE                                │  │
│   │                         (On desk/floor, plugged in)                         │  │
│   │                                                                             │  │
│   │   ┌─────────────────────┐     ┌─────────────────────┐                      │  │
│   │   │      LAPTOP         │     │    GPU WORKSTATION  │                      │  │
│   │   │   (Control Node)    │     │   (Inference Node)  │                      │  │
│   │   ├─────────────────────┤     ├─────────────────────┤                      │  │
│   │   │ • Velvet Daemon     │     │ • LLM inference     │                      │  │
│   │   │ • Context Manager   │◀───▶│ • TTS / STT         │                      │  │
│   │   │ • Memory Store      │     │ • Vision models     │                      │  │
│   │   │ • UI Server         │     │ • Heavy compute     │                      │  │
│   │   │ • Zenoh peer        │     │ • Zenoh peer        │                      │  │
│   │   └─────────────────────┘     └─────────────────────┘                      │  │
│   │                                                                             │  │
│   │   Later: Add Jetson Thor here (same role as GPU workstation)               │  │
│   │                                                                             │  │
│   └─────────────────────────────────────────────────────────────────────────────┘  │
│                                      │                                              │
│                                      │ WiFi / Ethernet                              │
│                                      │ (All Zenoh protocol)                         │
│                                      ▼                                              │
│   ┌─────────────────────────────────────────────────────────────────────────────┐  │
│   │                         SENSOR ENDPOINTS                                    │  │
│   │                    (Dumb terminals, no logic)                               │  │
│   │                                                                             │  │
│   │   ┌─────────────────────┐     ┌─────────────────────┐                      │  │
│   │   │    ANDROID PHONE    │     │   USB MICROPHONE    │                      │  │
│   │   │   (Prototype Only)  │     │   + WEBCAM          │                      │  │
│   │   ├─────────────────────┤     ├─────────────────────┤                      │  │
│   │   │ • Camera stream     │     │ • Audio input       │                      │  │
│   │   │ • Microphone stream │     │ • Video input       │                      │  │
│   │   │ • GPS location      │     │                     │                      │  │
│   │   │ • Battery sensors   │     │                     │                      │  │
│   │   │                     │     │                     │                      │  │
│   │   │ NO PROCESSING HERE  │     │ Direct to laptop    │                      │  │
│   │   │ Just streams data   │     │                     │                      │  │
│   │   └─────────────────────┘     └─────────────────────┘                      │  │
│   │                                                                             │  │
│   │   Phone connects via: WebSocket bridge (Zenoh doesn't have Android SDK)    │  │
│   │   This is a prototype limitation, not architecture choice.                 │  │
│   │                                                                             │  │
│   └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### Phone as Sensor Source (Prototype)

The Android phone exists purely for convenience—it has all the sensors we need in one package:

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                         PHONE ROLE (PROTOTYPE ONLY)                                 │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│   WHAT THE PHONE DOES:                           WHAT THE PHONE DOESN'T DO:        │
│   ───────────────────────────                    ─────────────────────────────     │
│   ✅ Streams camera when app open                ❌ Run background services         │
│   ✅ Streams microphone when app open            ❌ Store context or memory          │
│   ✅ Reports GPS location                        ❌ Make decisions                   │
│   ✅ Detects Bluetooth beacons                   ❌ Run LLM inference               │
│   ✅ Displays UI pushed from brain               ❌ Act as "fallback brain"         │
│                                                                                     │
│   CONNECTION:                                                                      │
│   ┌─────────────────────────────────────────────────────────────────────────────┐  │
│   │                                                                             │  │
│   │   Phone App ──[WebSocket]──▶ Laptop (WS→Zenoh Bridge) ──[Zenoh]──▶ Mesh    │  │
│   │                                                                             │  │
│   │   Why WebSocket:                                                            │  │
│   │   • Works in Android WebView/Native                                         │  │
│   │   • No native Zenoh SDK for Android (yet)                                   │  │
│   │   • Battery-friendly when app is foregrounded                               │  │
│   │                                                                             │  │
│   └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
│   FUTURE (Post-Prototype):                                                         │
│   • Replace phone with dedicated wearable (glasses, pin, etc.)                     │
│   • Or: ESP32-based sensor pods with native Zenoh                                  │
│   • Goal: Eliminate phone dependency entirely                                      │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📬 Message Architecture

### Key Spaces (Zenoh Topics)

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              ZENOH KEY SPACES                                       │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│   velvet/                                                                          │
│   │                                                                                │
│   ├── devices/                           # Device presence & status                │
│   │   ├── {device_id}/status             # Online, offline, capabilities           │
│   │   ├── {device_id}/health             # CPU, memory, battery                    │
│   │   └── {device_id}/capabilities       # What this device can do                 │
│   │                                                                                │
│   ├── sensors/                           # Raw sensor streams                      │
│   │   ├── audio/{device_id}              # Audio chunks (16kHz, 16-bit)            │
│   │   ├── video/{device_id}              # Video frames (MJPEG or H264)            │
│   │   ├── location/{device_id}           # GPS coordinates                         │
│   │   └── imu/{device_id}                # Accelerometer, gyroscope                │
│   │                                                                                │
│   ├── events/                            # Processed events (from edge ML)         │
│   │   ├── speech/{device_id}             # Transcribed speech                      │
│   │   ├── wake_word/{device_id}          # Wake word detected                      │
│   │   ├── face/{device_id}               # Face detection/recognition              │
│   │   └── scene/{device_id}              # Scene understanding                     │
│   │                                                                                │
│   ├── context/                           # Context state                           │
│   │   ├── current                        # Unified current context                 │
│   │   ├── personal                       # Personal context layer                  │
│   │   └── {space_id}                     # Spatial context layers                  │
│   │                                                                                │
│   ├── actions/                           # Action requests                         │
│   │   ├── speak                          # TTS requests                            │
│   │   ├── display/{target}               # UI render requests                      │
│   │   └── execute                        # Tool/action execution                   │
│   │                                                                                │
│   └── reflex/                            # Fast-path reflexes (bypass brain)       │
│       ├── triggers                       # Reflex trigger events                   │
│       └── commands                       # Direct actuation commands               │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### Message Format (MessagePack)

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              MESSAGE FORMAT                                         │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│   All messages use MessagePack for efficiency (60% smaller than JSON)              │
│                                                                                     │
│   BASE ENVELOPE:                                                                   │
│   ┌─────────────────────────────────────────────────────────────────────────────┐  │
│   │  {                                                                          │  │
│   │    "v": 1,                          # Protocol version                      │  │
│   │    "ts": 1706876400000,             # Unix timestamp (ms)                   │  │
│   │    "src": "laptop_001",             # Source device ID                      │  │
│   │    "seq": 12345,                    # Sequence number (for ordering)        │  │
│   │    "type": "sensor.audio",          # Message type                          │  │
│   │    "payload": {...}                 # Type-specific payload                 │  │
│   │  }                                                                          │  │
│   └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
│   EXAMPLE PAYLOADS:                                                                │
│                                                                                     │
│   # Audio chunk                                                                    │
│   {"samples": <binary>, "rate": 16000, "channels": 1}                             │
│                                                                                     │
│   # Speech event                                                                   │
│   {"text": "What time is it?", "confidence": 0.95, "speaker": null}               │
│                                                                                     │
│   # Context update                                                                 │
│   {"location": "workshop", "activity": "working", "people": ["self"]}             │
│                                                                                     │
│   # Action request                                                                 │
│   {"action": "speak", "text": "It's 3:30 PM", "priority": "normal"}               │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## ⚡ Reflex Layer (New in v1.2)

The critique correctly identified that a linear pipeline is too slow for critical commands. The Reflex Layer provides sub-100ms response for safety and immediate actions.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              REFLEX LAYER                                           │
│                        (Bypass Brain for Speed)                                     │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│   NORMAL PATH (2-5 seconds):                                                       │
│   Sensor → STT → Context → Reasoning (LLM) → Action → Output                       │
│                                                                                     │
│   REFLEX PATH (<100ms):                                                            │
│   Sensor → Pattern Match → Action                                                  │
│                                                                                     │
│   ┌─────────────────────────────────────────────────────────────────────────────┐  │
│   │                                                                             │  │
│   │                        ┌──────────────────┐                                 │  │
│   │                        │  REFLEX ENGINE   │                                 │  │
│   │                        │  (Edge Device)   │                                 │  │
│   │                        └────────┬─────────┘                                 │  │
│   │                                 │                                           │  │
│   │              ┌──────────────────┼──────────────────┐                        │  │
│   │              ▼                  ▼                  ▼                        │  │
│   │   ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐           │  │
│   │   │  KEYWORD DETECT  │ │  GESTURE DETECT  │ │  SAFETY TRIGGERS │           │  │
│   │   │  (Tiny ML Model) │ │  (CV Edge Model) │ │  (Rule-Based)    │           │  │
│   │   └────────┬─────────┘ └────────┬─────────┘ └────────┬─────────┘           │  │
│   │            │                    │                    │                      │  │
│   │            ▼                    ▼                    ▼                      │  │
│   │   ┌─────────────────────────────────────────────────────────────────────┐  │  │
│   │   │                      REFLEX RULES                                   │  │  │
│   │   ├─────────────────────────────────────────────────────────────────────┤  │  │
│   │   │                                                                     │  │  │
│   │   │  TRIGGER           │  ACTION              │  LATENCY   │  CONFIRM   │  │  │
│   │   │  ───────────────────────────────────────────────────────────────────│  │  │
│   │   │  "Stop"            │  Halt all motors     │  <50ms     │  Silent    │  │  │
│   │   │  "Cancel"          │  Abort current task  │  <50ms     │  Beep      │  │  │
│   │   │  "Undo"            │  Revert last action  │  <50ms     │  Beep      │  │  │
│   │   │  Hand raised       │  Pause and wait      │  <100ms    │  Beep      │  │  │
│   │   │  Loud noise        │  Record + alert      │  <100ms    │  None      │  │  │
│   │   │  "Hey Velvet"      │  Activate listening  │  <100ms    │  Chime     │  │  │
│   │   │  Motion limit hit  │  Stop motor          │  <10ms     │  Alert     │  │  │
│   │   │  Temperature spike │  Shutdown device     │  <10ms     │  Alert     │  │  │
│   │   │                                                                     │  │  │
│   │   └─────────────────────────────────────────────────────────────────────┘  │  │
│   │                                 │                                           │  │
│   │                                 ▼                                           │  │
│   │   ┌─────────────────────────────────────────────────────────────────────┐  │  │
│   │   │                      DIRECT ACTUATION                               │  │  │
│   │   │                                                                     │  │  │
│   │   │  Action executes BEFORE brain is notified.                          │  │  │
│   │   │  Brain gets informed after the fact for logging/context.            │  │  │
│   │   │                                                                     │  │  │
│   │   └─────────────────────────────────────────────────────────────────────┘  │  │
│   │                                                                             │  │
│   └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### Reflex Implementation

```python
# reflex_engine.py (runs on every compute node)

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional
import zenoh

class ReflexPriority(Enum):
    SAFETY = 0      # Cannot be overridden
    IMMEDIATE = 1   # Near-instant response
    FAST = 2        # Quick but can queue

@dataclass
class ReflexRule:
    name: str
    priority: ReflexPriority
    trigger: Callable[[dict], bool]  # Returns True if triggered
    action: Callable[[], None]       # What to do
    cooldown_ms: int = 500           # Prevent rapid re-triggering
    notify_brain: bool = True        # Inform reasoning engine after

class ReflexEngine:
    def __init__(self, zenoh_session: zenoh.Session):
        self.session = zenoh_session
        self.rules: list[ReflexRule] = []
        self.last_triggered: dict[str, float] = {}
        
        # Subscribe to reflex-relevant topics
        self.session.declare_subscriber(
            "velvet/sensors/audio/*",
            self._on_audio
        )
        self.session.declare_subscriber(
            "velvet/events/wake_word/*",
            self._on_wake_word
        )
        
        # Register default safety reflexes
        self._register_safety_reflexes()
    
    def _register_safety_reflexes(self):
        """Hard-coded safety rules that cannot be disabled."""
        
        self.register(ReflexRule(
            name="emergency_stop",
            priority=ReflexPriority.SAFETY,
            trigger=lambda e: e.get("keyword") in ["stop", "halt", "freeze"],
            action=self._emergency_stop,
            cooldown_ms=0,  # No cooldown for safety
        ))
        
        self.register(ReflexRule(
            name="cancel_task",
            priority=ReflexPriority.IMMEDIATE,
            trigger=lambda e: e.get("keyword") in ["cancel", "abort", "nevermind"],
            action=self._cancel_current,
            cooldown_ms=500,
        ))
        
        self.register(ReflexRule(
            name="wake_word",
            priority=ReflexPriority.FAST,
            trigger=lambda e: e.get("type") == "wake_word",
            action=self._activate_listening,
            cooldown_ms=1000,
        ))
    
    def _emergency_stop(self):
        """Immediately halt all motors and active actions."""
        # Publish to all actuators
        self.session.put("velvet/reflex/commands", {
            "command": "STOP_ALL",
            "timestamp": time.time_ns(),
            "authority": "reflex_safety"
        })
        # Audio feedback
        self.session.put("velvet/actions/beep", {"pattern": "alert"})
    
    def _cancel_current(self):
        """Abort the current reasoning/action chain."""
        self.session.put("velvet/reflex/commands", {
            "command": "CANCEL",
            "timestamp": time.time_ns(),
        })
        self.session.put("velvet/actions/beep", {"pattern": "ack"})
    
    def _activate_listening(self):
        """Wake word detected, start active listening."""
        self.session.put("velvet/context/listening", {"active": True})
        self.session.put("velvet/actions/beep", {"pattern": "chime"})
```

### Keyword Detection Model

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                         REFLEX KEYWORD DETECTION                                    │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│   MODEL: Porcupine (Picovoice) or OpenWakeWord                                     │
│   SIZE: ~5MB                                                                       │
│   LATENCY: <50ms                                                                   │
│   RUNS ON: Any device with microphone                                              │
│                                                                                     │
│   KEYWORDS (hard-coded, always active):                                            │
│   ┌─────────────────────────────────────────────────────────────────────────────┐  │
│   │                                                                             │  │
│   │   SAFETY:     "stop" "halt" "freeze" "emergency"                            │  │
│   │   CONTROL:    "cancel" "undo" "go back" "nevermind"                         │  │
│   │   WAKE:       "hey velvet" "ok velvet"                                      │  │
│   │   CONFIRM:    "yes" "no" "confirm" "deny"                                   │  │
│   │                                                                             │  │
│   └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
│   These bypass Whisper/LLM entirely. They're detected by a tiny on-device         │
│   model that runs on raw audio, not transcribed text.                             │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Data Flow (Simplified)

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           SIMPLIFIED DATA FLOW                                      │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│   ┌─────────────┐                                                                  │
│   │   SENSOR    │                                                                  │
│   │  (Phone,    │                                                                  │
│   │   USB Mic)  │                                                                  │
│   └──────┬──────┘                                                                  │
│          │                                                                         │
│          ▼                                                                         │
│   ┌──────────────────────────────────────────────────────────────┐                │
│   │                    EDGE PROCESSING                           │                │
│   │                    (On Laptop)                               │                │
│   │                                                              │                │
│   │   ┌────────────────┐    ┌────────────────┐                  │                │
│   │   │ REFLEX ENGINE  │    │ STREAM PROC    │                  │                │
│   │   │ (Keyword Det)  │    │ (VAD, Face)    │                  │                │
│   │   └───────┬────────┘    └───────┬────────┘                  │                │
│   │           │                     │                            │                │
│   │           ▼                     ▼                            │                │
│   │   REFLEX MATCH?           PROCESS & EMIT                    │                │
│   │   ├─YES→ IMMEDIATE ACTION  velvet/events/*                  │                │
│   │   └─NO → Continue                                            │                │
│   │                                                              │                │
│   └──────────────────────────────────────────────────────────────┘                │
│          │                                                                         │
│          ▼                                                                         │
│   ┌──────────────────────────────────────────────────────────────┐                │
│   │                    VELVET DAEMON                             │                │
│   │                    (Single Process)                          │                │
│   │                                                              │                │
│   │   ┌────────────────────────────────────────────────────────┐│                │
│   │   │                   CONTEXT MANAGER                      ││                │
│   │   │  • Unified context (not multiple instances)            ││                │
│   │   │  • Updates current state from events                   ││                │
│   │   │  • Manages active resource capabilities                ││                │
│   │   └────────────────────────────────────────────────────────┘│                │
│   │                          │                                   │                │
│   │                          ▼                                   │                │
│   │   ┌────────────────────────────────────────────────────────┐│                │
│   │   │                   REASONING ENGINE                     ││                │
│   │   │  • LLM inference (via gRPC to GPU box)                 ││                │
│   │   │  • Decides what action to take                         ││                │
│   │   │  • Manages conversation state                          ││                │
│   │   └────────────────────────────────────────────────────────┘│                │
│   │                          │                                   │                │
│   │                          ▼                                   │                │
│   │   ┌────────────────────────────────────────────────────────┐│                │
│   │   │                   ACTION ENGINE                        ││                │
│   │   │  • Routes outputs to correct device                    ││                │
│   │   │  • TTS, display, tool execution                        ││                │
│   │   └────────────────────────────────────────────────────────┘│                │
│   │                                                              │                │
│   └──────────────────────────────────────────────────────────────┘                │
│          │                                                                         │
│          ▼                                                                         │
│   ┌─────────────┐                                                                  │
│   │   OUTPUT    │                                                                  │
│   │  (Speaker,  │                                                                  │
│   │   Display)  │                                                                  │
│   └─────────────┘                                                                  │
│                                                                                     │
│   KEY CHANGE: One daemon, one process, clear flow.                                │
│   No microservices, no distributed state to synchronize.                          │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔒 Security (Unchanged)

Security requirements remain the same as v1.1:

- **TLS 1.3** for all Zenoh connections
- **Pre-shared keys** for device enrollment
- **WireGuard VPN** for remote access
- **No public exposure** of any services

---

## 📦 Implementation Roadmap

### Phase 1 (Prototype)

| Component | Technology | Notes |
|-----------|------------|-------|
| Primary Protocol | Zenoh (Rust) | Or Python `zenoh-python` for speed |
| Phone Bridge | WebSocket | Simple Android app → WS → Zenoh bridge |
| Message Format | MessagePack | Fast, compact |
| Reflex Keywords | OpenWakeWord | Open source, customizable |

### Phase 2 (Production)

| Component | Technology | Notes |
|-----------|------------|-------|
| Primary Protocol | Zenoh | Same, battle-tested by now |
| Wearable Sensors | ESP32 + Zenoh-Pico | Native Zenoh, no bridge |
| Reflex Keywords | Porcupine (Picovoice) | More accurate |

---

## 🚀 Quick Start

```bash
# Terminal 1: Start Zenoh router (optional, for complex topologies)
zenohd

# Terminal 2: Start Velvet daemon
python velvet_daemon.py

# Terminal 3: Start phone bridge (WebSocket to Zenoh)
python ws_bridge.py --port 8080

# On Android: Open app, connect to ws://laptop-ip:8080
```

---

*v1.2 simplifies the architecture significantly. One protocol (Zenoh), one daemon per node, reflexes for speed.*
