# Display State & Frontend Integration (`display_state.py`, Web UI)

## Overview
Coordinates visual state representations between backend Python processes and the browser frontend.

## Components
- `display_state.py`: Python state machine broadcasting UI changes (`display/update`, `display/reconnect`).
- `agent-orb.js`: Three.js / Canvas rendering of the multimodal agent orb representing listening, thinking, speaking, and alert states.
- `canvas-animations.js`: Real-time telemetry, waveform rendering, and force-directed graph physics.
- `notifications.js`: Toast alerts, biometric approval prompts, and security alerts.
- `ws-bridge.js`: WebSocket bridge connecting browser clients to local Velvet Gateway and handling automatic reconnection during 12h port rotations.
