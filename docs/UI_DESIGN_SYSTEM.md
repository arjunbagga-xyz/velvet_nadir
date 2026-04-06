# 🎨 UI Design System: Agent-Generatable Interfaces

> Minimal, lightweight, dynamic UI for ambient computing

---

## 📐 Core Philosophy

### The Problem with Traditional UI
Traditional interfaces are **static, complex, and require human designers**. For Velvet Nadir:
- UI is rarely needed (audio-first)
- When needed, it must be generated **instantly by agents**
- Must be **lightweight** (tiny displays, AR overlays)
- Must be **parseable by AI** (for generation and reading)

### The Solution: Semantic Wireframe System

```
┌─────────────────────────────────────────────────────────────────┐
│                 UI GENERATION FLOW                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  User Request ──▶ Agent ──▶ Semantic UI Spec ──▶ Renderer ──▶ Display
│                                                                 │
│  Example:                                                       │
│  "Show my schedule"                                             │
│       │                                                         │
│       ▼                                                         │
│  {                                                              │
│    "type": "list",                                              │
│    "variant": "timeline",                                       │
│    "items": [                                                   │
│      {"time": "9:00", "text": "Standup", "priority": "normal"}, │
│      {"time": "2:00", "text": "Client Call", "priority": "high"}│
│    ]                                                            │
│  }                                                              │
│       │                                                         │
│       ▼                                                         │
│  Rendered wireframe on display                                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🧱 Primitive Components

The smallest building blocks that agents can compose:

### Text Primitives

```yaml
# Hierarchy levels for text
text_primitives:
  - type: "title"      # Largest, bold, main heading
  - type: "subtitle"   # Secondary heading
  - type: "body"       # Standard paragraph text
  - type: "caption"    # Small, muted, metadata
  - type: "label"      # Tiny, uppercase, category tags
```

### Layout Primitives

```yaml
# Container types
layout_primitives:
  - type: "stack"      # Vertical arrangement
    variants: ["tight", "normal", "loose"]
  
  - type: "row"        # Horizontal arrangement
    variants: ["start", "center", "between", "end"]
  
  - type: "card"       # Bordered container with padding
    variants: ["flat", "elevated", "outlined"]
  
  - type: "grid"       # N-column grid
    columns: [1, 2, 3, 4]
```

### Interactive Primitives

```yaml
# User interaction elements
interactive_primitives:
  - type: "button"
    variants: ["primary", "secondary", "ghost", "danger"]
  
  - type: "toggle"
    states: ["on", "off"]
  
  - type: "slider"
    range: [min, max, step]
  
  - type: "input"
    variants: ["text", "number", "voice"]
```

### Visual Primitives

```yaml
# Non-text visual elements
visual_primitives:
  - type: "icon"
    set: ["system", "emoji", "custom"]
  
  - type: "divider"
    variants: ["solid", "dashed", "none"]
  
  - type: "progress"
    variants: ["bar", "circle", "dots"]
  
  - type: "badge"
    variants: ["count", "dot", "status"]
  
  - type: "avatar"
    variants: ["image", "initials", "icon"]
```

---

## 📦 Compound Components

Pre-composed patterns that agents can invoke by name:

### List Views

```
┌─────────────────────────────────────────────────────────────────┐
│ LIST: Simple                                                    │
├─────────────────────────────────────────────────────────────────┤
│  • Item one                                                     │
│  • Item two                                                     │
│  • Item three                                                   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ LIST: With Icons                                                │
├─────────────────────────────────────────────────────────────────┤
│  📧  Email from Sarah          3 unread                        │
│  📅  Meeting at 2pm            In 45 minutes                   │
│  ✅  Task: Review docs         Due today                       │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ LIST: Timeline                                                  │
├─────────────────────────────────────────────────────────────────┤
│  9:00  ○─── Team Standup                                       │
│        │                                                        │
│ 10:30  ●─── Client Call              ← NOW                     │
│        │                                                        │
│ 12:00  ○─── Lunch                                              │
│        │                                                        │
│  2:00  ◐─── Design Review            High priority             │
└─────────────────────────────────────────────────────────────────┘
```

### Cards

```
┌─────────────────────────────────────────────────────────────────┐
│ CARD: Info                                                      │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  ☀️  Weather                                            │   │
│  │  ───────────────────────────────────────────────────────│   │
│  │  72°F  Sunny                                            │   │
│  │  High: 78° Low: 65°                                     │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ CARD: Action                                                    │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  📞  Incoming Call                                      │   │
│  │  ───────────────────────────────────────────────────────│   │
│  │  Sarah Chen                                             │   │
│  │  Mobile • Last called 2 days ago                        │   │
│  │                                                         │   │
│  │  [ Decline ]              [ Answer ]                    │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ CARD: Choice                                                    │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  🛣️  Route Options                                      │   │
│  │  ───────────────────────────────────────────────────────│   │
│  │  ○  Highway 101    35 min  ███████░░  Traffic           │   │
│  │  ●  Highway 280    28 min  ██░░░░░░░  Clear    ← Best   │   │
│  │  ○  Surface roads  45 min  █░░░░░░░░  Light             │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Notifications

```
┌─────────────────────────────────────────────────────────────────┐
│ TOAST: Minimal (auto-dismiss)                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────┐                   │
│  │  ✓  Meeting added to calendar           │                   │
│  └─────────────────────────────────────────┘                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ BANNER: Persistent                                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ⚠️  Low battery (15%) • Nearby charger at Gate B7   [ • • • ] │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🎭 Visual Themes

### Theme: Wireframe (Default for Glasses/Small Displays)

```css
/* Minimal monochrome, maximum clarity */
:root {
  --bg: #000000;           /* Pure black */
  --fg: #FFFFFF;           /* Pure white */
  --accent: #00FF00;       /* High-viz green for highlights */
  --muted: #666666;        /* Secondary text */
  --border: #333333;       /* Subtle borders */
  
  --font-mono: "SF Mono", monospace;
  --font-size-base: 14px;
  --line-height: 1.4;
  --spacing: 8px;
  --radius: 0px;           /* Sharp corners */
}
```

Visual example:
```
┌─────────────────────────────────────────────────────────────────┐
│                     WIREFRAME THEME                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────────────────────────────────────────┐          │
│   │  SCHEDULE TODAY                                 │          │
│   ├─────────────────────────────────────────────────┤          │
│   │  09:00  Standup                                 │          │
│   │  10:30  ▶ CLIENT CALL                          │          │
│   │  12:00  Lunch                                   │          │
│   └─────────────────────────────────────────────────┘          │
│                                                                 │
│   [ Cancel ]                              [ Confirm ]          │
│                                                                 │
│   ▶ = current/highlighted (green accent)                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Theme: Skeleton (Loading States)

```css
/* Pulsing placeholder for loading content */
.skeleton {
  background: linear-gradient(
    90deg,
    #1a1a1a 0%,
    #2a2a2a 50%,
    #1a1a1a 100%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}
```

Visual example:
```
┌─────────────────────────────────────────────────────────────────┐
│                     SKELETON LOADING                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────────────────────────────────────────┐          │
│   │  ████████████████                               │          │
│   ├─────────────────────────────────────────────────┤          │
│   │  ░░░░░  ██████████████████                      │          │
│   │  ░░░░░  ███████████                             │          │
│   │  ░░░░░  █████████████████████                   │          │
│   └─────────────────────────────────────────────────┘          │
│                                                                 │
│   ████ = pulsing/shimmering animation                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Theme: Holographic (AR Glasses)

```css
/* Translucent, edge-lit, futuristic */
:root {
  --bg: rgba(0, 0, 0, 0.6);      /* Semi-transparent */
  --fg: #00FFFF;                  /* Cyan primary */
  --accent: #FF00FF;              /* Magenta highlight */
  --glow: 0 0 10px rgba(0, 255, 255, 0.5);
  
  --border: 1px solid rgba(0, 255, 255, 0.3);
  --radius: 8px;
}
```

Visual example:
```
┌─────────────────────────────────────────────────────────────────┐
│                     HOLOGRAPHIC THEME                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ╔═══════════════════════════════════════════════════╗        │
│   ║  ◈ INCOMING MESSAGE                               ║        │
│   ╟───────────────────────────────────────────────────╢        │
│   ║                                                   ║        │
│   ║  From: Sarah Chen                                 ║        │
│   ║  "Are we still on for 3pm?"                       ║        │
│   ║                                                   ║        │
│   ║  ⟨ Reply ⟩        ⟨ Dismiss ⟩        ⟨ Call ⟩     ║        │
│   ║                                                   ║        │
│   ╚═══════════════════════════════════════════════════╝        │
│             ↑                                                   │
│    Double-line borders with glow effect                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🤖 Agent UI Specification Format

### JSON Schema for Agent-Generated UI

```json
{
  "$schema": "velvet-ui/1.0",
  "type": "card",
  "variant": "action",
  "header": {
    "icon": "phone",
    "title": "Incoming Call"
  },
  "content": {
    "type": "stack",
    "children": [
      {
        "type": "text",
        "variant": "title",
        "value": "Sarah Chen"
      },
      {
        "type": "text",
        "variant": "caption",
        "value": "Mobile • Last called 2 days ago"
      }
    ]
  },
  "actions": [
    {
      "type": "button",
      "variant": "secondary",
      "label": "Decline",
      "action": "decline_call"
    },
    {
      "type": "button",
      "variant": "primary",
      "label": "Answer",
      "action": "answer_call"
    }
  ]
}
```

### Agent Prompt for UI Generation

```markdown
You are generating UI for a minimal wearable display.

RULES:
1. Use only primitive and compound components from the design system
2. Prefer simplicity - show only essential information
3. Maximum 3 action buttons per view
4. Text should be terse - no full sentences
5. Use icons where possible instead of text labels
6. Output valid JSON matching the UI schema

CONTEXT:
- Display: 400x200 pixels
- Theme: wireframe (monochrome)
- User state: {context}

TASK: Generate UI for "{user_request}"
```

---

## 📏 Display Adaptations

### Display Size Matrix

| Display Type | Resolution | Max Elements | Typography Scale |
|--------------|------------|--------------|------------------|
| Ring display | 100x50 | 1 icon + 1 word | 0.6x |
| Glasses edge | 200x50 | 1 line text | 0.7x |
| Glasses center | 400x200 | 1 card | 1.0x |
| Watch | 400x400 | 2 cards | 1.0x |
| Phone | 1080x2400 | Full UI | 1.2x |

### Responsive Component Behavior

```yaml
timeline_list:
  phone:
    show_icons: true
    show_subtitles: true
    spacing: "loose"
  
  watch:
    show_icons: true
    show_subtitles: false
    spacing: "normal"
  
  glasses:
    show_icons: true
    show_subtitles: false
    spacing: "tight"
    max_items: 3
  
  ring:
    FALLBACK: show_count_only  # "3 events"
```

---

## ⚡ Animation Principles

### Micro-Animations (Always On)
- Fade in/out: 150ms ease-out
- Slide: 200ms ease-in-out
- Scale: 100ms ease-out

### Feedback Animations
- Button press: scale(0.95) → scale(1.0)
- Success: brief green flash
- Error: brief red flash + haptic

### Loading States
- Skeleton shimmer (described above)
- Pulsing dot for "thinking"
- Progress bar for known duration

### Performance Rules
- No animations on battery saver mode
- Reduce motion for accessibility setting
- Max 60fps, prefer 30fps for power saving

---

## 🎯 Example: Full UI Generation Flow

**User says**: "What's my schedule today?"

**Agent thinks**: Generate timeline list for today's calendar events

**Agent outputs**:
```json
{
  "type": "card",
  "variant": "flat",
  "header": {
    "icon": "calendar",
    "title": "Today",
    "subtitle": "Mon, Jan 27"
  },
  "content": {
    "type": "list",
    "variant": "timeline",
    "items": [
      {
        "time": "9:00",
        "text": "Team Standup",
        "status": "past"
      },
      {
        "time": "10:30",
        "text": "Client Call",
        "status": "current",
        "priority": "high"
      },
      {
        "time": "12:00",
        "text": "Lunch",
        "status": "upcoming"
      },
      {
        "time": "2:00",
        "text": "Design Review",
        "status": "upcoming",
        "priority": "high"
      }
    ]
  }
}
```

**Rendered on glasses**:
```
╔═══════════════════════════════════════╗
║  📅 TODAY  Mon, Jan 27                ║
╟───────────────────────────────────────╢
║  09:00  ○ Team Standup                ║
║  10:30  ▶ Client Call    ← NOW        ║
║  12:00  ○ Lunch                       ║
║  14:00  ● Design Review  HIGH         ║
╚═══════════════════════════════════════╝
```

---

*This design system enables agents to generate contextual, lightweight UI on demand without human designers.*
