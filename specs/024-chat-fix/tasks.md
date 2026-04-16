# Tasks: Chat & Agentic RAG Pipeline Fix

**Input**: Design documents from `specs/024-chat-fix/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/, quickstart.md

**Tests**: No automated test tasks — verification is done via Navigator (browser MCP) and curl commands.

**Organization**: Tasks are grouped by user story with investigative steps preceding fixes. The agent team (Orchestrator, Navigator, Researcher, A1, A2) is referenced per task.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions
- **[Agent]**: Which agent executes this task (Navigator, Researcher, A1, A2, Orchestrator, User)

---

## Phase 1: Setup (Environment Verification)

**Purpose**: Confirm Docker environment is running and baseline state is documented.

- [x] T001 [Orchestrator] Verify all 4 Docker containers are healthy: `docker compose ps` must show backend, frontend, ollama, qdrant all healthy
- [x] T002 [Orchestrator] Verify backend health endpoint: `curl -s http://localhost:8000/api/health` must return `{"status": "healthy"}`
- [x] T003 [Orchestrator] Verify at least one collection exists with documents: `curl -s http://localhost:8000/api/collections` must return non-empty `collections` array — **ACTUAL ID: `0ea45e41-795b-409c-b987-dac21de28dbe`**
- [x] T004 [Orchestrator] Verify backend NDJSON streaming works — confirmed NDJSON lines with `{"type":"session"}`, `{"type":"status"}`
- [x] T005 [Orchestrator] Verify Makefile is unchanged: `git diff Makefile` produces no output

**Checkpoint**: Environment ready — investigation can begin.

---

## Phase 2: Investigation (Bug Observation + Research)

**Purpose**: Observe the bugs in the browser and research stack patterns. This phase produces the diagnostic evidence that informs fix instructions.

### Navigator Observation

- [ ] T006 [Navigator] Navigate to `http://localhost:3000/chat` and take screenshot of initial state
- [ ] T007 [Navigator] Select the `arca-backend-test` collection (click collection card or use config panel)
- [ ] T008 [Navigator] Type "What topics does this collection cover?" in chat input and click Send
- [ ] T009 [Navigator] Wait 10 seconds, then collect: console messages (`list_console_messages`), network requests (`list_network_requests`), screenshot of chat panel
- [ ] T010 [Navigator] Inspect the POST `/api/chat` network request: check status code, response headers (`Content-Type`), and response body (does it contain NDJSON lines?)
- [ ] T011 [Navigator] Run `evaluate_script` in browser: `JSON.stringify({msgCount: document.querySelectorAll('[class*="rounded-2xl"]').length, hasAssistantContent: document.querySelector('[class*="prose-sm"]')?.textContent?.length || 0, isStreaming: document.querySelector('[class*="animate-"]') !== null})`
- [ ] T012 [Navigator] Run `evaluate_script` in browser: `JSON.stringify({legacyStorage: localStorage.getItem('embedinator-chat-session')?.length || 0, sessionStorage: localStorage.getItem('embedinator-sessions:v1')?.length || 0})`
- [ ] T013 [Navigator] Report ALL findings to Orchestrator: fetch status, response body, console errors, DOM state, localStorage state

### Researcher Investigation (dispatched by Orchestrator based on T013 findings)

- [ ] T014 [P] [Researcher] Research Next.js 16 standalone streaming through rewrites: use `context7` to query Next.js docs for `rewrites` + `streaming` + `ReadableStream` behavior in `output: "standalone"` mode
- [ ] T015 [P] [Researcher] Research React 19 fetch ReadableStream patterns: use WebSearch for "React 19 fetch ReadableStream getReader NDJSON streaming" and check for known issues
- [ ] T016 [P] [Researcher] Load Vercel React best practices: read `.claude/skills/vercel-react-best-practices/rules/rerender-functional-setstate.md`, `rules/rerender-derived-state-no-effect.md`, `rules/rerender-move-effect-to-event.md`, `rules/client-localstorage-schema.md`, `rules/rendering-hydration-no-flicker.md`
- [ ] T017 [Orchestrator] Synthesize Navigator (T013) + Researcher (T014-T016) findings. Diagnose BUG-013 root cause. Write specific fix instructions for A1.

**Checkpoint**: Root cause diagnosed — fix instructions ready for A1.

---

## Phase 3: User Story 1 — Chat Response Rendering (Priority: P1) — BUG-013

**Goal**: Make the assistant's response text appear in the chat panel when the backend streams NDJSON.

**Independent Test**: Send a chat message with a collection selected → response text appears in the chat panel.

**Agent**: A1 (Frontend Fixer)

### Implementation for User Story 1

- [ ] T018 [US1] Add null guard for `res.body` in `frontend/lib/api.ts` — if `res.body` is null after fetch, call `callbacks.onError("Stream body unavailable", "STREAM_ERROR")` instead of crashing
- [ ] T019 [US1] Add error handling in `streamChat` `.then()` chain in `frontend/lib/api.ts` — wrap the reader loop in try/catch so JSON parse errors or reader failures are caught and forwarded to `callbacks.onError`
- [ ] T020 [US1] Audit all `useEffect` hooks in `frontend/app/chat/page.tsx` that call `setMessages` — identify which effects could fire after `sendMessage` and overwrite the assistant placeholder
- [ ] T021 [US1] Remove `useChatStorage` hook usage from `frontend/app/chat/page.tsx` — delete the `useChatStorage` import, the `storedMessages`/`storedSessionId`/`saveMessages`/`clearChat` destructuring, and ALL useEffect hooks that reference them (hydration effect lines ~124-129, save effect lines ~132-141)
- [ ] T022 [US1] Delete `frontend/hooks/useChatStorage.ts` — this is the legacy single-session system replaced by `useChatHistory`
- [ ] T023 [US1] Update `handleNewChat` in `frontend/app/chat/page.tsx` to remove `clearChat()` call (no longer exists after T021)
- [ ] T024 [US1] Guard the `activeSession` hydration effect in `frontend/app/chat/page.tsx` (lines ~101-121) — add a check that prevents overwriting messages if streaming is active (`isStreaming` ref or similar guard)
- [ ] T025 [US1] Verify `useStreamChat.sendMessage` callback closures in `frontend/hooks/useStreamChat.ts` — ensure `assistantId` is captured correctly in `onToken` callback and React strict mode double-invocation doesn't create duplicate placeholders

### Gate 1: Verify BUG-013 Fix

- [ ] T026 [User] Rebuild frontend: `docker compose build frontend && docker compose up -d frontend`
- [ ] T027 [Navigator] Navigate to `http://localhost:3000/chat`, select collection, send message — verify response text appears in chat panel (not skeleton bars)
- [ ] T028 [Navigator] Verify streaming cursor appears during response and disappears after completion
- [ ] T029 [Navigator] Verify confidence meter appears after response completes
- [ ] T030 [Navigator] Check console for errors — must be zero JavaScript errors related to streaming
- [ ] T030b [Navigator] Verify error path: deselect all collections, send a message — verify error message renders in chat panel with a "Retry" button (FR-005)
- [ ] T031 [Orchestrator] Gate 1 decision: PASS if T027-T030b all pass. FAIL → loop back to T017 with new Navigator observations.

**Checkpoint**: Chat response renders — US1 complete. Proceed to US2/US3 + US4 in parallel.

---

## Phase 4: User Story 2 + User Story 3 — Sidebar Navigation (Priority: P2) — BUG-014, BUG-015

**Goal**: Make sidebar "New Chat" clear state properly (BUG-014) and conversation history entries work correctly (BUG-015).

**Independent Test**: Click sidebar "New Chat" → panel clears. Complete a chat → sidebar shows correct title/count. Click sidebar entry → messages load.

**Agent**: A1 (Frontend Fixer)

> **Runs in PARALLEL with Phase 5** — A1 works on frontend, A2 works on backend simultaneously.

### Implementation for User Story 2 (BUG-014)

- [ ] T032 [P] [US2] Modify sidebar "New Chat" button in `frontend/components/SidebarNav.tsx` — change `onClick={() => router.push("/chat")}` to `onClick={() => router.push("/chat?new=1")}`
- [ ] T033 [US2] Add `?new=1` detection in `frontend/app/chat/page.tsx` — in the component body, check `searchParams.get("new")`, if truthy call `handleNewChat()` and then `router.replace("/chat", { scroll: false })` to clear the param

### Implementation for User Story 3 (BUG-015) — Verify

- [ ] T034 [US3] Verify BUG-015 is resolved by Phase 3 fixes — after BUG-013 is fixed, streaming completes correctly, which triggers `syncMessages` (page.tsx lines ~145-157), which updates the session title and message count. Navigator confirms in Gate 2.
- [ ] T035 [US3] If BUG-015 persists: audit `syncMessages` call in `frontend/app/chat/page.tsx` — ensure `prevStreamingRef` transition detection works and `syncMessages` is called with current messages after streaming completes

### Gate 2: Verify BUG-014 + BUG-015

- [ ] T036 [User] Rebuild frontend: `docker compose build frontend && docker compose up -d frontend`
- [ ] T037 [Navigator] With an active conversation visible, click sidebar "New Chat" — verify chat panel clears to empty state
- [ ] T038 [Navigator] Send a new message and wait for response — verify conversation appears in sidebar with first user message as title and correct message count
- [ ] T039 [Navigator] Click the conversation entry in sidebar — verify all messages load into chat panel
- [ ] T040 [Navigator] Verify active conversation is highlighted in sidebar
- [ ] T040b [Navigator] Test conversation rename: open dropdown menu on a sidebar entry, click Rename, type new title, press Enter — verify title updates immediately (FR-013)
- [ ] T040c [Navigator] Test conversation delete: open dropdown menu, click Delete, confirm in dialog — verify conversation is removed from sidebar and chat panel resets (FR-013)
- [ ] T041 [Orchestrator] Gate 2 decision: PASS if T037-T040c all pass. FAIL → loop to T034.

**Checkpoint**: Sidebar navigation works — US2 + US3 complete.

---

## Phase 5: User Story 4 — Reliable Backend Processing (Priority: P2) — BUG-016, BUG-017

**Goal**: Fix CallLimitCallback instantiation (BUG-016) and deduplicate citations (BUG-017).

**Independent Test**: `curl` complex query → no "call limit exceeded" warnings in logs, citations have unique `passage_id` values.

**Agent**: A2 (Backend Fixer)

> **Runs in PARALLEL with Phase 4** — A2 works on `backend/`, A1 works on `frontend/`.

### Implementation for User Story 4

- [ ] T042 [P] [US4] Fix CallLimitCallback instantiation in `backend/api/chat.py` line 156 — remove explicit args `(max_llm_calls=20, max_tool_calls=10)`, use `CallLimitCallback()` to inherit class defaults (100/50)
- [ ] T043 [P] [US4] Read `backend/agent/state.py` — audit the `citations` field reducer. Confirm it uses `operator.add` or similar accumulator. Document finding (no code change expected).
- [ ] T044 [US4] Add citation deduplication in `backend/api/chat.py` lines 211-217 — after building `citation_dicts` list, deduplicate by `passage_id` before yielding the citation NDJSON event. Use a `seen` set to track unique passage IDs.

### Gate 3: Verify BUG-016 + BUG-017

- [ ] T045 [User] Rebuild backend: `docker compose build backend && docker compose up -d backend`
- [ ] T046 [Orchestrator] Send complex query via curl: `curl -s -N -X POST http://localhost:8000/api/chat -H "Content-Type: application/json" -d '{"message":"Explain the ARCA system architecture and how its components interact","collection_ids":["07d3308c-5bb9-49a8-bcf7-5edafbcb8dca"],"llm_model":"qwen2.5:7b"}'` — capture full output
- [ ] T047 [Orchestrator] Check backend logs: `docker compose logs backend --tail=50 2>&1 | rg "call_limit"` — must show zero "call_limit_llm_exceeded" warnings
- [ ] T048 [Orchestrator] Check citation dedup in curl output from T046 — extract all `passage_id` values from the citation event, verify zero duplicates
- [ ] T049 [Orchestrator] Gate 3 decision: PASS if T047-T048 pass. FAIL → loop to T042.

**Checkpoint**: Backend fixes verified — US4 complete.

---

## Phase 6: E2E Verification (All Success Criteria)

**Purpose**: Verify all 7 success criteria with fully rebuilt containers.

- [ ] T050 [User] Full rebuild: `docker compose build backend frontend && docker compose up -d`
- [ ] T051 [Navigator] SC-001: Select collection, send message → response text renders in chat panel within 5 seconds of backend completion
- [ ] T052 [Navigator] SC-002: Click sidebar "New Chat" → chat panel clears to empty state 100% of the time
- [ ] T053 [Navigator] SC-003: After completed chat, check sidebar → conversation shows first user message as title with correct message count
- [ ] T054 [Navigator] SC-004: Click sidebar conversation entry → all messages load into chat panel
- [ ] T055 [Orchestrator] SC-005: Send complex query, check backend logs → zero "call limit exceeded" warnings
- [ ] T056 [Orchestrator] SC-006: Curl chat endpoint, inspect citation event → zero duplicate passage_ids
- [ ] T057 [Orchestrator] SC-007: Compile final pass/fail matrix for all 5 bugs (BUG-013 through BUG-017)
- [ ] T058 [Orchestrator] Verify Makefile unchanged: `git diff Makefile` must produce no output
- [ ] T059 [Orchestrator] Create final commit: `fix(chat): resolve 5 bugs in chat pipeline (BUG-013–BUG-017)`

**Checkpoint**: All success criteria verified — spec 024 complete.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Investigation)**: Depends on Phase 1 — Docker must be running
- **Phase 3 (US1 — BUG-013)**: Depends on Phase 2 — root cause must be diagnosed
- **Phase 4 (US2+US3 — BUG-014/015)**: Depends on Phase 3 Gate 1 — streaming must work
- **Phase 5 (US4 — BUG-016/017)**: Depends on Phase 1 only — can start after Phase 3 Gate 1 passes
- **Phase 6 (E2E Verification)**: Depends on Phase 4 Gate 2 AND Phase 5 Gate 3

### Parallel Opportunities

```
Phase 1 → Phase 2 → Phase 3 (US1) → Gate 1
                                        │
                          ┌──────────────┼──────────────┐
                          │                             │
                    Phase 4 (US2+US3)             Phase 5 (US4)
                    A1: frontend fixes            A2: backend fixes
                          │                             │
                          └──────────────┬──────────────┘
                                         │
                                   Phase 6 (E2E)
```

- **T014, T015, T016** — Researcher tasks can all run in parallel (different documentation sources)
- **T032** — Can run in parallel with T042-T044 (frontend vs backend, different agents)
- **T042, T043** — Backend tasks can run in parallel (different concerns in same file — audit is read-only)
- **Phase 4 and Phase 5** — Can run fully in parallel (A1 on frontend, A2 on backend)

### Within Each User Story

- Investigation (Navigator + Researcher) BEFORE fix instructions
- Fix instructions from Orchestrator BEFORE A1/A2 code changes
- Code changes BEFORE user rebuild
- User rebuild BEFORE Navigator verification
- Gate pass BEFORE next phase

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup verification
2. Complete Phase 2: Investigation (Navigator + Researcher)
3. Complete Phase 3: BUG-013 fix (A1)
4. **STOP and VALIDATE**: Gate 1 — does chat response render?
5. If yes: the product's core function works. Proceed to polish.

### Full Fix Delivery

1. Phase 1 → Phase 2 → Phase 3 (US1) → Gate 1
2. Phase 4 (US2+US3) + Phase 5 (US4) in parallel → Gate 2 + Gate 3
3. Phase 6 → E2E verification → Final commit

### Agent Execution Summary

| Agent | Tasks | Phase(s) |
|-------|-------|----------|
| Orchestrator | T001-T005, T017, T031, T041, T046-T049, T055-T059 | 1, 2, 3, 4, 5, 6 |
| Navigator | T006-T013, T027-T030, T037-T040, T051-T054 | 2, 3, 4, 6 |
| Researcher | T014-T016 | 2 |
| A1 (Frontend) | T018-T025, T032-T033, T034-T035 | 3, 4 |
| A2 (Backend) | T042-T044 | 5 |
| User | T026, T036, T045, T050 | 3, 4, 5, 6 |

---

## Notes

- [P] tasks = different files or different agents, no dependencies
- [Story] label maps task to specific user story for traceability
- [Agent] label indicates which team member executes the task
- Navigator verification tasks require Docker containers to be rebuilt BEFORE execution
- Phase 4 and Phase 5 are designed for parallel execution by different agents
- If Gate 1 fails, the investigation loop (Phase 2) repeats with new Navigator observations
- Makefile MUST remain unchanged throughout — checked at T005 and T058
