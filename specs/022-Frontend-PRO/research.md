# Research: Frontend PRO (Spec 022)

**Feature**: Professional Agentic RAG Chat Interface
**Date**: 2026-03-21
**Sources**: 4 parallel research agents (shadcn MCP, Playwright web browsing, frontend code exploration, Context7 library docs) + Vercel React best practices skill (62 rules)

---

## Decision 1: Tailwind v4 CSS Scanning Fix Strategy

**Decision**: Use `@source` directive in `globals.css` to explicitly point Tailwind's scanner at component directories.

**Rationale**: Tailwind v4 eliminated `tailwind.config.ts` — configuration is now CSS-first. The project has no `@source` directive, causing the scanner to miss shadcn component utility classes. Adding `@source "../components/**/*.tsx"; @source "../app/**/*.tsx";` directly tells the scanner where to find classes.

**Alternatives Considered**:
| Alternative | Why Rejected |
|------------|-------------|
| Create `tailwind.config.ts` with `content` array | v3 pattern, defeats purpose of v4 migration. Would work but adds unnecessary config file. |
| Rely on Turbopack auto-scan | Current approach — it's failing. Auto-scan doesn't traverse the `@theme inline` variable chain reliably. |
| Run `npx @tailwindcss/upgrade` | Would reset globals.css structure. Too disruptive given the existing Obsidian Violet palette. |

**Verification**: After adding `@source`, build the project and grep compiled CSS for marker classes: `bg-sidebar`, `text-sidebar-foreground`, `data-\[state=open\]`, `group-data-\[collapsible=icon\]`.

---

## Decision 2: Token System — shadcn Standard + OKLCH

**Decision**: Remove all custom `var(--color-*)` tokens. Standardize on shadcn's built-in token system. Convert Obsidian Violet palette values to OKLCH color format. Keep only 2 custom tokens: `--warning` and `--success`.

**Rationale**: shadcn v4 uses 38 CSS variables covering background, foreground, card, popover, primary, secondary, muted, accent, destructive, border, input, ring, chart-1-5, and sidebar-*. The custom `--color-*` layer creates ambiguity (e.g., `--color-border` collides with `--border`). OKLCH is the v4 standard format for perceptually uniform colors.

**Alternatives Considered**:
| Alternative | Why Rejected |
|------------|-------------|
| Keep custom tokens alongside shadcn | Creates dual token system, ongoing maintenance burden, collision risk. |
| Use HSL values instead of OKLCH | HSL is v3 format. OKLCH provides perceptually uniform color manipulation. |
| Remove all custom tokens including warning/success | shadcn has no `--warning` or `--success` equivalents. These are application-specific. |

**Migration Map**:
| Old | New |
|-----|-----|
| `var(--color-background)` | `bg-background` / `var(--background)` |
| `var(--color-text-primary)` | `text-foreground` |
| `var(--color-text-muted)` | `text-muted-foreground` |
| `var(--color-accent)` | `bg-primary` / `text-primary` |
| `var(--color-border)` | `border-border` |
| `var(--color-surface)` | `bg-card` |
| `var(--color-destructive)` | `text-destructive` |

---

## Decision 3: Markdown Rendering Stack

**Decision**: `react-markdown` + `remark-gfm` + `rehype-highlight`. No `rehype-sanitize` needed.

**Rationale**: react-markdown strips raw HTML by default — XSS-safe out of the box. `rehype-highlight` is lighter and simpler than `react-syntax-highlighter` (operates at AST level, just needs CSS theme import). `remark-gfm` adds GitHub Flavored Markdown: tables, strikethrough, task lists, autolinks.

**Alternatives Considered**:
| Alternative | Why Rejected |
|------------|-------------|
| `react-syntax-highlighter` for code blocks | Heavier bundle (~100KB vs ~15KB for rehype-highlight). Requires custom `code` component wiring. |
| `rehype-raw` + `rehype-sanitize` | Unnecessary — react-markdown already blocks raw HTML. Adding `rehype-raw` would enable HTML passthrough, creating the very vulnerability we want to prevent. |
| `shiki` for syntax highlighting | Excellent output quality but 2-3x larger bundle. Overkill for this use case. |
| `marked` or `markdown-it` instead of react-markdown | Not React-native. Would require `dangerouslySetInnerHTML` which is an XSS risk. |

**Integration Pattern**:
```tsx
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import 'highlight.js/styles/github-dark.css'

<Markdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}
  components={markdownComponents}>
  {content}
</Markdown>
```

**Key Gotcha**: Custom components receive `{ node, children, ...htmlProps }`. Must destructure `node` before spreading onto DOM elements to avoid React warnings.

---

## Decision 4: Citation Display — Dual Strategy

**Decision**: Parse response text for `[N]` markers AND always show "N sources" collapsible section. Handle both cases: inline markers present or absent.

**Rationale**: The LLM's response text may or may not contain inline citation markers (`[1]`, `[2]`) depending on the prompt template. The `citation` NDJSON event always delivers structured citation data. By implementing both inline badges and a separate citations section, the UI works regardless of backend prompt changes.

**Alternatives Considered**:
| Alternative | Why Rejected |
|------------|-------------|
| Only inline badges (parse text) | Fails silently if backend doesn't emit markers. |
| Only "N sources" section (no inline) | Loses the Perplexity-style inline citation UX that makes RAG feel professional. |
| Modify backend prompts to guarantee markers | Violates "zero backend changes" constraint. |

---

## Decision 5: Chat Session Storage Architecture

**Decision**: Versioned localStorage schema (`embedinator-sessions:v1`) with migration from old single-session format. Maximum 50 sessions. Try-catch all access.

**Rationale**: localStorage is the only client-side persistence available without backend changes. Versioning enables schema evolution. 50-session limit with LRU eviction prevents storage exhaustion. Try-catch handles private browsing mode where localStorage throws.

**Alternatives Considered**:
| Alternative | Why Rejected |
|------------|-------------|
| IndexedDB | More complex API, overkill for structured text storage. |
| Server-side session storage | Requires backend changes (violates constraint). |
| No persistence (in-memory only) | Users expect chat history to survive page refreshes. |
| Unlimited sessions | 5-10MB localStorage limit could be reached with 100+ sessions of long conversations. |

**Schema**:
```typescript
// Key: "embedinator-sessions:v1"
interface SessionStore {
  version: 1;
  sessions: Record<string, ChatSessionData>;
}
interface ChatSessionData {
  id: string; title: string; messages: ChatMessage[];
  config: { collectionIds: string[]; llmModel: string; embedModel: string; };
  createdAt: string; updatedAt: string;
}
```

---

## Decision 6: Configuration Panel — Collapsible vs Sidebar

**Decision**: Replace 256px `ChatSidebar` aside with a collapsible config panel (shadcn `Collapsible`) that slides down from a 40px toolbar.

**Rationale**: Configuration is "set once, chat many times." A persistent sidebar wastes horizontal space for an interaction that happens once per session. The toolbar shows a compact summary; the full panel is available on demand. This pattern is used by Perplexity AI and Claude.ai.

**Alternatives Considered**:
| Alternative | Why Rejected |
|------------|-------------|
| Keep ChatSidebar but narrow it | Still wastes space. 256px → 200px doesn't solve the problem. |
| Modal dialog for config | Blocks the chat view entirely. Can't see messages while configuring. |
| Floating popover | Too small for multi-select checkboxes + 2 dropdowns. |
| Move config to settings page | Separates configuration from the context where it's needed. |

---

## Decision 7: Textarea Auto-Resize

**Decision**: Use native CSS `field-sizing-content` property (already in the installed `textarea.tsx`). No custom hook needed.

**Rationale**: The shadcn v4 `Textarea` component already includes `field-sizing-content` in its CSS. This is a modern CSS feature that automatically adjusts height based on content. Just add `min-h-10 max-h-[120px]` constraints for 1-to-5-row range.

**Alternatives Considered**:
| Alternative | Why Rejected |
|------------|-------------|
| Custom `useAutoResize` hook with `scrollHeight` | Unnecessary JavaScript for something CSS handles natively. |
| Fixed height with scroll | Poor UX — user can't see what they're typing in long messages. |

---

## Decision 8: Radix vs Base UI Components

**Decision**: Keep the current mixed approach. Use `render` prop for Base UI components, `asChild` for Radix components. Don't force-migrate.

**Rationale**: The project has both Radix (`dialog`, `select`) and Base UI (everything else) components. Force-migrating dialog/select to Base UI would regenerate those components, potentially breaking existing functionality. The two patterns coexist without conflict.

**Alternatives Considered**:
| Alternative | Why Rejected |
|------------|-------------|
| Migrate all to Base UI | Risk of breaking dialog/select behavior. Not worth the churn for Spec 22. |
| Migrate all to Radix | Would lose v4 features and Base UI improvements. |
| Remove all Radix deps | Some components still import from Radix. Would break. |

---

## Decision 9: Syntax Highlighting Theme — Dark/Light Mode

**Decision**: Import `highlight.js/styles/github-dark.css` for dark mode. Override key classes in light mode via custom CSS.

**Rationale**: The app uses Obsidian Violet with dark/light toggle. A single highlight.js theme works in dark mode. For light mode, override the 5-6 key `hljs-*` classes to use lighter colors. This avoids dynamic CSS imports and keeps bundle size minimal.

**Alternatives Considered**:
| Alternative | Why Rejected |
|------------|-------------|
| Dynamic theme import based on active mode | Complexity of conditional CSS loading. Flash of wrong theme during hydration. |
| Two separate CSS files with media query | Would need `@media (prefers-color-scheme)` but we use class-based dark mode, not media. |
| Shiki with theme switching | Much larger bundle. Shiki themes are ~50KB each. |

---

## Decision 10: Ingestion Progress — Enhance Existing vs Create New

**Decision**: Enhance existing `DocumentUploader.tsx` progress polling. Add file type icons, file size display, and multi-file queue UI.

**Rationale**: `DocumentUploader` already has 2-second polling via `getIngestionJob()` and uses shadcn `Progress` with the render function pattern. The core polling logic is correct — only the visual layer needs enhancement.

**Alternatives Considered**:
| Alternative | Why Rejected |
|------------|-------------|
| Create separate `IngestionProgress.tsx` from scratch | Duplicates existing polling logic. Higher risk of inconsistency. |
| Use SWR for polling (replace current approach) | Current approach works. Switching to SWR adds migration risk for no functional gain. |

**Note**: While the plan context document proposed a separate `IngestionProgress.tsx` component, research found the core functionality already exists. The new component will be a visual wrapper around the existing polling logic, not a replacement.

---

## Decision 11: NDJSON Stream Event Types

**Decision**: Map NDJSON `status` events (with node names) to human-readable stage labels. Event type for text tokens is `token` (not `chunk`).

**Rationale**: The backend sends `{ type: "token", text: "..." }` for streaming text. The context document (22-specify.md) incorrectly referenced this as `chunk`. Corrected via frontend code exploration agent reading `useStreamChat.ts`.

**Event type mapping** (confirmed from codebase):
```
status → Pipeline stage names (intent_analysis, research, etc.)
token  → Streaming text content
clarification → Agent needs clarification
citation → Source references
meta_reasoning → Strategy information
confidence → Score (0-100)
groundedness → Claim verification stats
done → Completion with latency/trace_id
error → Error with message/code
```
