# Data Model: UX/UI Redesign — "Intelligent Warmth"

**Phase 1 output** | **Date**: 2026-03-19

## Entities

### Design Token

A named CSS custom property that defines a visual attribute and changes value based on active theme.

**Attributes**:
- `name` (string): CSS property name, e.g., `--color-background`
- `lightValue` (string): Hex value in light mode, e.g., `#faf9ff`
- `darkValue` (string): Hex value in dark mode, e.g., `#0d0c14`
- `category` (enum): `color | typography | spacing | sidebar`

**Relationships**: Referenced by all UI components via `var(--name)`. Defined in `globals.css`.

**Complete Token List (Obsidian Violet)**:

| Token | Light | Dark | Category |
|-------|-------|------|----------|
| `--color-background` | `#faf9ff` | `#0d0c14` | color |
| `--color-surface` | `#f4f0ff` | `#15122a` | color |
| `--color-border` | `#d1c4f5` | `#2a2352` | color |
| `--color-accent` | `#7c3aed` | `#a78bfa` | color |
| `--color-text-primary` | `#1e1b4b` | `#f5f3ff` | color |
| `--color-text-muted` | `#6b52b5` | `#9785d4` | color |
| `--color-success` | `#059669` | `#34d399` | color |
| `--color-warning` | `#d97706` | `#fbbf24` | color |
| `--color-destructive` | `#dc2626` | `#f87171` | color |
| `--sidebar-background` | `#f4f0ff` | `#15122a` | sidebar |
| `--sidebar-foreground` | `#1e1b4b` | `#f5f3ff` | sidebar |
| `--sidebar-primary` | `#7c3aed` | `#a78bfa` | sidebar |
| `--sidebar-primary-foreground` | `#faf9ff` | `#0d0c14` | sidebar |
| `--sidebar-accent` | `#ede9fe` | `#1e1744` | sidebar |
| `--sidebar-accent-foreground` | `#1e1b4b` | `#f5f3ff` | sidebar |
| `--sidebar-border` | `#d1c4f5` | `#2a2352` | sidebar |
| `--sidebar-ring` | `#7c3aed` | `#a78bfa` | sidebar |

---

### Theme Preference

User-controlled setting stored in browser, applied on every page load.

**Attributes**:
- `value` (enum): `dark | light | system`
- `storage`: localStorage (managed by next-themes)
- `key`: `theme` (next-themes default key)

**State Transitions**:
- Initial: `system` (derives from OS preference)
- User toggles → `dark` or `light` (persisted, overrides system)
- System changes → only affects if value is `system`

---

### Stored Chat Session

Chat messages persisted in localStorage for page refresh survival.

**Attributes**:
- `sessionId` (string): Backend session ID from NDJSON `session` event
- `messages` (ChatMessage[]): Array conforming to existing `ChatMessage` interface in `lib/types.ts`
- `updatedAt` (number): Unix timestamp of last write

**Validation Rules**:
- Maximum one stored conversation at a time
- Auto-evict previous when new session starts
- Must include: message content, citations, confidence scores, session ID

**State Transitions**:
- Empty → Active (first message sent)
- Active → Updated (new messages added during streaming)
- Active → Cleared (user triggers "New Chat" or "Clear Chat")
- Active → Evicted (new session starts, replacing previous)

**Storage key**: `embedinator-chat-session`

---

### Sidebar State

User's sidebar collapse/expand preference.

**Attributes**:
- `open` (boolean): `true` = expanded, `false` = collapsed (icon-only)
- `storage`: localStorage
- `key`: `sidebar-open`

**State Transitions**:
- Default: `true` (expanded on first visit)
- User clicks toggle → `!open` (persisted)
- Mobile viewport → hidden (overrides persisted state, uses Sheet overlay)

---

### Component Library Entry

A reusable UI primitive from shadcn/ui registry.

**Attributes**:
- `name` (string): Component name, e.g., `sidebar`, `badge`
- `path` (string): `components/ui/{name}.tsx`
- `dependencies` (string[]): Other shadcn components required
- `status` (enum): `installed | pending`

**21 Required Components**:
sidebar, sheet, command, badge, skeleton, card, button, input, textarea, select, tabs, table, dialog, popover, tooltip, scroll-area, progress, separator, dropdown-menu, sonner, breadcrumb
