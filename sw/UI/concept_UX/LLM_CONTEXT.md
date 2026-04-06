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

## Key Rules
1. All buttons filled - never outline-only
2. Angular clip-path on buttons/tabs
3. Rectangular containers
4. Geometric icons (no emojis)
5. Icons use --primary color
6. Glow = 5px fixed
