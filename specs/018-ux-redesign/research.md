# Research: UX/UI Redesign — "Intelligent Warmth"

**Phase 0 output** | **Date**: 2026-03-19

## Research Tasks & Findings

### R1: shadcn/ui + Tailwind CSS 4 Compatibility

**Decision**: shadcn/ui is compatible with Tailwind CSS 4. Use `npx shadcn@latest init` which detects TW4 and configures accordingly.

**Rationale**: shadcn/ui generates components using CSS custom properties and the `cn()` utility (clsx + tailwind-merge). Tailwind CSS 4 uses `@theme` directive instead of `tailwind.config.ts` for design tokens. shadcn's init command detects the Tailwind version and adjusts output. The CSS variable-based theming approach is the same in both TW3 and TW4.

**Alternatives considered**: Manual component installation (copy-paste from shadcn source). Rejected — `npx shadcn add` handles dependency resolution and TW version detection automatically.

---

### R2: next-themes Integration with Next.js 16 App Router

**Decision**: Use `<ThemeProvider attribute="class" defaultTheme="system" enableSystem>` inside `<body>` in `app/layout.tsx`. Add `suppressHydrationWarning` to `<html>`.

**Rationale**: Verified via context7 (library ID: `/pacocoursey/next-themes`). The `attribute="class"` strategy adds/removes a `.dark` class on `<html>`, which Tailwind CSS 4 uses with its `darkMode: 'selector'` setting. `suppressHydrationWarning` prevents React from warning about the class mismatch during SSR→client hydration (next-themes injects the class via a script before React hydrates). `enableSystem` + `defaultTheme="system"` respects OS preference on first visit per FR-010.

**Alternatives considered**: `data-theme` attribute strategy. Rejected — Tailwind's dark mode utility classes (`dark:`) require class-based strategy. The `selector` approach in TW4 uses `[class~="dark"]` or `.dark` which works with `attribute="class"`.

---

### R3: shadcn Sidebar Integration Pattern

**Decision**: Use the compound component pattern: `SidebarProvider > Sidebar(collapsible="icon") > SidebarHeader + SidebarContent + SidebarFooter + SidebarRail`. Content goes in `SidebarInset`.

**Rationale**: Verified via shadcn-ui MCP (`get_component_examples("sidebar")` — 33 examples). The Sidebar component requires:
- `SidebarProvider` wrapping the entire layout (manages open/closed state)
- `Sidebar` with `collapsible="icon"` for icon-only collapsed mode
- `SidebarInset` wrapping the main content area
- `SidebarRail` for the hover-to-expand rail affordance
- `useSidebar()` hook for programmatic control (`state`, `open`, `setOpen`, `toggleSidebar`, `isMobile`)
- Specific CSS variables: `--sidebar-background`, `--sidebar-foreground`, `--sidebar-primary`, `--sidebar-primary-foreground`, `--sidebar-accent`, `--sidebar-accent-foreground`, `--sidebar-border`, `--sidebar-ring`
- Mobile behavior uses Sheet (already included as sidebar dependency)

**Key code pattern** (from shadcn-ui MCP example 3):
```tsx
<SidebarProvider>
  <AppSidebar />
  <main>
    <SidebarTrigger />
    {children}
  </main>
</SidebarProvider>
```

**Alternatives considered**: Custom sidebar with Sheet for mobile. Rejected — shadcn Sidebar handles desktop/mobile behavior, animation, keyboard shortcuts, and accessibility out of the box.

---

### R4: Provider Nesting Order in layout.tsx

**Decision**: `ThemeProvider` wraps `SidebarProvider`. Sonner `<Toaster />` is a sibling inside ThemeProvider, not nested in SidebarProvider.

**Rationale**: ThemeProvider must be the outermost provider (after `<body>`) because SidebarProvider's CSS variables depend on the current theme being resolved. If SidebarProvider wraps ThemeProvider, the sidebar renders before the theme is known, causing a flash of unstyled content. The Toaster from Sonner should be placed as a direct child of ThemeProvider so it inherits theme tokens.

**Layout hierarchy**:
```
<html suppressHydrationWarning>
  <body>
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
      <SidebarProvider defaultOpen={true}>
        <SidebarNav />
        <SidebarInset>
          <main>{children}</main>
        </SidebarInset>
      </SidebarProvider>
      <Toaster />
      <CommandPalette />
    </ThemeProvider>
  </body>
</html>
```

---

### R5: localStorage Chat Persistence Architecture

**Decision**: Single-conversation model. Store `ChatMessage[]` + `sessionId` under key `embedinator-chat-session`. Auto-evict on new session. Last-write-wins for multi-tab.

**Rationale**: Per clarification Q1 (keep only most recent conversation) and Q2 (last-write-wins, no cross-tab sync). The `useChatStorage` hook will:
1. On mount: read from localStorage and return messages + sessionId (or empty)
2. On message update: write current messages to localStorage
3. On new session start: clear previous data, write new sessionId
4. Provide a `clearChat()` function for the "Clear Chat" command

**Data shape**:
```typescript
interface StoredChat {
  sessionId: string;
  messages: ChatMessage[];
  updatedAt: number; // timestamp for debugging
}
```

**Storage key**: `embedinator-chat-session`
**Size estimate**: ~50 messages with citations ≈ 200KB, well within localStorage ~5MB limit.

**Alternatives considered**: sessionStorage (doesn't survive new tabs — rejected per Q2 answer "C"). IndexedDB (overkill for single conversation). No persistence (rejected per FR-019).

---

### R6: Color Token Migration Strategy

**Decision**: Replace hard-coded Tailwind gray/neutral classes with CSS variable utilities. Remove all `dark:` variant prefixes — the token system handles dark mode automatically.

**Rationale**: 15 of 22 frontend source files use hard-coded `text-gray-*`, `bg-gray-*`, `border-gray-*` with NO dark mode support. 7 additional files use `neutral-*` with `dark:` pairs. The migration replaces specific gray shades with semantic tokens (text-primary, text-muted, surface, border, accent) that resolve to different values in light vs dark via CSS custom properties.

**Migration table**:

| Old Pattern | New Token |
|-------------|-----------|
| `text-gray-900/800/700/600` | `text-[var(--color-text-primary)]` |
| `text-gray-500/400` | `text-[var(--color-text-muted)]` |
| `bg-white` | `bg-[var(--color-background)]` |
| `bg-gray-50/100` | `bg-[var(--color-surface)]` |
| `border-gray-200/300` | `border-[var(--color-border)]` |
| `*-blue-500/600` | `*-[var(--color-accent)]` |

**Verification**: After migration, `grep -r 'text-gray-\|bg-gray-\|border-gray-\|bg-white' frontend/components/ frontend/app/` should return zero results (excluding node_modules and test files).

---

### R7: Lucide React Icon Names for Sidebar

**Decision**: Use these lucide-react icons for the 5 sidebar navigation links:
- Chat: `MessageSquare`
- Collections: `FolderOpen`
- Documents: `FileText`
- Settings: `Settings`
- Observability: `Activity`

Additional icons: `Sun` and `Moon` for ThemeToggle, `PanelLeft` for SidebarTrigger, `Search` for CommandPalette, `Copy` for message copy button.

**Rationale**: These are standard lucide-react icon names that clearly communicate each section's purpose. All verified to exist in the lucide-react package.
