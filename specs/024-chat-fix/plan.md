# Implementation Plan: Chat & Agentic RAG Pipeline Fix

**Branch**: `024-chat-fix` | **Date**: 2026-03-27 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/024-chat-fix/spec.md`

## Summary

Fix 5 bugs (BUG-013 through BUG-017) that break the chat pipeline end-to-end. The backend produces correct NDJSON — all issues are in the frontend rendering chain (P0), sidebar navigation (P1), backend parameter regression (P1), and citation deduplication (P2). The approach is investigative: observe in browser, research stack patterns, diagnose, apply targeted fix, verify.

## Technical Context

**Language/Version**: Python 3.14+ (backend), TypeScript 5.7 (frontend)
**Primary Dependencies**: FastAPI >=0.135, LangGraph >=1.0.10, Next.js 16, React 19, SWR 2, shadcn/ui v4
**Storage**: SQLite WAL (`data/embedinator.db`), Qdrant (vectors), localStorage (frontend sessions)
**Testing**: Manual browser testing via MCP tools (chrome-devtools, playwright), curl verification
**Target Platform**: Docker Compose (4 services: qdrant, ollama, backend, frontend) on Linux
**Project Type**: Web application (Python backend + Next.js frontend)
**Performance Goals**: Chat response visible within 5s of backend completion; sidebar updates within 3s
**Constraints**: No new dependencies, no API contract changes, no new components, Makefile sacred
**Scale/Scope**: 5 bugs, 17 functional requirements, 7 success criteria

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Local-First Privacy | PASS | No cloud dependencies added. All fixes are local code changes. |
| II. Three-Layer Agent Architecture | PASS | No graph structure changes. BUG-016 fixes a parameter on the existing CallLimitCallback. |
| III. Retrieval Pipeline Integrity | PASS | No changes to chunking, hybrid search, or reranking. BUG-017 dedup is at the NDJSON emission layer, not the retrieval layer. |
| IV. Observability from Day One | PASS | Trace recording is unaffected. Confidence display (FR-004) already exists — just needs streaming to complete for it to render. |
| V. Secure by Design | PASS | No credential handling changes. No new endpoints. |
| VI. NDJSON Streaming Contract | PASS | Event types unchanged. BUG-017 dedup changes the citation *content* (removes duplicates) but not the *schema*. |
| VII. Simplicity by Default | PASS | Removing `useChatStorage` (legacy dual system) reduces complexity. No new abstractions introduced. |
| VIII. Cross-Platform Compatibility | PASS | All changes are in Python and TypeScript — no platform-specific code. Docker deployment unaffected. |

**Gate result**: ALL PASS — no violations. Proceed to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/024-chat-fix/
├── plan.md              # This file
├── research.md          # Phase 0 output — no unknowns (all verified empirically)
├── data-model.md        # Phase 1 output — key entities and state flows
├── quickstart.md        # Phase 1 output — verification commands
├── contracts/           # Phase 1 output — NDJSON event contract (reference only)
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
backend/
├── api/
│   └── chat.py              # BUG-016 (CallLimitCallback), BUG-017 (citation dedup)
└── agent/
    └── state.py             # Citations reducer (read-only audit)

frontend/
├── app/
│   └── chat/
│       └── page.tsx         # BUG-013 (state race conditions), BUG-014 (?new=1 handler)
├── hooks/
│   ├── useStreamChat.ts     # BUG-013 (streaming callbacks)
│   ├── useChatHistory.ts    # BUG-015 (session persistence)
│   └── useChatStorage.ts    # BUG-013 (candidate for removal — legacy dual system)
├── lib/
│   └── api.ts               # BUG-013 (NDJSON fetch + parse, res.body null guard)
└── components/
    ├── SidebarNav.tsx        # BUG-014 (New Chat button)
    ├── ChatPanel.tsx         # BUG-013 (message rendering)
    ├── ChatMessageBubble.tsx # BUG-013 (bubble rendering)
    ├── ChatInput.tsx         # Reference only
    └── ChatToolbar.tsx       # Reference only
```

**Structure Decision**: Existing web application structure. No new files or directories created. All changes are modifications to existing files.

## Agent Team

5 agents with strict role separation. Only A1 and A2 write code.

| Agent | Role | Model | MCP Tools | Writes Code? |
|-------|------|-------|-----------|--------------|
| **Orchestrator** | Coordinator — diagnoses, designs fixes, assigns work, gates phases | Opus 4.6 | All (coordination only) | NO |
| **Navigator** | Frontend tester — navigates browser, observes DOM/console/network, verifies fixes | Sonnet 4.6 | `chrome-devtools`, `playwright` | NO |
| **Researcher** | Documentation investigator — official docs, best practices, known issues | Sonnet 4.6 | `langchain-docs`, `context7`, `shadcn-ui`, WebSearch, WebFetch | NO |
| **A1** | Frontend Fixer — applies code changes to `frontend/` ONLY | Sonnet 4.6 | Read, Edit, Write, Grep, Glob | YES (frontend only) |
| **A2** | Backend Fixer — applies code changes to `backend/` ONLY | Sonnet 4.6 | Read, Edit, Write, Grep, Glob | YES (backend only) |

### Role Boundaries (HARD RULES)

- **Orchestrator** NEVER reads source files or writes code. Coordinates and synthesizes.
- **Navigator** NEVER modifies files. Observes only through browser automation MCPs.
- **Researcher** NEVER modifies files. Searches documentation and returns findings.
- **A1** ONLY modifies files under `frontend/`. Receives specific fix instructions from Orchestrator.
- **A2** ONLY modifies files under `backend/`. Receives specific fix instructions from Orchestrator.
- **User** rebuilds Docker containers manually after each phase.

### Navigator MCP Reference

**Chrome DevTools**: `list_pages`, `select_page`, `navigate_page`, `take_screenshot`, `evaluate_script`, `list_console_messages`, `get_console_message`, `list_network_requests`, `get_network_request`, `click`, `fill`, `type_text`, `press_key`

**Playwright**: `browser_navigate`, `browser_snapshot`, `browser_click`, `browser_fill_form`, `browser_type`, `browser_console_messages`, `browser_network_requests`, `browser_take_screenshot`

**Base URL**: `http://localhost:3000`

### Researcher MCP Reference

**langchain-docs** (`search_docs_by_lang_chain`): LangGraph streaming, Send() fan-out, callback patterns

**context7** (`resolve-library-id` → `query-docs`): Next.js 16, React 19, SWR 2, FastAPI, Pydantic

**shadcn-ui** (`list_shadcn_components`, `get_component_details`): Sidebar, Collapsible, Dialog APIs

**Vercel React Best Practices** (local skill at `.claude/skills/vercel-react-best-practices/`):
- `rules/rerender-functional-setstate.md` — functional setState (onToken callback pattern)
- `rules/rerender-derived-state-no-effect.md` — avoid derived state in effects
- `rules/rerender-move-effect-to-event.md` — move logic from effects to handlers
- `rules/client-localstorage-schema.md` — localStorage schema management
- `rules/rendering-hydration-no-flicker.md` — hydration without flicker

**WebSearch / WebFetch**: Known issues with Next.js standalone + streaming, React 19 ReadableStream

## Phase Execution Plan

### Phase 1: BUG-013 — Chat Response Never Renders (P0-CRITICAL)

**Goal**: Diagnose and fix why the browser doesn't render chat responses.

| Step | Agent | Action |
|------|-------|--------|
| 1.1 | Navigator | Open `/chat`, select collection, send message, observe: console errors, network POST status/body, DOM state. Screenshot before and after. |
| 1.2 | Researcher | (if needed) Investigate: Next.js 16 standalone streaming through rewrites, React 19 ReadableStream fetch patterns, `res.body` null in standalone mode. Load Vercel best practices for functional setState and hydration. |
| 1.3 | Orchestrator | Synthesize Navigator + Researcher findings. Diagnose root cause from 4 suspects: (1) res.body null, (2) competing setMessages, (3) useChatStorage hydration race, (4) React strict mode double-invocation. |
| 1.4 | Orchestrator | Write specific fix instructions for A1. |
| 1.5 | A1 | Apply fix to: `useStreamChat.ts`, `page.tsx`, `api.ts`, `useChatStorage.ts`. |
| 1.6 | User | Rebuild frontend: `docker compose build frontend && docker compose up -d frontend` |
| 1.7 | Navigator | Re-test: send message, verify response text renders. |
| Gate 1 | Orchestrator | PASS if response renders. FAIL → loop to 1.1. |

**Suspect investigation priorities**:

1. **Suspect #1 — res.body null**: `streamChat` in `api.ts:147` uses `res.body!.getReader()`. If `res.body` is null (possible in Next.js standalone), the non-null assertion crashes silently in the `.then()` chain. The outer `.catch()` only catches non-AbortError.

2. **Suspect #2 — Competing setMessages**: `page.tsx` has 3+ useEffect hooks calling `setMessages`. If any fires after `sendMessage` creates the assistant placeholder, it overwrites the array. The `onToken` callback's `prev.map(msg => msg.id === assistantId)` finds no match and silently does nothing.

3. **Suspect #3 — useChatStorage hydration race**: Hydration effect (line 124-129) runs on mount with `storedMessages` from legacy localStorage. If non-empty, it replaces messages. Combined with Suspect #2 — the dual localStorage system is the prime suspect.

4. **Suspect #4 — React strict mode**: Docker may run in dev mode (double effect invocation). Two assistant placeholders → onToken updates wrong one.

**Likely fix direction**: Remove `useChatStorage` (legacy dual system), guard hydration effects, add `res.body` null check.

---

### Phase 2: BUG-014 + BUG-015 — Sidebar Navigation (P1-HIGH)

**Goal**: Make sidebar "New Chat" clear state and conversation history load correctly.

| Step | Agent | Action |
|------|-------|--------|
| 2.1 | Navigator | Test: click sidebar "New Chat" (observe clearing), send message (observe sidebar title/count), click conversation entry (observe message loading). |
| 2.2 | Orchestrator | Confirm BUG-014 root cause (sidebar button only navigates, doesn't clear state). Design URL-param signaling fix. Check if BUG-015 was resolved by Phase 1. |
| 2.3 | A1 | Apply fix: `SidebarNav.tsx` (navigate with `?new=1`), `page.tsx` (detect `?new=1`, trigger handleNewChat, remove param). |
| 2.4 | User | Rebuild frontend. |
| 2.5 | Navigator | Re-test all sidebar interactions. |
| Gate 2 | Orchestrator | PASS if sidebar works. FAIL → loop to 2.1. |

**Fix approach**: URL-based signaling — `router.push("/chat?new=1")`. `ChatPageContent` detects `searchParams.get("new")`, calls `handleNewChat()`, then `router.replace("/chat")` to clean the param.

---

### Phase 3: BUG-016 + BUG-017 — Backend Fixes (P1-HIGH + P2-MEDIUM)

> **Runs in PARALLEL with Phase 2** — different layer (backend), different agent (A2), no file conflicts.

**Goal**: Fix CallLimitCallback limits and deduplicate citations.

| Step | Agent | Action |
|------|-------|--------|
| 3.1 | A2 | Apply BUG-016 fix: remove explicit args from `CallLimitCallback()` at `chat.py:156`. Apply BUG-017 fix: add `passage_id` dedup before citation emission at `chat.py:211-217`. Audit `state.py` citations reducer. |
| 3.2 | User | Rebuild backend: `docker compose build backend && docker compose up -d backend` |
| 3.3 | Orchestrator | Curl test: verify no `call_limit_llm_exceeded` warnings, verify unique citations. |
| Gate 3 | Orchestrator | PASS if curl shows correct limits and unique citations. |

---

### Phase 4: End-to-End Verification

**Goal**: Verify all 7 success criteria with fully rebuilt containers.

| Step | Agent | Action |
|------|-------|--------|
| 4.1 | User | Full rebuild: `docker compose build backend frontend && docker compose up -d` |
| 4.2 | Navigator | Execute SC verification matrix (all 7 SCs). |
| 4.3 | Orchestrator | Compile pass/fail report. If any fail, loop to relevant phase. |

**SC Verification Matrix**:

| SC | Test | Expected |
|----|------|----------|
| SC-001 | Select collection, send message | Response text renders in chat panel |
| SC-002 | Click sidebar "New Chat" | Chat panel clears to empty state |
| SC-003 | After completed chat, check sidebar | Conversation title = first message, correct count |
| SC-004 | Click sidebar conversation | Messages load into chat panel |
| SC-005 | Send complex query, check backend logs | Zero "call limit exceeded" warnings |
| SC-006 | Curl chat, inspect citation event | Zero duplicate passage_ids |
| SC-007 | All above | All 5 bugs confirmed resolved |

## Operational Protocols

### Makefile SACRED
Do NOT modify the Makefile. Verify at every gate: `git diff Makefile` must show no changes.

### Docker Rebuild Protocol
1. Orchestrator tells user which service(s) to rebuild
2. User runs: `docker compose build <service> && docker compose up -d <service>`
3. Navigator verifies in browser OR Orchestrator verifies via curl
4. Agents MUST NOT run build commands

### Verification Commands

```bash
# Backend health
curl -s http://localhost:8000/api/health | python3 -m json.tool

# Chat API (direct)
curl -s -N -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "hello", "collection_ids": ["07d3308c-5bb9-49a8-bcf7-5edafbcb8dca"], "llm_model": "qwen2.5:7b"}' \
  | head -10

# Chat API (through proxy)
curl -s -N -X POST http://localhost:3000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "hello", "collection_ids": ["07d3308c-5bb9-49a8-bcf7-5edafbcb8dca"], "llm_model": "qwen2.5:7b"}' \
  | head -10

# Check call limit warnings
docker compose logs backend --tail=50 2>&1 | rg "call_limit"

# Check Makefile unchanged
git diff Makefile
```

### Git Protocol
- Branch: `024-chat-fix`
- Conventional commits only (no Co-Authored-By)
- Commit after each phase, not after each file
- Format: `fix(frontend): resolve chat response rendering (BUG-013)`
