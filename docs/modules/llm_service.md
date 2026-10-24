# Mesh LLM Service (`services/llm_service.py`, `llm.py`)

## Overview
Coordinates distributed LLM inference across heterogeneous mesh nodes (Ollama, vLLM, llama.cpp, cloud providers).

## Features
- **Node Cooldown & Exponential Backoff**: Tracks failures per node with cooldown timers ($2^n \times \text{base}$ seconds) avoiding black-holed requests.
- **Independent Judge Routing (`generate_judge`)**: Excludes the worker node and worker model from evaluating its own output.
- **Defensive Generation**: Transparently handles truncated JSON, strips thinking tokens (`<think>...</think>`), coerces malformed arguments, and retries across alternate nodes.
