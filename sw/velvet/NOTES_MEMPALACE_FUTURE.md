# MemPalace — Skipped Features for Future Consideration

> Documented during Sprint 15 (2026-05-08). We integrated only the **Knowledge Graph** from MemPalace.
> These features were evaluated and deferred. Revisit when relevant.

## Contradiction Detection
- **What**: Checks new assertions against existing KG facts — catches attribution conflicts, temporal errors, stale information
- **Status in MemPalace**: Marked "experimental" — KG primitives exist but no end-to-end CLI/MCP tool shipped yet
- **Velvet relevance**: High. Multi-agent mesh means conflicting memories are inevitable. Could be wired into Agni (purification layer) to flag contradictions during memory consolidation.
- **When to revisit**: After Agni is operational and we have enough KG data to test against

## AAAK Dialect (Lossy Compression)
- **What**: ~40% token reduction via lossy text compression with entity-aware abbreviation mappings
- **Velvet relevance**: Medium. Could reduce context window pressure in Gateway LLM calls, especially on edge devices (Jetson) with limited context length.
- **When to revisit**: When we hit context window limits on edge inference

## Memory Stack (L0–L3 Progressive Loading)
- **What**: 4-layer memory: L0 Identity (~50 tokens), L1 Essential Story (~600-900 tokens), L2 On-Demand Recall, L3 Deep Search
- **Velvet relevance**: Low (overlaps). Our Aether/Mnemosyne/Tartarus tier model serves the same purpose with different metaphors. No value in replacing what works.
- **When to revisit**: If we ever deprecate PowerMem entirely

## MCP Server (29 Tools)
- **What**: Full MCP tool suite for palace reads/writes, KG operations, cross-wing navigation, agent diaries
- **Velvet relevance**: Medium-future. Useful for interop with Claude Code, Gemini CLI, and other MCP-compatible tools. Not relevant to Velvet's internal mesh architecture today.
- **When to revisit**: When we build external tool integrations or developer APIs

## Palace Graph (Room-Based Navigation)
- **What**: Cross-wing navigation graph built from ChromaDB metadata. `traverse()`, `find_tunnels()`, `graph_stats()`
- **Velvet relevance**: Low (overlaps). Our ContextWorkspace spatial model + Locus engine already handle spatial navigation and context scoping.
- **When to revisit**: If we need cross-context "tunnel" discovery (e.g., finding hidden connections between unrelated workspaces)
