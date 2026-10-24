# Velvet Nadir Design Language

**Version:** 1.0 | **Style:** Minimalist + Cyberpunk

## Colors
```css
:root {
    --bg: #000; --bg2: #0a0a0a; --fg: #fff; --muted: #555; --dim: #1a1a1a;
    --primary: #00d4ff; --secondary: #ff44aa; --neutral: #444444; --alert: #ff4444;
    --glow: 5px;
}
.light { --bg: #f5f5f8; --bg2: #fff; --fg: #111; --muted: #777; --dim: #ddd; }
```

## Iconography (Geometric Unicode)
| ◉ Context | ◎ Memory | ◇ Calendar | ⬡ Search | △ Warning |
| ▢ Folder | ▤ Document | ▥ Image | ▷ Video | ◈ Notification |

## Buttons (All Filled)
```html
<button class="btn neutral">Cancel</button>
<button class="btn primary">Confirm</button>
<button class="btn secondary">Options</button>
```
Angular shape: `clip-path: polygon(4px 0, 100% 0, 100% calc(100% - 4px), calc(100% - 4px) 100%, 0 100%, 0 4px);`

## Containers
- `container-rect` - bordered rectangles (default)
- `container-blank` - no borders
- `container-glass` - translucent blur

## States
`.active` `.current` `.past` `.alert` `.selected` `.on` `.highlight` `.flipped` `.paused` `.dismissed` `.expanded`

## Dynamic Widget & Modality Levels
- **`ZERO_UI`**: Ambient voice mode (UI_Score < 2).
- **`MICRO_UI`**: HUD overlay / toast notification (2 <= UI_Score < 4).
- **`WIDGET_UI`**: Direct manipulation widget - Media scrubber, 3D model spinner, File Explorer (4 <= UI_Score < 7).
- **`MACRO_UI`**: Full workspace canvas takeover (UI_Score >= 7).
