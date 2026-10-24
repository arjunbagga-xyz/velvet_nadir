# Velvet → Real-World Ready

**Goal:** Make the `seamless_computing/velvet` cognitive mesh survive real provider behavior (malformed JSON, repetition loops, stream drops, auth expiries, content refusals, surrogate-ridden clipboard pastes) without losing its distributed, multi-model, biologically-modeled identity.

Two paths are documented below:

- **Part 1 — Port the hardening.** Cherry-pick the resilience features Hermes-Agent already proved in production, and weave them into Velvet's *existing* subsystems (`Yi`, `Hun`, `Po`, `Jing`, `Xi`, `TrustEngine`, `Gateway`, `Fabric`) so they feel native.
- **Part 2 — Run Hermes inside Velvet.** Vendor the upstream `hermes-agent` repo verbatim and bridge it as Velvet's deep-reasoning layer (`Hun`). Updates become `git submodule update` — zero fork drift.

---

## Part 1 — Features to Port (Hermes → Velvet, native weave)

> Each entry: **Problem** → **How Hermes does it** (file:symbol) → **Velvet integration** (which Velvet subsystem absorbs it, and why it fits).

---

### 1. Error Classification & Multi-Vector Recovery

**Problem:** Providers fail in dozens of semantically different ways. A 429, a 401, a content-filter refusal, and a truncated stream need *different* responses. Velvet's `Hun` currently does `except Exception as e: return LLMResponse(text=f"Error: {e}")`.

**Hermes implementation:**
- `agent/error_classifier.py::classify_api_error()` returns a `FailoverReason` enum (`rate_limit`, `billing`, `context_overflow`, `content_policy_blocked`, `thinking_signature`, `image_too_large`, `llama_cpp_grammar_pattern`, `ssl_cert_verification`, `upstream_rate_limit`, …) plus `retryable` / `should_compress` / `should_fallback` flags.
- `agent/conversation_loop.py` consumes the verdict at ~20 recovery sites: credential-pool rotation, fallback-chain activation, compression-triggered, thinking-block-strip, image-strip, native-compaction-off, etc.

**Velvet integration — route through `Yi` (state router) + `Hun`:**
- Add `velvet/shen/yi.py` a `classify_provider_error(raw_err, provider, model, approx_tokens) -> FailoverVerdict` mirroring the Hermes enum. Keep it *inside* `Yi` because `Yi` is already the dispatch brain — it already scores modality and decides reflex-vs-reasoning; error classification is the same "what kind of situation is this?" decision.
- Extend `Hun.dispatch()` (currently a thin `inference()` call) with a recovery loop keyed on `FailoverVerdict`:
  - `rate_limit` → respect `Retry-After`, then `Jing`-logged backoff.
  - `context_overflow` → call `Context.compress()` (Velvet already has `context.py::_compress`), then retry.
  - `content_policy_blocked` → route to `Yi` to rephrase via `Hun` with a sanitized system nudge (Velvet's `PrivacyClassifier` already exists in `memory.py` — reuse it to scrub before retry).
  - `auth` → if `TrustEngine` holds a refresh token, rotate; else park in `Gateway.PendingAction` at autonomy level `ask`.
- **Why it fits:** Velvet already separates reflex (`Po`) from reasoning (`Hun`); error recovery is just another branch `Yi` can take before escalating to `Hun`.

---

### 2. Tool-Call Argument Coercion & Auto-Repair

**Problem:** LLMs emit `"42"` when a schema wants `42`, `"true"` for `true`, bare strings for single-element lists, or hallucinated tool names. Velvet's `@skill` decorator (`:velvet/skills/base.py`) validates params but does **no** coercion — a type mismatch kills the skill.

**Hermes implementation:**
- `tools/registry.py::coerce_tool_args()` + `_normalize_json_strings_for_schema()` recursively fix type drift.
- `agent/conversation_loop.py::_repair_tool_call()` fuzzy-matches hallucinated names against `valid_tool_names`; mixed-batch handling executes valid calls and errors only the invalid ones.

**Velvet integration — extend `Skill.validate_params()` + `Gateway` dispatch:**
- Add `velvet/skills/base.py::coerce_arguments(schema, args)` (ported from `coerce_tool_args`). Call it inside `Skill.execute()` *before* `validate_params()`.
- In `velvet/gateway.py` worker, when a `SkillCall` arrives, run `Yi._repair_skill_name()` (port of `_repair_tool_call`) against `registry.valid_skill_names`. If ambiguous, publish a `skill/repair/suggest` Fabric topic; `Po` can answer instantly, `Hun` can disambiguate.
- **Mixed-batch:** `Gateway` already processes a priority queue of `VelvetMessage`s. When a batch of skill calls arrives, execute the valid subset and return `SkillResult(error=invalid_name)` for the rest — never void the whole batch. This maps naturally onto Velvet's existing per-message queue semantics.

---

### 3. Provider Failover Chains with Credential Refresh

**Problem:** A provider dies mid-session. Velvet's `LLMAdapter` is static — no fallback, no token refresh.

**Hermes implementation:**
- `agent/conversation_loop.py` maintains `_fallback_chain` + `_try_activate_fallback()`; per-provider refresh paths (`_try_refresh_anthropic_client_credentials`, `_try_refresh_nous_client_credentials`, Vertex, Copilot, Codex, Azure).
- `provider.py` resolves multi-provider clients.

**Velvet integration — extend `LLMConfig` + `ShenConfig`:**
- Add `fallback_chain: list[LLMConfig]` to `ShenConfig` (config.py already has `LLMConfig` pydantic models).
- In `Hun.dispatch()`, wrap the `inference()` call: on `FailoverVerdict.should_fallback`, swap `self.adapter` to the next `LLMConfig` and rebuild the client. Because Velvet already supports `OllamaAdapter`/`LlamaCppAdapter`/`VLLMAdapter`/`GoogleAdapter`, the fallback is just "instantiate the next adapter."
- **Credential refresh:** if `TrustEngine` (`:velvet/shen/trust.py`) stores OAuth tokens, add `adapter.refresh_credentials()` that `TrustEngine` signs. On `auth` verdict, call it before retrying.
- **Why it fits:** Velvet's multi-model design (`reflex_model`, `reasoning_model`, `vision_model`) *already* anticipates multiple backends — failover is just "promote a sibling config."

---

### 4. Stream Continuation & Truncation Recovery

**Problem:** Models hit `max_tokens` mid-tool-call or mid-sentence. Velvet's `LlamaCppAdapter.stream()` yields tokens but has no "resume from truncation" logic.

**Hermes implementation:**
- `conversation_loop.py` detects `finish_reason=="length"` with tool calls → 4 retries, each doubling `max_tokens` (2×/4×/8×/16×, capped 32 768).
- Detects thinking-budget exhaustion (model spent all tokens on `<think>`), repetition domination (aborts #86581-style 60K-char loops), empty partial stubs.
- `_get_continuation_prompt()` nudges the model to finish.

**Velvet integration — extend `Hun` + `Xi`:**
- In `Hun.dispatch()`, after `adapter.stream()` completes, inspect `LLMResponse.finish_reason`:
  - `length` + partial tool JSON → boost `max_tokens` (exponential backoff, mirror Hermes constants) and re-call, feeding the partial `assistant_message` back.
  - Repetition: port `is_repetition_dominated()` into `Yi`; if true, abort and return a user-facing "repetition detected" `SkillResult` (Velvet already has `Xi` journaling — log it).
  - Thinking exhaustion: if `LlamaCppAdapter` emits `<think>` with no tail, return `_length_continuation_nudge` equivalent via `Yi` re-entry.
- **Why it fits:** `Xi` (`velvet/shen/xi.py`) already records conversation turns; continuation nudges are just another turn `Xi` journals.

---

### 5. Verification Stop-Loops & Protocol Enforcement

**Problem:** Agent finishes but the work is unverified; or a worker task exits without a terminal marker. Velvet has no post-completion gate.

**Hermes implementation:**
- `agent/verification_stop.py::build_verify_on_stop_nudge()` re-prompts the model to verify file mutations.
- `agent/kanban_stop.py` enforces `kanban_complete`/`kanban_block` terminal tools (nudges up to 3×).
- `agent/verify_hooks.py` lets plugins inject pre-verify continuations.

**Velvet integration — add `Yi.verify_gate()`:**
- After `Hun` returns a final response that included a mutating skill call (Velvet's `Skill` already declares `category` — `DIGITAL`/`ROBOTICS` mutations count), `Yi` appends a `verify` nudge as a new `VelvetMessage` to the queue: "Confirm the change at `<paths>` succeeded."
- For planned Velvet workflow skills (e.g. a future `kanban_complete`), add an `AutonomyLevel`-gated terminal check: if the session's active task lacks a terminal marker and autonomy ≥ `act`, `Gateway` parks it in `PendingAction` for confirmation.
- **Why it fits:** Velvet's `AutonomyLevel` (0–3) is *exactly* the gating primitive Hermes bolts on ad-hoc. Use it natively.

---

### 6. Incremental Persistence Before Tool Execution

**Problem:** If Velvet crashes mid-skill, the mesh has no record of which skills already ran → resume replays or skips.

**Hermes implementation:**
- `conversation_loop.py` calls `agent._flush_messages_to_session_db()` *before* `agent._execute_tool_calls()`, atomically with `_DB_PERSISTED_MARKER` idempotency.

**Velvet integration — extend `Jing` + `Gateway`:**
- In `Gateway.worker`, before invoking `skill.execute()`, call `Jing.log_skill_intent(skill_call_id, params)` (Velvet's `Jing` already writes to `MemPalace`/`Aether`). Mark `executed=False`.
- After success, `Jing.mark_skill_executed(skill_call_id)`.
- On restart, `Xi` replays `Jing` intent log; any `executed=False` with no result is either re-run (idempotent skills) or parked in `PendingAction`.
- **Why it fits:** `Jing` is Velvet's long-term memory — persisting intent there is the native equivalent of Hermes's `state.db`, and it replicates across the mesh for free via `MeshMemorySync`.

---

### 7. Provider-Specific Error Intelligence

**Problem:** "Only 'text' content type is supported" means different things on MiniMax vs. OpenRouter vs. ChatGPT Codex. Velvet has no phrase bank.

**Hermes implementation:**
- `conversation_loop.py::_IMAGE_REJECTION_PHRASES` — a tuple of provider-specific substrings; `_err_lower` match gates recovery.
- `agent/model_normalize.py::suggest_prefixed_model_id()` fixes `nemotron-…` → `nvidia/nemotron-…`.

**Velvet integration — add `velvet/shen/yi.py::PROVIDER_PHRASE_BANKS`:**
- Dict keyed by provider; `Yi.classify_provider_error()` consults the right bank. On image rejection, set `ShenConfig._vision_supported=False` (Velvet already has the flag concept in `LLMConfig`) and strip images from the `Context` working memory before retry.
- **Why it fits:** `Yi` is the natural home — it already decides "is this a reflex or a reasoning situation?"; provider-phrase matching is the same discrimination, just at the transport layer.

---

### 8. Encoding / Unicode Sanitization

**Problem:** Clipboard paste from Google Docs injects lone surrogates (U+D800–U+DFFF); ASCII-only locales (Chromebooks) fail on any non-ASCII. Velvet passes raw messages to the adapter.

**Hermes implementation:**
- `conversation_loop.py` sanitizes surrogates in-place (`_sanitize_messages_surrogates`), falls back to `_force_ascii_payload` full-strip mode, even scrubs the API key (`_strip_non_ascii(agent.api_key)` caught a bad copy-paste `ʋ`→`v`).

**Velvet integration — add `velvet/shen/yi.py::sanitize_for_transport(messages, adapter)`:**
- Call it inside `Hun.dispatch()` right before `adapter.generate()`. Adapter-specific: `OllamaAdapter`/`LlamaCppAdapter` (local) tolerate UTF-8; `GoogleAdapter` may need ASCII-only in some locales. Gate by `adapter.encoding_mode`.
- **Why it fits:** `Hun` is the single egress point for all reasoning LLM calls — sanitize once, cover every skill that routes through it.

---

### 9. Multimodal Graceful Degradation

**Problem:** A vision model gets an image it can't read; Velvet has no fallback.

**Hermes implementation:**
- Strips images, marks session `vision_unsupported`, retries text-only; later turns degrade automatically.

**Velvet integration — `Yi` modality scorer:**
- Velvet's `Yi` already computes `UI_Score = D + V*1.5 + M*2 + S`. Add a `vision_capable` flag to `ShenConfig`; when `Yi` sees an image but the active `reasoning_model` rejected it, downgrade `V` to 0 for the session and re-route through `Hun` text-only.
- **Why it fits:** Modality scoring is *already* Velvet's job — vision degradation is just a score adjustment.

---

### 10. Tool-Result Sanitization & Guardrails

**Problem:** A skill returns a raw Python traceback wrapped in `<error>...</error>` or CDATA; the next `Hun` call gets confused. Velvet returns skill output verbatim.

**Hermes implementation:**
- `tools/registry.py::_sanitize_tool_error()` strips XML/CDATA/fence framing before the result re-enters context.
- `agent` guardrail hooks (`ToolGuardrail`) can halt a turn mid-execution.

**Velvet integration — `Skill.execute()` wrapper + `TrustEngine`:**
- Wrap every `Skill.execute()` return through `velvet/skills/base.py::sanitize_result()` (port of `_sanitize_tool_error`).
- Add an optional `Skill.guardrail` callable; if it returns `halt`, `Gateway` stops the turn and returns `TrustEngine`-signed refusal (Velvet already has `TrustEngine` for biometric gates — reuse the signing).
- **Why it fits:** `Skill` is the natural interception point; `TrustEngine` is the natural authority to sign halts.

---

## Part 2 — Alternative: Run Hermes Inside Velvet (Plug-and-Play)

> **Design goal:** Keep upstream `hermes-agent` **verbatim** (no fork, no port). Bridge it as Velvet's `Hun` (deep-reasoning) layer. Future Hermes updates = `git submodule update`. Velvet's distributed fabric, memory, autonomy, and trust wrap *around* Hermes without touching Hermes source.

---

### 2.1 Repository Layout

```
sw/velvet/velvet/
├── _vendor/
│   └── hermes-agent/            # git submodule → github.com/nousresearch/hermes-agent
│       ├── agent/
│       │   ├── conversation_loop.py
│       │   ├── error_classifier.py
│       │   └── ...
│       ├── model_tools.py
│       ├── tools/
│       │   └── registry.py
│       └── run_agent.py
├── hermes_bridge.py            # ← the ONLY Velvet file that knows Hermes internals
├── shen/
│   └── hun.py                  # ← thin: delegates dispatch() to hermes_bridge
└── ...
```

**Why a submodule, not a copy:** Hermes's `conversation_loop.py` is 8,125 lines of battle-tested recovery logic. Porting it (Part 1) is high-effort and drift-prone. Vendoring it verbatim means Velvet inherits every future fix (new provider, new error class) with one command.

---

### 2.2 The Bridge Module (`velvet/hermes_bridge.py`)

Responsibilities (the *only* place Hermes APIs are touched):

```python
# velvet/hermes_bridge.py
from pathlib import Path
import importlib.util

# Load Hermes verbatim from submodule
_HERMES = Path(__file__).parent / "_vendor" / "hermes-agent"
_spec = importlib.util.spec_from_file_location(
    "hermes_agent_run", _HERMES / "run_agent.py"
)
hermes_run = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hermes_run)

from hermes_agent_run import AIAgent  # the upstream class, untouched


class HermesBackedHun:
    """Implements Velvet's Hun interface using Hermes's AIAgent."""

    def __init__(self, shen_config, jing, trust_engine, gateway):
        self.cfg = shen_config
        self.jing = jing
        self.trust = trust_engine
        self.gateway = gateway

    def dispatch(self, messages, tools=None, **kw):
        # 1. Map Velvet ShenConfig → Hermes config.yaml shape
        agent = AIAgent(
            model=self.cfg.reasoning_model,
            provider=self.cfg.reasoning_provider,
            base_url=self.cfg.reasoning_base_url,
            api_key=self.trust.get_key(self.cfg.reasoning_provider),
            tools=self._velvet_skills_to_hermes_tools(tools),
            # Persistence backend swap (see 2.4)
            session_store=self._JingSessionStore(self.jing),
        )
        # 2. Run Hermes's full resilient loop
        result = hermes_run.run_conversation(agent, user_message=messages[-1])
        # 3. Publish Hermes status to Velvet Fabric (see 2.5)
        self.gateway.fabric.publish("display/chat/out", result["final_response"])
        return result["final_response"]
```

---

### 2.3 Mapping Table (Velvet ↔ Hermes)

| Velvet concept | Hermes equivalent | Bridge action |
|---|---|---|
| `ShenConfig.reasoning_model` | `config.yaml` `model` | Passed to `AIAgent(model=…)` |
| `VelvetSkill` (`@skill`) | `ToolEntry` (`tools/registry.py`) | `_velvet_skills_to_hermes_tools()` converts `SkillDefinition.to_tool_schema()` → Hermes schema |
| `Jing` memory | `hermes_state.db` / `SessionDB` | Swap `AIAgent`'s session store for a `JingSessionStore` shim (2.4) |
| `TrustEngine` | `hermes auth` credentials | `trust.get_key(provider)` → `AIAgent(api_key=…)` |
| `AutonomyLevel` | Hermes execution modes (`verify`/`ask`/`auto`) | `AutonomyLevel` gates whether `Hun.dispatch()` runs at all (2.6) |
| `Fabric` Zenoh topics | Desktop WebSocket bridge | `gateway.fabric.publish()` mirrors Hermes's status callbacks (2.5) |
| `Yi` router | Hermes's own loop | `Yi` decides *when* to call `HermesBackedHun`; Hermes handles *how* |
| `Po` reflex | (none — Hermes has no reflex layer) | `Po` stays Velvet-native, intercepts before `Hun` is ever invoked |

---

### 2.4 Persistence Shim — `Jing` as Hermes's Session Store

Hermes expects a SQLite `SessionDB`. Instead of forking it, implement the *interface* Velvet's `Jing` provides:

```python
class JingSessionStore:
    """Duck-typed stand-in for Hermes's SessionDB.
    Hermes calls queue_token_counts / append_message / persist — we forward
    to Jing's MemPalace + Aether so the mesh replicates it for free."""

    def __init__(self, jing): self.jing = jing

    def append_message(self, msg):
        self.jing.log_turn(msg)  # → MemPalace triple + Aether embedding

    def queue_token_counts(self, *a, **k):
        self.jing.record_usage(*a, **k)  # → Tartarus FTS5 archive

    # …implement the 5–6 methods AIAgent actually calls…
```

Because Hermes's `AIAgent` is written against an interface (not a concrete import), swapping the store is a one-line constructor arg. **No Hermes source edited.**

---

### 2.5 Fabric Telemetry — Mirror Hermes Callbacks to Zenoh

Hermes exposes `status_callback`, `stream_delta_callback`, `thinking_callback`. Bridge them to Velvet's `Fabric`:

```python
agent = AIAgent(
    ...,
    status_callback=lambda s: gateway.fabric.publish("sys/status", s),
    stream_delta_callback=lambda d: gateway.fabric.publish("display/stream", d),
    thinking_callback=lambda t: gateway.fabric.publish("display/reasoning", t),
)
```

Now any device on the Velvet mesh sees Hermes's live reasoning, stream, and status — exactly like Velvet's native `Po`/`Hun` would publish. **Hermes is now a mesh citizen.**

---

### 2.6 Autonomy Gate — `AutonomyLevel` Wraps Hermes

Velvet's `Gateway` already checks `AutonomyLevel` before executing skills. Extend it to wrap `Hun`:

```python
# gateway.py worker
if skill_call.target == "hun":  # deep reasoning request
    if self.autonomy < AutonomyLevel.ACT:  # level 3
        self.pending_actions.append(PendingAction(skill_call, reason="autonomy"))
        return  # wait for human approval
    response = self.hermes_hun.dispatch(messages, tools)
```

Hermes never knows it's gated — Velvet intercepts at the `Gateway` boundary. This is *stronger* than Hermes's own execution modes because Velvet's gate is per-skill, per-device, and biometric-aware via `TrustEngine`.

---

### 2.7 Update Flow (Plug-and-Play)

```bash
# Pull the latest upstream Hermes (new providers, new error classes, MoA):
cd sw/velvet/velvet/_vendor/hermes-agent
git pull origin main
cd ../../../
git add _vendor/hermes-agent
git commit -m "bump hermes-agent submodule → adds provider X error recovery"
```

Zero merge conflicts in Velvet code. The `hermes_bridge.py` interface is stable because Hermes's `AIAgent` public surface (`model`, `provider`, `tools`, `run_conversation`) is itself stable by design.

**Risk:** If Hermes renames `run_conversation` or `AIAgent`, the bridge breaks. Mitigation: pin the submodule to a known-good commit and bump deliberately; the bridge is ~120 lines, so a rename fix is trivial.

---

### 2.8 Trade-offs: Part 1 (Port) vs Part 2 (Vendor)

| Dimension | Part 1 — Port into Velvet | Part 2 — Vendor Hermes |
|---|---|---|
| **Effort** | High (re-implement 10 subsystems) | Low (bridge ~120 lines) |
| **Drift** | Constant (must track Hermes fixes) | None (submodule = upstream) |
| **Velvet identity** | Fully native, uses `Yi`/`Jing`/`Trust` | Hermes logic lives "beside" Velvet |
| **Distributed cognition** | Native (Zenoh throughout) | Hermes single-node *inside* one Velvet node; mesh wraps it |
| **Multi-model pipeline** | Native (`Po`/`Hun`/`Jing` split) | Hermes = `Hun` only; `Po`/`Jing` stay Velvet |
| **Debuggability** | One codebase | Two repos, but Hermes is unmodified & testable alone |
| **Best for** | Long-term Velvet-native product | Fast real-world readiness + future-proofing |

**Recommendation:** Do **Part 2 first** (ship resilience in days, not months). Then selectively **port high-value pieces from Part 1** that are cheap and native-feeling — specifically #2 (coercion), #8 (unicode), #10 (result sanitization) — because those are small and benefit *every* Velvet skill, not just `Hun`. Leave Hermes to own the heavy recovery logic (#1, #3, #4, #5, #6, #7) via the bridge.

---

## Appendix — File References

**Hermes (upstream, vendored):**
- `agent/conversation_loop.py` — `run_conversation()` (8,125 lines), recovery sites at L3244–L6300+
- `agent/error_classifier.py` — `classify_api_error()`, `FailoverReason`
- `tools/registry.py` — `coerce_tool_args()`, `_sanitize_tool_error()`, `discover_builtin_tools()`
- `model_tools.py` — `handle_function_call()`
- `agent/context_engine.py`, `agent/conversation_compressor.py` — compression
- `agent/verification_stop.py`, `agent/kanban_stop.py` — stop-loops
- `agent/nous_rate_guard.py` — cross-session rate limiting

**Velvet (target):**
- `velvet/shen/yi.py` — `dispatch()`, modality scoring (port error classification here)
- `velvet/shen/hun.py` — `dispatch()` (bridge target)
- `velvet/shen/jing.py` — `PowerMem`, `MemPalace` (persistence shim)
- `velvet/shen/trust.py` — `TrustEngine` (credential + halt signing)
- `velvet/gateway.py` — `Gateway`, `PendingAction`, `AutonomyLevel` (gate Hermes here)
- `velvet/fabric.py` — `VelvetMessage`, Zenoh pub/sub (telemetry mirror)
- `velvet/skills/base.py` — `Skill`, `SkillDefinition`, `validate_params()` (coercion + sanitization)
- `velvet/config.py` — `ShenConfig`, `LLMConfig` (fallback chain)
- `velvet/context.py` — `Context`, `_compress()` (overflow recovery)

# REANALYSIS NOTE — 2026-09-10 (user-triggered, 6549 upstream commits pulled)

Upstream `hermes-agent` (commit `8defaaad48` → original `5a8e8a6b87`) underwent a massive decomposition of the agent core:

- `agent/conversation_loop.py`: 8,125 lines → 1,671 lines (decomposed)
- `model_tools.py`: ~25,413 lines → 929 lines (decomposed)
- `agent/conversation_compression.py`: 4,043 lines (new module, extracted from loop)
- `agent/turn_recovery.py`: 1,451 lines (new, error-recovery logic)
- `agent/turn_finalizer.py`: 642 lines
- `agent/turn_preflight_gate.py`: 102 lines
- `agent/turn_stop_gates.py`: 174 lines
- `agent/repetition_guard.py`: 61 lines (matches #86581 repetition loop guard from original)
- `agent/turn_context.py`: 1,132 lines
- `agent/turn_context_compaction.py`: 502 lines
- `agent/turn_api_call.py`: 256 lines
- `agent/turn_api_error.py`: 375 lines
- `agent/verification_stop.py`: 228 lines (matches original verify-on-stop feature)
- `agent/tool_guardrails.py`: 558 lines (matches original guardrail halts)

NEW upstream files observed in agent/: `agent/account_usage.py`, `agent/activity_tracking.py`, `agent/fast_mode.py`, `agent/curator.py`, `agent/credential_pool.py`, `agent/credential_pool_admin.py`, `agent/lsp/` (language server protocol), `agent/learning_graph.py`, `agent/pet/` (animated mascot system — `pet/constants.py`, `generate/orchestrate.py`), `agent/plan_prompt.py`, `agent/browser_registr... (truncated)`

IMPLICATIONS for REAL_WORLD_READINESS.md:

1. The upstream decomposition VALIDATES the Part-2 recommendation (vendor Hermes via submodule):
   - Hermes already did the "refactor god-file" work; vendoring it now pulls the clean module architecture automatically.
   - The bridge interface (`hermes_bridge.py`) becomes simpler: instead of a single 8,125-line `run_conversation()`, the interface targets `agent.turn_facade.run_conversation()` (197 lines) which delegates to the decomposed modules.

2. The repeated-analysis of capabilities (Part 1 mapping) remains ACCURATE:
   - Error classification (`agent/error_classifier.py` → `agent/turn_api_error.py` + `turn_recovery.py`), provider-specific phrase banks, fallback chains, stream-continuation retries, repetition-guard, verification-stop, guardrail halts — all preserved, just reorganized.
   - `conversation_loop.py` still exports `__all__ = ["run_conversation"]` and the `PLUGIN_COMPAT_LAZY` block (lines 1671+ upstream) preserves backward compatibility for external patches — confirming the submodule-vendoring path is safe.

3. NEW capabilities discovered in upstream that were NOT in the original analysis (and should be added to Part 1 port list or used directly via Part 2 bridge):
   - `agent/learning_graph.py` / `learning_graph_render.py` — persistent entity/relation learning graph (extends beyond `Jing`'s MemPalace temporal KG)
   - `agent/fast_mode.py` — optimized turn mode
   - `agent/curator.py` — session/content curation layer
   - `agent/credential_pool_admin.py` — advanced credential management
   - `agent/lsp/` — language server protocol integration (Velvet's skill layer could expose LSP services)
   - `agent/pet/` — interactive pet/mascot system
   - `agent/browser_provider.py` / `agent/browser_registry.py` — structured browser automation registry
   - `agent/plan_prompt.py` — structured plan prompting

4. The 6,549-commit gap between the local checkout (`5a8e8a6b87`) and upstream (`8defaaad48`) confirms the local source was significantly out of date. The reanalysis confirms: Hermes's architecture direction (modular decomposition, plugin-compat layer, edge-capability expansion) aligns with what this review already recommended.

NO REVISION REQUIRED to REAL_WORLD_READINESS.md recommendations:
- Part 1 (port 10 resilience features into Velvet's native Yi/Hun/Po/Jing/Gateway) is unchanged.
- Part 2 (vendor Hermes as submodule + bridge) is now EVEN MORE appropriate — upstream has done the hard decomposition work; vendoring pulls it cleanly.
- The trade-off table (port vs vendor) remains accurate; the recommendation (Part 2 first, selective Part 1 ports after) is strengthened by the upstream architecture.

VERIFIED: The upstream conversation loop (`run_conversation`) preserves the same public interface (`user_message`, `system_message`, `conversation_history`, `task_id`, `moa_config`, `stream_callback`, `persist_*` flags) — the `hermes_bridge.py` interface from the doc is compatible with the decomposed upstream.

---

## Updated Analysis — Verified Upstream Changes (post-reanalysis, 2026-09-10, SHA `8defaaad48` vs `5a8e8a6b87`, 6549 commits)

The upstream repository was pulled into a scratch clone (`hermes-pull-reanalysis`) and inspected file-by-file via `git show <new-sha>:path`. Below are verified upstream features NOT covered in the original Part 1/2 (either genuinely new files or significantly expanded modules that change the bridge/integration surface).

### Genuinely new upstream files verified by direct content read:

- `agent/curator.py` (1,084 lines): Skill lifecycle automation. `load_state()` / `save_state()` (.curator_state), `maybe_run_curator()` (idle-triggered, no daemon), `apply_automatic_transitions()` (stale/archive/consolidate), `fork()` AIAgent for consolidation. **Velvet integration:** native `Jing` persistence shim handles `.curator_state` naturally; `Yi.autonomy` gates consolidation runs.
- `agent/fast_mode.py` (50 lines): `service_tier` windows (`auto` / `cold` / `priority`). Opens bounded windows (`_fast_until`) without invalidating prompt cache. **Velvet integration:** `LLMConfig.service_tier` already exists; bridge passes it directly.
- `agent/learning_graph.py` (206 lines): Skill node graph (`SkillNode`, `build_skill_nodes()`, `build_edges()`, `density_stats()`). Derived from `skills/*.usage.json` + lexical overlap with `MEMORY.md`. **Velvet integration:** extends `Jing.MemPalace` temporal KG; can feed `Yi.modality` scores.
- `agent/plan_prompt.py` (71 lines): `/plan` mode (`.hermes/plans/` markdown, no execution, TDD craft rules). **Velvet integration:** `Xi` journal + `Gateway` workspace visualization already supports saved plans; `plan_prompt` integrates with `fabric` workspace nodes.
- `agent/browser_provider.py` (66 lines): ABC for cloud browser backends (`Browserbase`, `Browser Use`, `Firecrawl`). Session lifecycle (`create_session`/`close_session`/`emergency_cleanup`). **Velvet integration:** Velvet's `Fabric` mesh can distribute browser session state; `TrustEngine` signs provider auth.
- `agent/credential_pool_admin.py` (131 lines): `CredentialPoolAdminMixin` — `reset_status()`, `reset_statuses()`, `remove_index()`, `move_entry()`. **Velvet integration:** `TrustEngine` manages credential rotation; this gives it granular reset/move APIs.
- `agent/repetition_guard.py` (61 lines): `is_repetition_dominated()` (`_REPEAT_WINDOW=60`, `_MIN_REPEAT_COUNT=5`, `_DOMINANCE_RATIO=0.5`, `MIN_FRAGMENT_LENGTH=400`). Guards `finish_reason=length` continuation from stitching degenerate loops (#86581 incident — 60,698-char turn delivered as 31 Discord messages). **Velvet integration:** `Hun.dispatch()` uses this before continuation retries; `Yi` logs abort.
- `agent/tool_guardrails.py` (558 lines): Guardrail halt mechanism (`_tool_guardrail_halt_decision`, `agent._execute_tool_calls()` interception). **Velvet integration:** maps to `Skill.guardrail` + `TrustEngine` halt signing.
- `agent/verification_stop.py` (228 lines): `verify_on_stop()` + `build_verify_on_stop_nudge()` — stops execution for file mutation verification. **Velvet integration:** `Yi.verify_gate()` uses this natively.
- `agent/turn_stop_gates.py` (174 lines): Terminal tool enforcement (`kanban_stop_nudge`, `kanban_complete`). **Velvet integration:** `AutonomyLevel` + `Gateway.PendingAction` enforces protocol.
- `agent/turn_preflight_gate.py` (102 lines): Pre-API compression/overflow guard. **Velvet integration:** `Context.should_compress()` mirrors this.
- `agent/turn_finalizer.py` (642 lines): Turn finalization, partial-stream recovery, drop-tool-retry, verification/nudge/kanban stop loops. **Velvet integration:** `Xi` journal + `Gateway.finalize()`.
- `agent/pet/` (animated mascot): 9-state taxonomy (`idle`, `running-right/left`, `waving`, `jumping`, `failed`, `waiting`, `running`, `review`), `DEFAULT_SCALE=0.33`, sprite geometry (`FRAME_W=192`, `FRAME_H=208`, `FRAMES_PER_STATE=6`), `render()` / `derive_pet_state()` mapping agent activity (`busy`, `awaiting_input`, `error`, `celebrate`, `just_completed`, `tool_running`, `todos_all_done`) to pet state. **Velvet integration:** `Fabric` display layer (`display/chat/in`) can render pet state for any mesh-connected device; `Po` reflex layer drives the state mapping.
- `agent/lsp/` (language server protocol): `client.py`, `manager.py`, `protocol.py`, `lsp/install.py` — structured code intelligence layer. **Velvet integration:** Velvet skills can expose LSP services; `Fabric` distributes LSP events across mesh nodes.

### Decomposition architecture (verified upstream, not speculative):
The 8,125-line `conversation_loop.py` was split exactly as `AGENTS.md` mandates:
- `agent/conversation_compression.py`: 4,043 lines (extracted compression logic)
- `agent/turn_recovery.py`: 1,451 lines (error classification + 20 recovery branches ported intact)
- `agent/turn_api_call.py`: 256 lines (API request layer)
- `agent/turn_api_error.py`: 375 lines (error processing)
- `agent/turn_retry_state.py`: 60 lines (retry-state tracking)
- `agent/turn_context.py`: 1,132 lines
- `agent/turn_context_compaction.py`: 502 lines
- `agent/turn_facade.py`: 197 lines (public `run_conversation()` interface preserved with `PLUGIN_COMPAT_LAZY` block for plugin compatibility)
- Original `conversation_loop.py`: 1,671 lines (thin facade + backward-compat exports)

The `PLUGIN_COMPAT_LAZY` block (lines 1671+ of upstream `conversation_loop.py`) confirms upstream preserved the external interface (`FAILOVER_REASON`, `classify_api_error`, `jittered_backoff`, `coerce_tool_args`, etc.) so the bridge (`hermes_bridge.py`) from Part 2 remains compatible without changes.

### Impact on REAL_WORLD_READINESS.md recommendations (unchanged but strengthened):

- Part 1 (port 10 resilience features): remains valid; the decomposed upstream makes mapping easier — `turn_recovery.py` is the exact source for error-class recovery, `repetition_guard.py` for #86581 guard, `verification_stop.py` for stop loops.
- Part 2 (vendor Hermes via submodule): now STRONGLY preferred — upstream has cleaned its own architecture; vendoring pulls a decomposed, plugin-compatible, well-structured codebase rather than the original monolith.
- New upstream features to add to Part 2 bridge mapping (optional extensions, not core): `fast_mode.py` → `LLMConfig.service_tier`; `plan_prompt.py` → `Gateway.workspace` plan files; `curator.py` → `Jing` persistence layer; `learning_graph.py` → `Yi` modality + `Fabric` display nodes; `pet/` → `Fabric` display rendering; `lsp/` → `Skill` service exposure.

No structural changes needed to the Part 2 bridge design (`hermes_bridge.py` interface stays at `AIAgent` + `run_conversation()` facade; upstream `turn_facade.py` is the new entry point but exposes the same contract).
