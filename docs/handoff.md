# Velvet Nadir Handoff Document

> Current state of the system after Sprint 11, for the next agent or session.

**Last Updated:** March 25, 2026

---

## 1. System State

### Sprint 10: COMPLETE ✅ (128 tests passing)

**Phase 1: Hive Mind Memory** — Jing (PowerMem integration), Tartarus (cold store), MeshMemorySync, PrivacyGuard  
**Phase 2: Xi Background Tasks** — Xi scheduler, Fuxi (consolidation), Agni (purification)  
**Phase 3: Trust + Agents + Affinity** — TrustEngine, AgentOrchestrator, ModelAffinityTracker, Inari, DeviceWatchdog  
**Phase 4: Saraswati Skill Learning** — Shruti (observe) → Smriti (codify) → Vidya (validate + deploy)  

### Sprint 11: CLEANUP COMPLETE ✅
Standardized API exports, sandboxed risky device scripts, audited imports, and added high-perf backend support via Polymath.
- **100% Test Success** (171/171 regression tests passing) confirming all Sprint 11 features.
- **`__all__` exports** added to 19 modules for cleaner Public API.
- **`DeviceScript` Sandbox** added (AST validation + restricted run).
- **Standardized Error Handling** (new `errors.py`) across all adapters.
- **Polymath Integration** in `LLMService` for optimized hardware loading.
- **TOML Config Support** (`velvet.toml`) for easier deployment.
- **Skill Approval Queue** in `Saraswati` for learned skills.

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
    ┌──────────┬────────┬───────┼──────────┬──────────────┐
    ▼          ▼        ▼       ▼          ▼              ▼
 Fuxi(3)   Agni(5)  Inari(7) Watchdog(8) Saraswati(9)  [future]
```

### Key Components

| Component | Module | Purpose |
|-----------|--------|---------|
| Yi | `shen/yi.py` | Intent routing (reflex vs. reasoning) |
| Po | `shen/po.py` | Fast reflexes + learned patterns + vision |
| Hun | `shen/hun.py` | Deep reasoning via LLM |
| Jing | `shen/jing.py` | Tiered memory (Aether/Mnemosyne/Tartarus) |
| Xi | `shen/xi.py` | Background task scheduler |
| Polymath | `shen/polymath.py` | Hardware intel + config builder |
| Gateway | `gateway.py` | Central orchestrator + Xi lifecycle + tool parsing |
| TrustEngine | `shen/trust.py` | Device trust with hot cache + confidence EMA |
| PrivacyGuard | `privacy.py` | Dual perimeter (mesh/internet + trusted/untrusted) |
| Errors | `errors.py` | Centralized Velvet Error hierarchy |

### Communication

- **Zenoh** peer-to-peer fabric (no broker)
- Topics: `audio/wake`, `audio/transcript`, `skill/request`, `mesh/device/*`, etc.
- MeshMemorySync replicates writes across trusted peers

### Memory Hierarchy

| Tier | Name | Storage | Access |
|------|------|---------|--------|
| Hot | Aether | PowerMem RAM | Instant |
| Warm | Mnemosyne | PowerMem vector | ~10ms |
| Cold | Tartarus | SQLite FTS5 | ~50ms |

---

## 3. File Structure (42 source files)

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
└── shen/                             # Cognitive (15 modules)
    ├── yi.py, po.py, hun.py, jing.py
    ├── polymath.py, tartarus.py, mesh_memory.py
    ├── xi.py, fuxi.py, agni.py
    ├── trust.py, affinity.py
    ├── inari.py, device_watchdog.py, saraswati.py
```

---

## 4. Next Steps: Post-Cleanup

### Post-Cleanup

- Train custom "Hey Velvet" wake word
- Finalize mTLS mesh security layer
- Zenoh security (PSK/mTLS)
- End-to-end live integration test

---

## 5. Vision Docs vs. Reality

| Vision Feature | Status | Implementation |
|---------------|--------|----------------|
| 3-tier memory | ✅ | Aether/Mnemosyne/Tartarus via Jing |
| Memory consolidation | ✅ | Xi + Fuxi + Agni BreathTasks |
| Skill hot-plug | ✅ | Saraswati → Vidya → `~/.velvet/skills/` |
| Device mesh + heartbeats | ✅ | `devices.py` + `fabric.py` |
| Privacy model | ⚠️ | 2-level (trusted/untrusted) vs. vision's 4-level |
| Model routing | ✅ | MeshLLMAdapter + ModelAffinityTracker |
| Display routing | ❌ | TTS-only output |
| People recognition | ❌ | No face/voice embedding |
| Spatial awareness | ❌ | No geofence triggers |
| Context merging | ❌ | No location-based merge |

---

## 6. Running the System

```bash
# Tests
cd sw/velvet
python -m pytest tests/ -v

# Sprint 10 tests specifically
python -m pytest tests/test_phase1_memory.py tests/test_phase2_xi.py \
    tests/test_phase3_trust.py tests/test_phase4_saraswati.py tests/test_po_reflexes.py -v

# Run system (requires Ollama)
python -m velvet.main
```

---

*The hardest part — the cognitive architecture — is done. What remains is security, polish, and hardware deployment.*
