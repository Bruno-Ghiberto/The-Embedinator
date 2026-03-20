# A3 — Wave 3 — frontend-architect (Sonnet)

## CALLSIGN: CHAT SPECIALIST

## MISSION

You are a Wave 3 frontend-architect running in PARALLEL with A4–A7. You own the Chat page — the primary user surface and most complex page in the application. Your mission: redesign the chat experience to surface AI intelligence through streaming cursors, citation chips, confidence badges, meta-reasoning indicators, and localStorage persistence. This is the highest-complexity Wave 3 assignment.

Do NOT start until the orchestrator signals that Wave 2 gate passed (foundation is verified).

## INTEL — Read Before Starting

1. Your instruction file (this file)
2. `specs/018-ux-redesign/tasks.md` — your tasks: T016–T027
3. `specs/018-ux-redesign/spec.md` — FR-012 through FR-019 (your scope)
4. `specs/018-ux-redesign/contracts/ui-components.md` — useChatStorage hook contract
5. `specs/018-ux-redesign/data-model.md` — StoredChat entity definition
6. `Docs/PROMPTS/spec-18-UX_UI-Redesign/18-implement.md` — Color Migration Guide (CRITICAL)

Also read the CURRENT source of each file before modifying it:
- `frontend/components/ChatPanel.tsx`
- `frontend/components/ChatInput.tsx`
- `frontend/components/ChatSidebar.tsx`
- `frontend/components/CitationTooltip.tsx`
- `frontend/components/ConfidenceIndicator.tsx`
- `frontend/components/ModelSelector.tsx`
- `frontend/app/chat/page.tsx`
- `frontend/hooks/useStreamChat.ts`
- `frontend/lib/types.ts` (read only — DO NOT MODIFY)

## ASSIGNED TASKS

T016 through T027 (12 tasks).

---

**T016** — Create `frontend/hooks/useChatStorage.ts`

New hook for localStorage chat persistence (FR-019). Contract in `contracts/ui-components.md`.

```typescript
interface StoredChat {
  sessionId: string;
  messages: ChatMessage[];  // from @/lib/types
  updatedAt: number;
}
```

- Key: `embedinator-chat-session`
- `saveMessages(msgs: ChatMessage[], sessionId: string)` — writes to localStorage. If sessionId differs from stored, auto-evict previous.
- `clearChat()` — removes localStorage entry entirely.
- Returns: `{ storedMessages, storedSessionId, saveMessages, clearChat }`
- Handle SSR: check `typeof window !== "undefined"` before localStorage access.
- Last-write-wins for multi-tab (no cross-tab sync).

**T017** — Redesign message bubbles in `frontend/components/ChatPanel.tsx`

Read the current file. Then restyle:
- User messages: right-aligned, `bg-[var(--color-accent)]` background, white text
- Assistant messages: left-aligned, `bg-[var(--color-surface)]` background
- Use shadcn `ScrollArea` for the message container (replace raw `overflow-y-auto`)
- Replace ALL hard-coded `neutral-*` / `gray-*` classes with design tokens
- Remove ALL `dark:` variant classes
- **IMPORTANT**: Preserve existing `onGroundedness` rendering — do NOT remove groundedness data display

**T018** — Add blinking caret cursor + stage-status indicator

In `ChatPanel.tsx`:
- Add a CSS `@keyframes blink` animation: `opacity 0→1→0` at 530ms interval
- During streaming (`isStreaming`), render a `<span>` with the blink animation as the cursor
- Add a small shadcn `Badge` showing the current pipeline node name (from the `onStatus` callback data). Show "Retrieving", "Reranking", "Generating" etc.

**T019** — Migrate `frontend/components/CitationTooltip.tsx`

Read current file. Replace raw Radix Tooltip with:
- shadcn `Badge` for each citation chip (small, clickable)
- shadcn `Popover` for expansion showing: full citation text, source document name, relevance score
- Migrate all color classes to design tokens. Remove `dark:` variants.

**T020** — Migrate `frontend/components/ConfidenceIndicator.tsx`

Read current file. Replace raw Radix Tooltip with:
- Colored shadcn `Badge`: green (`--color-success`) for score >= 70, yellow/amber (`--color-warning`) for 40-69, red (`--color-destructive`) for < 40
- shadcn `Popover` for expandable 5-signal confidence breakdown
- Migrate all color classes to design tokens. Remove `dark:` variants.

**T021** — Add meta-reasoning indicator in `ChatPanel.tsx`

When `onMetaReasoning` callback fires (provides `strategies_attempted` array):
- Render a small `Badge` variant="outline" showing "Meta-Reasoning" label
- Inside or on hover: show the list of strategies attempted

**T022** — Add clarification card in `ChatPanel.tsx`

When `onClarification` callback fires (provides `question` string):
- Render a styled shadcn `Card` in the message stream
- Card contains the clarification question text and a response CTA area

**T023** — Add copy-to-clipboard button in `ChatPanel.tsx`

For each assistant message:
- On hover, show a small copy icon button (lucide `Copy` icon)
- On click, copy message text content to clipboard via `navigator.clipboard.writeText()`
- Brief visual feedback (icon changes to checkmark for 2 seconds)

**T024** — Create chat empty state in `ChatPanel.tsx`

When `messages.length === 0` (replace current minimal empty state):
- Centered greeting: "What would you like to explore?"
- 3-4 clickable starter question badges/buttons
- Clicking a starter calls the `onSubmit` handler with that question text

**T025** — Integrate useChatStorage with `frontend/app/chat/page.tsx`

Read current ChatPage. Then:
- Import and use `useChatStorage` hook
- On mount: if stored messages exist, hydrate them into state
- On message update (from useStreamChat): save to localStorage
- On new session: auto-evict previous
- Wire "Clear Chat" to `clearChat()` — this will also be used by A8's CommandPalette

**T026** — Restyle `frontend/components/ChatSidebar.tsx` AND `frontend/components/ModelSelector.tsx`

Read both files. Then:
- Replace raw Radix Select with shadcn `Select` component in both files
- ModelSelector is shared by ChatSidebar and Settings page — restyle it here
- Migrate all `neutral-*` / `gray-*` color classes to design tokens
- Remove all `dark:` variant classes

**T027** — Restyle `frontend/components/ChatInput.tsx`

Read current file. Then:
- Use shadcn `Textarea` (instead of raw `<textarea>`)
- Use shadcn `Button` (instead of raw `<button>`)
- Migrate all color classes to design tokens. Remove `dark:` variants.

---

## RULES OF ENGAGEMENT

- Do NOT modify `frontend/lib/types.ts` or `frontend/lib/api.ts` — ever.
- Do NOT modify `frontend/hooks/useStreamChat.ts` — integrate with it, don't rewrite it.
- Do NOT modify `frontend/app/layout.tsx` — that's A1/A8's territory.
- Do NOT touch any Collection, Document, Settings, or Observability component.
- Use `cn()` from `@/lib/utils` for all className conditionals.
- Use `"use client"` directive on any component that uses hooks or browser APIs.
- After completing all tasks, verify: `grep -r 'text-gray-\|bg-gray-\|border-gray-\|bg-white\|dark:' frontend/components/Chat*.tsx frontend/components/CitationTooltip.tsx frontend/components/ConfidenceIndicator.tsx frontend/components/ModelSelector.tsx` returns ZERO results.

## COMPLETION SIGNAL

"A3 COMPLETE. Chat page redesigned — all 12 tasks done. Zero hard-coded gray classes in chat components."
