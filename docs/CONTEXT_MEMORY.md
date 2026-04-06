# 🧠 Context & Memory Architecture

> Technical details for how Velvet Nadir perceives, comprehends, and remembers the context of the world.

---

## 🎭 Context Management System

The **Context Management** module acts as the "working memory pipeline" that the `Yi` (Intent Router) constantly reads. 
When user audio/visual streams are converted to state, it lands in five parallel **Context Tracks**.

### 1. The 5 Context Tracks (`context.py`)

- **Personal:** Information about the user. Intent, health, mood, identity.
- **Workshop:** Technical data. Active terminal traces, coding files, debugging logs.
- **Business:** Meetings, schedules, company intelligence, macro relationships.
- **Environmental:** Unstructured sensor data. The room brightness, the weather, mesh device locations.
- **Transient:** Highly ephemeral data. A verification code, a quick calculation.

### 2. Context Engagement Levels

The Engine operates on four engagement states:
1. `PASSIVE`: Listening for Wake Word.
2. `INFORMATIVE`: Context gathers quietly.
3. `SUGGESTIVE`: Context provides proactive notifications through UI.
4. `AUTONOMOUS`: Context takes independent action without waiting for prompts.

---

## 📚 Tiered Cognitive Memory (Jing)

Velvet implements a structured three-tier thermal memory storage architecture collectively managed by **Jing** and backed by the completely offline `PowerMem` package.

### `Aether` (Hot Memory)
- **Role:** Instantaneous session recall and rapid context awareness.
- **Storage medium:** RAM Cache (managed by PowerMem).
- **TTL (Time to Live):** Measured in hours / single conversational session.
- **Examples:** "What did I just say?", "Keep holding that lock."

### `Mnemosyne` (Warm Memory)
- **Role:** Semantic search over recent historical records.
- **Storage medium:** Local Vector Database (SentenceTransformers embedding layer via Polymath).
- **TTL:** Measured in weeks / months.
- **Examples:** "Did we discuss the API design last week?", "What was the name of the guy from the coffee shop?"

### `Tartarus` (Cold Storage)
- **Role:** Archival, exact-match keyword search, deep history.
- **Storage medium:** SQLite FTS5 (Full Text Search).
- **TTL:** Infinite.
- **Examples:** Exact logging of a configuration string written a year ago, raw transcript archiving.

---

## 🧹 Memory Consolidation & The Xi Scheduler

Memory doesn't move through tiers automatically. Data needs to be processed, synthesized, reduced, and embedded. 
This is handled by the **Xi Scheduler** running background cognitve **BreathTasks** while Velvet Nadir is idle.

### `Fuxi` (The Embedder)
- **Priority:** 3
- Reads the raw transcripts appended to the `Xi` Journal by `Yi` during active engagement.
- Batches interactions and generates dense vector embeddings via Polymath to store in **Mnemosyne**.
- Also actively searches for repetitive structural patterns in how the user speaks and teaches **Po** new `LearnedReflexes` so future duplicate queries bypass the LLM entirely.

### `Agni` (The Purifier)
- **Priority:** 5
- The Garbage Collector for the mind.
- **Cold Archiving:** Moves stale, unused nodes from `Aether` to `Tartarus`.
- **Hot Promotion:** If an older memory in `Tartarus` is queried frequently, `Agni` will promote it to `Aether`.
- **Knowledge Graph Assembly:** Merges duplicate entities in the graph (e.g., linking "Dave" to "David").

---

## 🪞 Mesh Memory Sync (The Hive Mind)
Because Velvet Nadir runs on a distributed Zenoh architecture across multiple endpoints, Memory cannot live purely on a single edge node.

When `Jing` updates a vector in Mnemosyne, it securely fires a payload to the `mesh/memory/sync` Zenoh topic. Other trusted nodes receive this payload and independently merge the specific memory. Thus, what a pair of smart glasses sees is "remembered" by the Desktop GPU when the user sits down.

---

*Because of this multi-tiered architecture with offline background scheduling, Velvet Nadir achieves an almost biological equivalent to human memory sleep consolidation.*
