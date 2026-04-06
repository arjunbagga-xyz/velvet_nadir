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

## Widget
```html
<div class="widget" data-name="Title">content</div>
<div class="widget wide" data-name="Wide">content</div>
```
