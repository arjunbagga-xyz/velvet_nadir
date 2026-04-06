# 🧠 Context & Memory Management v1.2

> Rethinking context for real-world use with AI-agent business operations

---

## 📋 Revision Notes

**v1.2 Changes (2026-02-03):**
- Dropped complex context "merging" with CRDTs
- Introduced **Parallel Context Tracks** instead of instance merging
- Added **Active Context Selection** for tracking which contexts user is engaged with
- Added AI Agent autonomy levels for business operation support
- Clarified phone role as sensor-only (no context hosting)

---

## 🎯 Design Philosophy Shift

### v1.1 vs v1.2 Approach

| Aspect | v1.1 | v1.2 | Rationale |
|--------|------|------|-----------|
| **Context Model** | Multiple instances that merge | Single stream with parallel tracks | Merging is complex, tracks are simple |
| **State Location** | Distributed across devices | Centralized on primary brain | Phone can't reliably host state |
| **Context Types** | Personal + Spatial + Virtual | Personal (always) + Domain Tracks | Cleaner mental model |
| **AI Agents** | Not addressed | First-class citizens with own tracks | Business via AI requires this |

---

## 🌍 Revised Context Model

### Single Context Stream with Parallel Tracks

Instead of "merging" separate context instances, we have:
1. **One unified context stream** that YOU are always part of
2. **Parallel domain tracks** that run independently
3. **Active engagement indicators** showing which tracks you're currently involved in

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                         PARALLEL CONTEXT TRACKS                                     │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│   ╔═══════════════════════════════════════════════════════════════════════════════╗│
│   ║                      YOUR PERSONAL STREAM (Always Active)                     ║│
│   ║                                                                               ║│
│   ║   Location: Workshop │ Activity: Designing │ Next: Vendor call @ 5pm         ║│
│   ║   Energy: High │ Focus: Deep │ Companions: Alone                              ║│
│   ║                                                                               ║│
│   ╚═══════════════════════════════════════════════════════════════════════════════╝│
│              │                                                                      │
│              │  YOU ARE ENGAGED WITH:                                               │
│              │                                                                      │
│   ┌──────────┴──────────────────────────────────────────────────────────────────┐  │
│   │                                                                             │  │
│   │   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐            │  │
│   │   │  WORKSHOP       │  │  PROJECT:       │  │  BUSINESS       │            │  │
│   │   │  TRACK          │  │  DRONE-X        │  │  TRACK          │            │  │
│   │   │  ★ ACTIVE       │  │  ★ ACTIVE       │  │  ○ BACKGROUND   │            │  │
│   │   ├─────────────────┤  ├─────────────────┤  ├─────────────────┤            │  │
│   │   │ Project: Drone  │  │ Stage: Motor    │  │ Pending: 3 items│            │  │
│   │   │ Tools: CAD open │  │ Blockers: none  │  │ Agents: 2 active│            │  │
│   │   │ Last: Mount dwg │  │ Next: Testing   │  │ Revenue: $XXX   │            │  │
│   │   └─────────────────┘  └─────────────────┘  └─────────────────┘            │  │
│   │                                                                             │  │
│   │   Track states are independent. No merging needed.                         │  │
│   │   Your engagement level determines what gets your attention.               │  │
│   │                                                                             │  │
│   └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
│   OTHER TRACKS (Not engaged, running independently):                              │
│   ┌─────────────────────────────────────────────────────────────────────────────┐  │
│   │                                                                             │  │
│   │   HOME TRACK           VEHICLE TRACK         PROJECT: WEBSITE              │  │
│   │   ○ Monitoring         ○ Parked              ○ Paused                       │  │
│   │   • All secure         • Battery: OK         • Waiting on client           │  │
│   │   • Temp: 23°C         • Location: Shop      • Last: 3 days ago            │  │
│   │                                                                             │  │
│   └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### Track Types

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              TRACK TYPE DEFINITIONS                                 │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│   1. PERSONAL STREAM (Singleton, always active)                                    │
│      ─────────────────────────────────────────                                     │
│      • Your physical presence, state, schedule                                     │
│      • Cannot be paused or backgrounded                                            │
│      • All other tracks relate to this                                             │
│                                                                                     │
│   2. SPATIAL TRACKS (Location-bound)                                               │
│      ─────────────────────────────────────────                                     │
│      • Workshop, Home, Office, Vehicle, etc.                                       │
│      • Activate when you enter, deactivate when you leave                          │
│      • Track state persists even when you're not there                             │
│      • Can monitor even when not active (e.g., home security)                      │
│                                                                                     │
│   3. PROJECT TRACKS (Task-bound)                                                   │
│      ─────────────────────────────────────────                                     │
│      • One track per active project                                                │
│      • Contains: goals, tasks, blockers, artifacts, people                         │
│      • Can be active or paused                                                     │
│      • Multiple can be active simultaneously                                       │
│                                                                                     │
│   4. BUSINESS TRACK (Domain-bound)                                                 │
│      ─────────────────────────────────────────                                     │
│      • Your business operations                                                    │
│      • AI agents operate here autonomously                                         │
│      • Escalates to you only when needed                                           │
│      • Contains: clients, finances, agents, tasks                                  │
│                                                                                     │
│   5. AGENT TRACKS (Autonomous)                                                     │
│      ─────────────────────────────────────────                                     │
│      • Each AI agent has its own sub-track                                         │
│      • Reports to Business Track                                                   │
│      • Has defined autonomy boundaries                                             │
│      • Can request your attention                                                  │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 👤 Active Engagement System

Instead of "merging" contexts, we track your **engagement level** with each track:

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                         ENGAGEMENT LEVELS                                           │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│   ★★★ FOCUSED                                                                      │
│       • You are actively working in this track                                     │
│       • Full attention, proactive assistance enabled                               │
│       • Example: Working on CAD design in workshop                                 │
│       • Only one track can be FOCUSED at a time                                    │
│                                                                                     │
│   ★★○ ACTIVE                                                                       │
│       • Track is loaded and relevant                                               │
│       • Updates shown, but not interrupting focus                                  │
│       • Example: Project track while in workshop                                   │
│       • Multiple tracks can be ACTIVE                                              │
│                                                                                     │
│   ★○○ MONITORING                                                                   │
│       • Track runs in background                                                   │
│       • Only critical alerts surface                                               │
│       • Example: Home security while at work                                       │
│                                                                                     │
│   ○○○ PAUSED                                                                       │
│       • Track state preserved but not running                                      │
│       • No updates or alerts                                                       │
│       • Example: Paused project                                                    │
│                                                                                     │
│   ENGAGEMENT TRANSITIONS:                                                          │
│   ┌─────────────────────────────────────────────────────────────────────────────┐  │
│   │                                                                             │  │
│   │   Transition          │ How it happens                                      │  │
│   │   ────────────────────────────────────────────────────────────────────────  │  │
│   │   PAUSED → MONITORING │ You say "Keep an eye on X"                          │  │
│   │   MONITORING → ACTIVE │ You enter relevant location OR say "Open X"         │  │
│   │   ACTIVE → FOCUSED    │ You say "Focus on X" OR start working on it         │  │
│   │   FOCUSED → ACTIVE    │ Automatic when you switch focus                     │  │
│   │   ACTIVE → MONITORING │ You leave location OR say "Background X"            │  │
│   │   ANY → PAUSED        │ You say "Pause X" OR project completes              │  │
│   │                                                                             │  │
│   └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🤖 AI Agent Operations

Your goal is to run a business via AI agents. This requires a specialized track system:

### Agent Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                         AI AGENT SYSTEM                                             │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│   ┌─────────────────────────────────────────────────────────────────────────────┐  │
│   │                       BUSINESS TRACK                                        │  │
│   │                    (Your business overview)                                 │  │
│   ├─────────────────────────────────────────────────────────────────────────────┤  │
│   │                                                                             │  │
│   │   STATUS: 2 Active Agents │ 3 Pending Decisions │ $XXX Revenue Today        │  │
│   │                                                                             │  │
│   │   ┌─────────────────────────────────────────────────────────────────────┐  │  │
│   │   │                    AGENT SUB-TRACKS                                 │  │  │
│   │   ├─────────────────────────────────────────────────────────────────────┤  │  │
│   │   │                                                                     │  │  │
│   │   │   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐    │  │  │
│   │   │   │  SALES AGENT    │  │  SUPPORT AGENT  │  │  OPS AGENT      │    │  │  │
│   │   │   │  "Alex"         │  │  "Jamie"        │  │  "Morgan"       │    │  │  │
│   │   │   ├─────────────────┤  ├─────────────────┤  ├─────────────────┤    │  │  │
│   │   │   │ Autonomy: HIGH  │  │ Autonomy: MED   │  │ Autonomy: LOW   │    │  │  │
│   │   │   │ • Email leads   │  │ • Answer tickets│  │ • Schedule tasks│    │  │  │
│   │   │   │ • Send quotes   │  │ • Basic refunds │  │ • Order supplies│    │  │  │
│   │   │   │ • Follow up     │  │ • Escalate hard │  │ • Track shipment│    │  │  │
│   │   │   │                 │  │   cases         │  │                 │    │  │  │
│   │   │   │ PENDING: 1      │  │ PENDING: 0      │  │ PENDING: 2      │    │  │  │
│   │   │   │ (Quote > $5k)   │  │                 │  │ (New vendor?)   │    │  │  │
│   │   │   └─────────────────┘  └─────────────────┘  └─────────────────┘    │  │  │
│   │   │                                                                     │  │  │
│   │   └─────────────────────────────────────────────────────────────────────┘  │  │
│   │                                                                             │  │
│   │   ESCALATION QUEUE (Needs you):                                            │  │
│   │   1. [Alex] Quote request from BigCorp: $12,000 - Approve?                 │  │
│   │   2. [Morgan] New vendor "FastParts" - cheaper but unvetted. Switch?       │  │
│   │   3. [Morgan] Inventory low on Widget-X. Reorder 100 units?                │  │
│   │                                                                             │  │
│   └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### Agent Autonomy Levels

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                         AGENT AUTONOMY FRAMEWORK                                    │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│   LEVEL 0: OBSERVER                                                                │
│   ─────────────────────                                                            │
│   • Can only read and report                                                       │
│   • No actions without explicit approval                                           │
│   • Use case: New agent, learning phase                                            │
│                                                                                     │
│   LEVEL 1: SUGGESTIVE                                                              │
│   ─────────────────────                                                            │
│   • Can draft responses, plans, actions                                            │
│   • Must wait for approval before executing                                        │
│   • Use case: High-stakes decisions                                                │
│                                                                                     │
│   LEVEL 2: BOUNDED                                                                 │
│   ─────────────────────                                                            │
│   • Can act within defined boundaries                                              │
│   • Escalates when outside boundaries                                              │
│   • Boundaries: $ limits, action types, client tiers                               │
│   • Use case: Most operational agents                                              │
│                                                                                     │
│   LEVEL 3: AUTONOMOUS                                                              │
│   ─────────────────────                                                            │
│   • Can act freely within domain                                                   │
│   • Reports after the fact                                                         │
│   • Still respects hard limits (legal, safety)                                     │
│   • Use case: Trusted, mature agents                                               │
│                                                                                     │
│   BOUNDARY EXAMPLES:                                                               │
│   ┌─────────────────────────────────────────────────────────────────────────────┐  │
│   │                                                                             │  │
│   │   Agent: Sales "Alex"                                                       │  │
│   │   Level: 2 (BOUNDED)                                                        │  │
│   │                                                                             │  │
│   │   ALLOWED AUTONOMOUSLY:                                                     │  │
│   │   • Send email to leads                                                     │  │
│   │   • Send quotes < $5,000                                                    │  │
│   │   • Schedule follow-ups                                                     │  │
│   │   • Answer product questions                                                │  │
│   │                                                                             │  │
│   │   REQUIRES APPROVAL:                                                        │  │
│   │   • Quotes >= $5,000                                                        │  │
│   │   • Custom pricing                                                          │  │
│   │   • Contract modifications                                                  │  │
│   │   • Refunds > $500                                                          │  │
│   │                                                                             │  │
│   │   NEVER ALLOWED:                                                            │  │
│   │   • Legal commitments                                                       │  │
│   │   • Bank account access                                                     │  │
│   │   • Personnel decisions                                                     │  │
│   │                                                                             │  │
│   └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### Agent-Owner Communication

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                      AGENT ESCALATION SYSTEM                                        │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│   When an agent needs your attention:                                              │
│                                                                                     │
│   1. ASYNC QUEUE (Default)                                                         │
│      • Agent adds to escalation queue                                              │
│      • You review when convenient                                                  │
│      • Queue sorted by priority + age                                              │
│                                                                                     │
│   2. NOTIFICATION (Urgent but not immediate)                                       │
│      • Agent triggers a notification                                               │
│      • You see it in UI / hear a brief alert                                       │
│      • Can respond now or queue for later                                          │
│                                                                                     │
│   3. INTERRUPT (Time-sensitive)                                                    │
│      • Agent interrupts your current focus                                         │
│      • Requires immediate decision                                                 │
│      • Only for true deadlines                                                     │
│                                                                                     │
│   INTERRUPT CRITERIA:                                                              │
│   ┌─────────────────────────────────────────────────────────────────────────────┐  │
│   │                                                                             │  │
│   │   Interrupt if:                                                             │  │
│   │   • Decision deadline < 30 minutes                                          │  │
│   │   • Financial impact > $X (configurable)                                    │  │
│   │   • Customer tier = VIP                                                     │  │
│   │   • Agent explicitly says "urgent"                                          │  │
│   │                                                                             │  │
│   │   Never interrupt if:                                                       │  │
│   │   • You're in a meeting (calendar-aware)                                    │  │
│   │   • You're in focus mode                                                    │  │
│   │   • It's sleep hours                                                        │  │
│   │   • Unless actual emergency                                                 │  │
│   │                                                                             │  │
│   └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
│   RESPONSE METHODS:                                                                │
│   • Voice: "Approve the BigCorp quote"                                             │
│   • Quick action: Tap approve/deny on notification                                 │
│   • Detailed: Open business track and review                                       │
│   • Delegate: "Let Alex decide"                                                    │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📊 Unified Context State

### Schema

```yaml
# context_state.yaml

# Your personal stream (always present)
personal:
  id: "you"
  timestamp: "2026-02-03T10:30:00Z"
  
  location:
    current: "workshop"
    confidence: 0.98
    coordinates: [28.6139, 77.2090]
    indoor_zone: "main_bench"
  
  activity:
    type: "designing"
    subtype: "cad_work"
    focus_level: "deep"
    started: "2026-02-03T09:15:00Z"
  
  schedule:
    next_event:
      title: "Vendor call"
      time: "2026-02-03T17:00:00Z"
      eta_minutes: 390
    free_until: "2026-02-03T17:00:00Z"
  
  companions: []  # Alone
  
  state:
    energy: "high"
    mood: "focused"  # inferred from activity pattern

# Track engagement
tracks:
  workshop:
    type: "spatial"
    engagement: "focused"  # ★★★
    state:
      active_project: "drone-x"
      tools_in_use: ["fusion360", "oscilloscope"]
      recent_actions:
        - "Modified motor mount design"
        - "Ran thermal simulation"
  
  drone-x:
    type: "project"
    engagement: "active"  # ★★○
    state:
      stage: "prototyping"
      completion: 0.45
      current_task: "Motor mount finalization"
      blockers: []
      next_tasks:
        - "3D print mount v2"
        - "Wiring harness"
  
  business:
    type: "business"
    engagement: "monitoring"  # ★○○
    state:
      agents_active: 2
      pending_decisions: 3
      daily_revenue: 1250.00
      escalation_queue:
        - agent: "alex"
          subject: "BigCorp quote: $12,000"
          priority: "high"
          deadline: "2026-02-03T15:00:00Z"
  
  home:
    type: "spatial"
    engagement: "monitoring"  # ★○○
    state:
      status: "secure"
      occupants: ["wife"]
      temperature: 23
      alerts: []
```

### State Transitions

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                         CONTEXT STATE MACHINE                                       │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│   TRIGGERS FOR STATE CHANGE:                                                       │
│                                                                                     │
│   LOCATION CHANGE:                                                                 │
│   ├─ Enter Workshop → Workshop track: monitoring → focused                         │
│   ├─ Leave Workshop → Workshop track: focused → monitoring                         │
│   ├                  → Last project track: active → active (persists)              │
│   └─ Enter Home     → Home track: monitoring → active                              │
│                                                                                     │
│   VOICE COMMAND:                                                                   │
│   ├─ "Focus on Drone project" → drone-x: active → focused                          │
│   ├─ "Background the business" → business: active → monitoring                     │
│   ├─ "Pause website project" → website: any → paused                               │
│   └─ "What's pending?" → Read escalation queue from all tracks                     │
│                                                                                     │
│   AUTOMATIC:                                                                       │
│   ├─ Started using Fusion 360 → Infer CAD work, update activity                    │
│   ├─ Agent requests attention → Add to escalation queue                            │
│   ├─ Calendar event starts → Adjust schedule, maybe notify                         │
│   └─ Long idle period → Reduce focus level                                         │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 💾 Memory Architecture (Simplified)

### Storage Strategy

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                         MEMORY TIERS (v1.2)                                         │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│   TIER 1: WORKING MEMORY (RAM)                                                     │
│   ──────────────────────────────                                                   │
│   • Current context state (above schema)                                           │
│   • Active conversation (last 20 turns)                                            │
│   • Recent sensor events (5 minute buffer)                                         │
│   • Agent escalation queue                                                         │
│   Size: ~100MB                                                                     │
│   Location: Primary compute node                                                   │
│                                                                                     │
│   TIER 2: SESSION MEMORY (SQLite)                                                  │
│   ──────────────────────────────                                                   │
│   • Today's events (summarized)                                                    │
│   • Decisions made today                                                           │
│   • Agent actions log                                                              │
│   • Temporary notes                                                                │
│   Retention: 7 days, then consolidate                                              │
│   Size: ~1GB                                                                       │
│   Location: Primary compute node                                                   │
│                                                                                     │
│   TIER 3: LONG-TERM MEMORY (ChromaDB + SQLite)                                     │
│   ──────────────────────────────                                                   │
│   • Knowledge graph (people, places, projects)                                     │
│   • Preference rules                                                               │
│   • Correction history                                                             │
│   • Important conversations (embedded)                                             │
│   • Business records                                                               │
│   Retention: Forever                                                               │
│   Size: 10GB+                                                                      │
│   Location: Primary compute node + backup                                          │
│                                                                                     │
│   KEY SIMPLIFICATION:                                                              │
│   Phone stores NOTHING. All state is on stationary compute.                        │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🧭 Spatial Awareness (Simplified)

### Location Detection

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                         LOCATION DETECTION                                          │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│   PRIMARY: WiFi Network + IP                                                       │
│   ─────────────────────────────                                                    │
│   • Connected to "Workshop_Net" → You're in workshop                               │
│   • Simple, reliable, no fancy tech                                                │
│                                                                                     │
│   SECONDARY: BT Beacons (optional)                                                 │
│   ─────────────────────────────                                                    │
│   • For indoor zone detection (which room)                                         │
│   • Cheap ESP32 devices can broadcast BLE beacons                                  │
│                                                                                     │
│   TERTIARY: GPS (from phone, when available)                                       │
│   ─────────────────────────────                                                    │
│   • For outdoors / unknown locations                                               │
│   • Only used when WiFi doesn't match known places                                 │
│                                                                                     │
│   PLACE DEFINITIONS:                                                               │
│   ┌─────────────────────────────────────────────────────────────────────────────┐  │
│   │                                                                             │  │
│   │   places:                                                                   │  │
│   │     workshop:                                                               │  │
│   │       wifi_networks: ["Workshop_Net"]                                       │  │
│   │       on_enter:                                                             │  │
│   │         - activate_track: "workshop"                                        │  │
│   │         - say: "Welcome back. Pick up where you left off?"                  │  │
│   │       on_exit:                                                              │  │
│   │         - save_state: true                                                  │  │
│   │         - say: "Leaving workshop. Anything to note?"                        │  │
│   │                                                                             │  │
│   │     home:                                                                   │  │
│   │       wifi_networks: ["Home_5G", "Home_2.4G"]                               │  │
│   │       on_enter:                                                             │  │
│   │         - activate_track: "home"                                            │  │
│   │       on_exit:                                                              │  │
│   │         - background_track: "home"                                          │  │
│   │         - ensure: "security_mode: away"                                     │  │
│   │                                                                             │  │
│   └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📝 Learning from Corrections

### Correction Types

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                         CORRECTION LEARNING                                         │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│   FACTUAL CORRECTIONS                                                              │
│   ───────────────────────                                                          │
│   User: "No, Sarah works at TechCorp, not DataCo"                                  │
│   Action: Update knowledge graph immediately                                       │
│   Confidence: 1.0 (explicit correction)                                            │
│                                                                                     │
│   PREFERENCE CORRECTIONS                                                           │
│   ───────────────────────                                                          │
│   User: "Don't interrupt me when I'm in deep focus"                                │
│   Action: Add rule to preference model                                             │
│   Scope: Global (applies everywhere)                                               │
│                                                                                     │
│   AGENT TRAINING                                                                   │
│   ───────────────────────                                                          │
│   User: "Alex, don't offer discounts to new customers"                             │
│   Action: Add to Alex's boundary rules                                             │
│   Scope: Agent-specific                                                            │
│                                                                                     │
│   OVERRIDE ANALYSIS                                                                │
│   ───────────────────────                                                          │
│   When user says "No" or "Cancel":                                                 │
│   • Log what system proposed                                                       │
│   • Log what user did instead                                                      │
│   • After 3 similar overrides, ask: "Should I always do X instead of Y?"           │
│                                                                                     │
│   CORRECTION STORAGE:                                                              │
│   ┌─────────────────────────────────────────────────────────────────────────────┐  │
│   │                                                                             │  │
│   │   corrections:                                                              │  │
│   │     - timestamp: "2026-02-03T10:30:00Z"                                     │  │
│   │       type: "preference"                                                    │  │
│   │       context: {location: "workshop", activity: "deep_focus"}               │  │
│   │       system_did: "Announced newsletter email"                              │  │
│   │       user_said: "Don't announce newsletters when I'm focused"              │  │
│   │       learned:                                                              │  │
│   │         rule: "IF focus_level = deep AND email.type = newsletter THEN mute"│  │
│   │         confidence: 0.9                                                     │  │
│   │       applied: true                                                         │  │
│   │                                                                             │  │
│   └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🎯 Summary: v1.1 → v1.2 Changes

| Aspect | v1.1 | v1.2 |
|--------|------|------|
| Context model | Multiple instances with CRDT merging | Single stream + parallel tracks |
| User engagement | Implicit (location-based) | Explicit engagement levels |
| AI Agents | Not designed | First-class with autonomy framework |
| State location | Distributed | Centralized on primary brain |
| Phone role | Possible state host | Sensor source only |
| Complexity | High (academic correctness) | Lower (practical implementation) |

---

*v1.2 trades "elegance" for practicality. One brain, one truth, parallel tracks for independence.*
