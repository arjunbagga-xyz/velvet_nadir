# Velvet Dashboard UI Handoff

> Comprehensive guide for the agent taking over **Icons, Animations, and Micro-interactions** for the Velvet Nadir Web UI.

**Date:** March 2026
**Target Path:** `sw/UI/app/`

---

## 1. Tech Stack & Environment

- **Architecture:** Vanilla HTML5, CSS3, and JavaScript (ES6 Modules).
- **Frameworks:** None. No React, Vue, Svelte, Tailwind, or complex build pipelines (Webpack/Vite). Pure DOM manipulation for maximum performance and explicit control.
- **Server:** Simple static file server. Run the application from the `sw/UI/app/` directory:
  ```bash
  npx -y http-server . -p 3000 -c-1 --cors
  ```

## 2. File Structure

All UI code resides within `sw/UI/app/`:

- `index.html`: The monolithic root document. Contains structural layout, navigation bars, fixed tooltips, and empty container divs for dynamic JS injection.
- `styles.css`: 3000+ line absolute source of truth for styling. Heavily relies on CSS variables for dynamic theming, CSS Flexbox/Absolute Positioning for layouts, and specific z-index stacking layers.
- `app.js`: Core application entry point. Handles view switching (Zenoh Fabric vs Jing vs Noise), global event listeners (mouse movements for tooltips), data orchestration, and `<canvas>` rendering loops via `requestAnimationFrame`.
- `data.js`: Mock data payloads representing the backend state (contexts, devices, logs).
- `entity-popups.js`: HTML string builders for dynamic popup content (Device info, Context details, etc.) and semantic SVG icon mapping. Relies on the Window Manager.
- `window-manager.js`: Custom window management system. Handles spawning, dragging, resizing, minimizing (to left taskbar), and closing persistent DOM windows entirely natively.
- `memory-graph.js`: Specific logic for rendering the interactive D3/force-directed style graph on the "Jing" (Memory) view.

## 3. Core UI Systems & Previous Work

The previous agent completed structural layout fixes, global color unification, and stability logic.

### Theming System (The C1/C2/C3 Schema)
The UI uses a dynamic, dual-tone glowing glassmorphism aesthetic.
- **Variables:** Themes are driven by RGB tuples defined in `:root` (e.g., `--c1: 20, 184, 166;`).
- **Badges:** A strict semantic coloring rule applies globally via the `badge(text, type)` helper:
  - **Positive (`type="positive"`):** C2 text on a 15% opacity C3 background.
  - **Negative (`type="negative"`):** C3 text on a 15% opacity C2 background.
  - **Neutral (`type="neutral"`):** C1 text on a 15% opacity C1 background.
- **Glassmorphism:** Achieved via `background: var(--surface-glass)` and `backdrop-filter: blur(Npx)`. Neumorphic lighting is simulated using internal 1px borders and outer glowing drop shadows (`box-shadow: 0 0 var(--glow) var(--accent-glow)`).

### Window Manager Layout Stability
Popups are **persistent** stateful DOM elements. They do *not* auto-close when clicking outside. They must be manually closed or minimized to the `#left-taskbar`. 
- **Desktop:** The taskbar uses `position: absolute; right: calc(100% + 10px)` to float symmetrically to the left of the main `<nav>`, preventing any flex layout shifts when minimized items appear.
- **Mobile (<768px):** Absolute overrides drop and flex `order` properties take over to stack the Top Bar into a vertical column: `Main Nav (Order 1) -> Actions (Order 2) -> Taskbar (Order 3)`.

## 4. Incoming Objective: Icons & Animations

Your focus is bringing the static application to life.

> **User Request:** "Next we are gonna work on icons and animations and stuff."

### Priorities for the UI Animator Agent:
1. **Entity Icons:** The `ICONS` object inside `app.js` and `entity-popups.js` currently holds functional but static SVGs (squares, server racks, brains). The user explicitly intends to upgrade these to **animated entity icons**.
2. **Micro-Interactions (CSS):** The stylesheet has basic `:hover` colors, but lacks sophisticated micro-interactions. Consider adding scale transforms on click (`:active`), ripple effects, or smooth `transition` properties for core buttons (`.nav-item`, `.remote-ctrl-btn`, `.icon-btn`).
3. **Popup Transitions (CSS/JS):** Window popups currently snap instantly into existence out of thin air. Implement CSS keyframe animations/transitions for spawning (e.g., scale-up fade-in) and minimizing (smoothly morphing into the taskbar).
4. **Canvas Animations (JS):** `app.js` runs a continuous `requestAnimationFrame` loop (`renderMeshConnectionsLoop`) that draws lines between operations mesh nodes. Review functions like `renderDormantSineConnection` and `renderSilkPulseConnection`. If the user requests enhancements to the network mesh visuals natively, this is where the math lives.
