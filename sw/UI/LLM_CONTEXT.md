# Velvet Nadir - LLM Context

Generate UI using **Velvet Nadir**: dark-first, minimalist + cyberpunk.

## Colors
```css
--bg: #000; --bg2: #0a0a0a; --fg: #fff; --muted: #555; --dim: #1a1a1a;
--primary: #00d4ff; --secondary: #ff44aa; --neutral: #444444; --alert: #ff4444; --glow: 5px;
```

## Buttons - ALL FILLED
```html
<button class="btn neutral">Cancel</button>
<button class="btn primary">Confirm</button>
<button class="btn secondary">Options</button>
```
Angular: `clip-path: polygon(4px 0, 100% 0, 100% calc(100% - 4px), calc(100% - 4px) 100%, 0 100%, 0 4px);`

## Icons (Geometric Unicode, colored --primary)
◉ Context | ◎ Memory | ◇ Calendar | ⬡ Search | △ Warning | ▢ Folder | ▤ Document | ▥ Image | ▷ Video | ◈ Notification

## Widget
```html
<div class="widget" data-name="Title">content</div>
```

## States
`.active` `.current` `.alert` `.selected` `.on` `.highlight` `.flipped` `.paused` `.dismissed`

## Modality Decision Engine & Direct Manipulation
$$\text{UI\_Score} = D + (V \times 1.5) + (M \times 2) + S$$

- **LEVEL 0 (`ZERO_UI`)** ($\text{UI\_Score} < 2$): Ambient voice output only.
- **LEVEL 1 (`MICRO_UI`)** ($2 \le \text{UI\_Score} < 4$): Micro HUD toast overlay.
- **LEVEL 2 (`WIDGET_UI`)** ($4 \le \text{UI\_Score} < 7$): Direct manipulation widget (Media Controller, 3D Inspector, File Explorer).
- **LEVEL 3 (`MACRO_UI`)** ($\text{UI\_Score} \ge 7$): Full workspace canvas takeover.

## Dynamic UI Event Protocol
- `ui.widget.render`: Pushes JSON payload describing widget type (`media`, `model3d`, `editor`, `micro_hud`), title, and direct manipulation parameters.
- `widget.action`: Dispatches direct manipulation actions (seek, toggle_play, spin_model, save_file) back to backend daemons over WebSocket.

## Key Rules
1. All buttons filled - never outline-only
2. Angular clip-path on buttons/tabs
3. Rectangular containers
4. Geometric icons (no emojis)
5. Icons use --primary color
6. Glow = 5px fixed
7. UI surfaces ONLY when `UI_Score >= 4` and a display device is nearby.
