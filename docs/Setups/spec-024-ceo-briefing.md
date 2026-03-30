# Spec 024: Chat & Agentic RAG Pipeline Fix -- CEO Briefing

**Company**: The Embedinator (`d7b07693-6463-413a-9690-0ef8feec4005`)
**Assigned To**: CEO (`098ecb35-30a9-43fa-b76f-89ebd42a7833`)
**Branch**: `024-chat-fix`
**Priority**: P0-CRITICAL (product non-functional)
**Bugs**: BUG-013 (P0), BUG-014 (P1), BUG-015 (P1), BUG-016 (P1), BUG-017 (P2)

---

## Executive Summary

The Embedinator's chat pipeline is broken. Users cannot see AI responses (BUG-013), cannot start new conversations (BUG-014), see broken sidebar entries (BUG-015), experience premature research truncation (BUG-016), and receive quadruplicated citations (BUG-017). This is a 5-bug fix across backend and frontend with zero new features, zero new dependencies, and zero API contract changes.

**Prior work completed**: Phases 1+2 of the original speckit workflow are DONE (tasks T001-T017). Root causes have been identified and the Board approved Option A (full streaming fix for both backend and frontend).

**Root cause (BUG-013)**: `collect_answer` in `backend/agent/research_nodes.py:609` uses `ainvoke()` instead of `astream()`, producing zero streaming tokens. Additionally, `chat.py:171` is missing `version="v2"` and `subgraphs=True` parameters. On the frontend side, a dual localStorage system (`useChatStorage` legacy + `useChatHistory` v1) creates race conditions that overwrite streaming state.

This briefing defines an 8-phase workflow (Phase 0 through Phase 7) to fix all 5 bugs, verify each fix through browser automation and curl, and run a post-fix quality gate before declaring the spec complete.

---

## Spec Artifacts -- READ THESE FIRST

| Priority | File | Contents |
|----------|------|----------|
| 1 | `specs/024-chat-fix/spec.md` | Bug registry, FR-001 through FR-017, SC-001 through SC-007, user stories, edge cases |
| 2 | `specs/024-chat-fix/plan.md` | Phase details, suspect analysis, agent scope, verification commands, file touch matrix |
| 3 | `specs/024-chat-fix/tasks.md` | T001-T059 task checklist with agent assignments (T001-T017 already DONE) |
| 4 | `specs/024-chat-fix/research.md` | 6 verified decisions from the diagnostic session |
| 5 | `docs/PROMPTS/spec-24-chat-fix/24-implement.md` | Original Agent Teams execution manual (reference only -- Paperclip replaces Agent Teams) |

---

## Agent Registry

| Role | Agent ID | Capabilities |
|------|----------|-------------|
| CEO (you) | `098ecb35-30a9-43fa-b76f-89ebd42a7833` | Orchestration, sub-issue creation, gate decisions |
| python-expert | `eac71da4-ef0a-4954-9dd0-0f7178ccc0eb` | Backend Python code changes |
| frontend-architect | `84481498-a0d7-4d97-8aee-782536ed8bdb` | Frontend TypeScript/React code changes |
| quality-engineer | `7c3a6b0c-8c78-4249-b9f6-6ad5f742c29c` | Browser-based verification via Playwright/Chrome DevTools |
| deep-research-agent | `a27a8527-3865-4df5-a092-6918b116bdee` | Documentation research, API pattern discovery |
| root-cause-analyst | `e61358a8-9912-4a9e-9267-9d25b6d603de` | Diagnostic escalation when agents hit blockers |
| security-engineer | `fadc9672-723b-49f9-b412-7c959f6726cf` | Post-fix security scan |
| self-review | `362cbfa3-cb8f-4f93-b28b-09adec8a475b` | Scope drift detection, spec compliance check |
| performance-engineer | `30874d8c-a601-47f3-9956-3d3a1b7a106a` | Lighthouse audit on modified pages |

---

## Bug Registry

| ID | Severity | Layer | Summary | Root Cause |
|----|----------|-------|---------|------------|
| BUG-013 | P0-CRITICAL | Both | Chat response text never renders -- skeleton bars shown indefinitely | Backend: `ainvoke()` at `research_nodes.py:609` instead of `astream()`. Frontend: dual localStorage race condition in `useChatStorage` overwrites streaming state |
| BUG-014 | P1-HIGH | Frontend | Sidebar "New Chat" button does not clear state | `SidebarNav.tsx` navigates to `/chat` without signaling state reset |
| BUG-015 | P1-HIGH | Frontend | Conversation history entries show "New Chat 0" and fail to load | Streaming never completes (BUG-013 cascade), so `syncMessages` never fires to update title/count |
| BUG-016 | P1-HIGH | Backend | Call limit callback uses old limits (20/10) instead of class defaults (100/50) | Explicit args at `chat.py:156` override the updated class defaults |
| BUG-017 | P2-MEDIUM | Backend | Citations duplicated 4x in response | `Send()` fan-out creates N sub-question loops, each appending via `operator.add` reducer with no dedup before NDJSON emission |

---

## 8-Phase Workflow

### Phase 0 -- Pre-flight Research

**Objective**: Obtain up-to-date documentation for LangGraph `astream()` patterns and Next.js 16 streaming through rewrites before any code changes begin.

| Field | Value |
|-------|-------|
| Agent | deep-research-agent (`a27a8527-3865-4df5-a092-6918b116bdee`) |
| /sc command | `/sc:research --sequential --context7` |
| MCPs | langchain-docs, context7, sequential-thinking |
| Skills | vercel-react-best-practices, next-best-practices |

**Task**: Research two specific areas and produce a document with exact API patterns:

1. **LangGraph `astream()` for sub-graph nodes**: How to replace `ainvoke()` with `astream()` inside a research node that runs within a `Send()` fan-out. The current code at `backend/agent/research_nodes.py:609` uses `await llm.ainvoke([...])`. The fix must stream tokens while still capturing the full answer text for the state. Include the exact function signature and yield pattern.

2. **Next.js 16 streaming through rewrites**: Confirm that `ReadableStream` responses from a backend proxied through `next.config.ts` rewrites arrive correctly at the browser. Document any known issues with `res.body` being null in standalone mode and the correct fetch pattern for NDJSON streaming in React 19.

**Deliverable**: Research document with exact API patterns, code snippets, and version-specific caveats.

**Escalation protocol**: If research hits a dead end or conflicting documentation, STOP. Post a BLOCKED comment with what was found and what is missing. Wait for CEO to assign root-cause-analyst (`e61358a8-9912-4a9e-9267-9d25b6d603de`). NEVER guess API patterns.

**Board gate**: CEO posts research summary to the Board. Wait for "approved" before proceeding.

**Mandatory protocols**:
1. Read `/home/brunoghiberto/.paperclip/agents/memory-protocol.md` FIRST. Follow the triple-write rule.
2. Use sequential-thinking MCP before any non-trivial investigation step.
3. Run gitnexus detect_changes AFTER finishing (should be zero -- this phase writes no code).
4. No builds. No package installs. Makefile is SACRED.

---

### Phase 1 -- Backend Streaming Fix (Critical Path)

**Objective**: Fix the backend so that `collect_answer` streams tokens via `astream()` and `chat.py` correctly propagates sub-graph streaming events.

| Field | Value |
|-------|-------|
| Agent | python-expert (`eac71da4-ef0a-4954-9dd0-0f7178ccc0eb`) |
| /sc command | `/sc:implement --sequential --context7 --safe-mode` |
| MCPs | serena (symbol-level read/edit), gitnexus (impact analysis), langchain-docs, sequential-thinking |
| Standby | root-cause-analyst (`e61358a8-9912-4a9e-9267-9d25b6d603de`) |

**Steps (execute in order)**:

1. `sequentialthinking` -- Plan the approach using Phase 0 research deliverable. Map out the exact changes before touching any file.

2. `gitnexus impact` on `collect_answer` -- Report the blast radius (direct callers, affected execution flows, risk level) to CEO before proceeding. If risk is HIGH or CRITICAL, STOP and wait for CEO approval.

3. `serena find_symbol` -- Read the full body of `collect_answer` in `backend/agent/research_nodes.py`. Confirm `ainvoke()` at line 609 is the target.

4. `langchain-docs` -- Confirm the `astream()` API signature from the Phase 0 research. Cross-reference with the LangGraph docs MCP.

5. `serena replace_symbol_body` -- Change `ainvoke()` to `astream()` in `collect_answer`. The replacement must:
   - Stream tokens to the caller via the LangGraph streaming protocol
   - Still capture the full answer text and write it to `state["messages"]`
   - Preserve the existing fallback/exception handling at lines 614-621

6. Fix `chat.py:171` -- Add `version="v2"` and `subgraphs=True` to the `graph.astream()` call so sub-graph streaming events propagate to the NDJSON endpoint.

7. `serena find_symbol` -- Read `init_session` in `backend/agent/nodes.py`. Fix the `db=None` injection gap if present.

8. `gitnexus detect_changes` -- Verify ONLY the expected symbols were modified. If unexpected files appear in the diff, STOP and report.

**Files modified**:
- `backend/agent/research_nodes.py` -- `collect_answer` function body
- `backend/api/chat.py` -- `graph.astream()` parameters
- `backend/agent/nodes.py` -- `init_session` (if `db=None` gap confirmed)

**Escalation protocol**: If ANY step fails or produces unexpected results, STOP immediately. Post a BLOCKED comment describing what failed, what was attempted, and the current state of the code. Wait for CEO to assign root-cause-analyst. NEVER retry without diagnosis. NEVER continue with partial fixes.

**Mandatory protocols**:
1. Read `/home/brunoghiberto/.paperclip/agents/memory-protocol.md` FIRST. Follow the triple-write rule.
2. Use sequential-thinking MCP before any non-trivial code change.
3. Run gitnexus impact BEFORE editing any symbol. Run gitnexus detect_changes AFTER finishing.
4. No builds. Board rebuilds Docker. No package installs. Makefile is SACRED.

---

### Phase 2 -- Frontend Streaming Fix (BUG-013 frontend side)

**Objective**: Fix the frontend rendering chain so that NDJSON streaming events from the backend are parsed and rendered in the chat panel.

| Field | Value |
|-------|-------|
| Agent | frontend-architect (`84481498-a0d7-4d97-8aee-782536ed8bdb`) |
| /sc command | `/sc:implement --sequential --context7 --safe-mode` |
| MCPs | context7, shadcn-ui, next-devtools-mcp, serena, sequential-thinking |
| Skills | vercel-react-best-practices, next-best-practices, frontend-design, shadcn |
| Standby | root-cause-analyst (`e61358a8-9912-4a9e-9267-9d25b6d603de`) |

**Steps (execute in order)**:

1. `sequentialthinking` -- Plan the approach using Phase 0 research deliverable. The primary fix direction is removing the dual localStorage system and adding stream guards.

2. `next-devtools-mcp nextjs_runtime` -- Inspect the running app state. Confirm the frontend is receiving streaming responses but failing to render them.

3. **Remove `useChatStorage` entirely**:
   - Delete the `useChatStorage` import and all destructured references (`storedMessages`, `storedSessionId`, `saveMessages`, `clearChat`) from `frontend/app/chat/page.tsx`
   - Delete the hydration `useEffect` (lines ~124-129) that reads from legacy localStorage
   - Delete the save `useEffect` (lines ~132-141) that writes to legacy localStorage
   - Delete `frontend/hooks/useChatStorage.ts` entirely
   - Update `handleNewChat` in `page.tsx` to remove the `clearChat()` call

4. **Add `res.body` null guard in `frontend/lib/api.ts`**:
   - At line ~147 where `res.body!.getReader()` is called
   - If `res.body` is null, call `callbacks.onError("Stream body unavailable", "STREAM_ERROR")` and return
   - Wrap the reader loop in try/catch so JSON parse errors are caught and forwarded to `callbacks.onError`

5. **Fix hydration race using React 19 pattern from research**:
   - Guard the `activeSession` hydration effect in `page.tsx` (lines ~101-121) so it does not overwrite messages if streaming is active
   - Verify `useStreamChat.sendMessage` callback closures capture `assistantId` correctly

6. `gitnexus detect_changes` -- Verify ONLY frontend files were modified. If backend files appear in the diff, STOP and report.

**Files modified**:
- `frontend/lib/api.ts` -- `res.body` null guard, error handling
- `frontend/app/chat/page.tsx` -- Remove `useChatStorage`, guard hydration effects, update `handleNewChat`
- `frontend/hooks/useChatStorage.ts` -- DELETE
- `frontend/hooks/useStreamChat.ts` -- Verify/fix callback closures (modify only if needed)

**PARALLEL EXECUTION**: This phase runs IN PARALLEL with Phase 1. Zero file overlap between backend and frontend agents.

**Escalation protocol**: If ANY step fails or produces unexpected results, STOP immediately. Post a BLOCKED comment describing what failed, what was attempted, and the current state of the code. Wait for CEO to assign root-cause-analyst. NEVER retry without diagnosis. NEVER continue with partial fixes.

**Mandatory protocols**:
1. Read `/home/brunoghiberto/.paperclip/agents/memory-protocol.md` FIRST. Follow the triple-write rule.
2. Use sequential-thinking MCP before any non-trivial code change.
3. Run gitnexus detect_changes AFTER finishing.
4. No builds. Board rebuilds Docker. No package installs. Makefile is SACRED.

**Board gate after Phase 1 + Phase 2 complete**: CEO posts a comment asking the Board to rebuild and restart:
```
## Board Action Required — Rebuild

Phase 1 (backend) and Phase 2 (frontend) code changes are complete.
Please rebuild and restart the containers:

  docker compose build backend frontend && docker compose up -d

Reply "rebuilt" when done so Phase 3 verification can begin.
```

---

### Phase 3 -- First Verification (BUG-013 fixed?)

**Objective**: Verify that BUG-013 is resolved -- chat responses render in the browser after the Phase 1 + Phase 2 fixes.

| Field | Value |
|-------|-------|
| Agent | quality-engineer (`7c3a6b0c-8c78-4249-b9f6-6ad5f742c29c`) |
| /sc command | `/sc:test --sequential --playwright` |
| MCPs | playwright, chrome-devtools, browser-tools, sequential-thinking |
| Skills | webapp-testing |
| Standby | root-cause-analyst (`e61358a8-9912-4a9e-9267-9d25b6d603de`) |

**Test sequence**:

1. Navigate to `http://localhost:3001/chat` (or `http://localhost:3000/chat` if 3001 is not the correct port -- verify)
2. Select a collection from the collection picker
3. Type "What topics does this collection cover?" and send
4. Wait 40 seconds (backend response takes 30-40s for complex queries)
5. `chrome-devtools list_network_requests` -- Verify the POST `/api/chat` returns 200 with `Content-Type: application/x-ndjson` and the response body contains NDJSON lines
6. `chrome-devtools list_console_messages` -- Verify zero JavaScript errors related to streaming, fetch, or ReadableStream
7. `playwright browser_snapshot` -- Verify the assistant message text is rendered in the chat panel (not skeleton bars)
8. `playwright browser_take_screenshot` -- Capture visual evidence of the rendered response

**Deliverable**: SC-001 verification report with PASS or FAIL status and screenshot evidence attached.

**Board manual verification (REQUIRED)**:

After the quality-engineer completes automated tests, the CEO MUST ask the Board to perform manual verification. Post a comment on this issue requesting:

```
## Board Manual Verification — Phase 3

Please start the app and verify BUG-013 is fixed:

1. Start the app using the TUI launcher (./embedinator.sh or your preferred method)
2. Open http://localhost:3001/chat in your browser
3. Select a collection from the picker
4. Type a question and send it
5. Verify: does the response text render in the chat panel? (not skeleton bars)
6. Verify: do you see streaming text appearing progressively?
7. Reply with PASS or FAIL and describe what you observed
```

Wait for Board response before proceeding.

**Gate decision**:
- Board replies PASS + quality-engineer PASS: Proceed to Phase 4 + Phase 5
- ANY FAIL: CEO assigns root-cause-analyst (`e61358a8-9912-4a9e-9267-9d25b6d603de`) to diagnose. NEVER retry the same fix without a new diagnosis. Maximum 3 retry loops before escalating to Board.

**Escalation protocol**: If verification encounters infrastructure issues (containers not running, network errors, Playwright connection failures), STOP immediately. Post a BLOCKED comment. Wait for CEO. Do not conflate infrastructure failures with bug verification failures.

**Mandatory protocols**:
1. Read `/home/brunoghiberto/.paperclip/agents/memory-protocol.md` FIRST. Follow the triple-write rule.
2. Use sequential-thinking MCP before deciding PASS/FAIL on ambiguous results.
3. No builds. No code changes. No package installs. Makefile is SACRED.

---

### Phase 4 -- Sidebar Navigation Fix (BUG-014 + BUG-015)

**Objective**: Fix sidebar "New Chat" button to clear state and fix conversation history entries to show correct titles and load messages on click.

| Field | Value |
|-------|-------|
| Agent | frontend-architect (`84481498-a0d7-4d97-8aee-782536ed8bdb`) |
| /sc command | `/sc:implement --sequential --context7` |
| MCPs | serena, context7, shadcn-ui, sequential-thinking |
| Skills | shadcn, ui-ux-pro-max, polish |
| Standby | root-cause-analyst (`e61358a8-9912-4a9e-9267-9d25b6d603de`) |

**Tasks**:

1. **BUG-014 fix** -- Modify `frontend/components/SidebarNav.tsx`:
   - Change the "New Chat" button's `onClick` from `router.push("/chat")` to `router.push("/chat?new=1")`

2. **BUG-014 fix** -- Modify `frontend/app/chat/page.tsx`:
   - Add `?new=1` detection in the component body
   - When `searchParams.get("new")` is truthy, call `handleNewChat()` then `router.replace("/chat", { scroll: false })` to clean the param

3. **BUG-015 verification** -- Confirm that BUG-015 is resolved by the Phase 2 streaming fix:
   - When streaming completes correctly, `syncMessages` fires and updates the session title (first user message truncated to 40 chars) and message count
   - If NOT resolved, audit `syncMessages` in `page.tsx` and fix the `prevStreamingRef` transition detection

4. `gitnexus detect_changes` -- Verify only `SidebarNav.tsx` and `page.tsx` were modified

**Files modified**:
- `frontend/components/SidebarNav.tsx` -- "New Chat" button onClick
- `frontend/app/chat/page.tsx` -- `?new=1` detection and handler

**PARALLEL EXECUTION**: This phase runs IN PARALLEL with Phase 5. Zero file overlap.

**Escalation protocol**: If ANY step fails, STOP. Post a BLOCKED comment. Wait for CEO to assign root-cause-analyst. NEVER retry without diagnosis. NEVER continue with partial fixes.

**Mandatory protocols**:
1. Read `/home/brunoghiberto/.paperclip/agents/memory-protocol.md` FIRST. Follow the triple-write rule.
2. Use sequential-thinking MCP before any non-trivial code change.
3. Run gitnexus detect_changes AFTER finishing.
4. No builds. Board rebuilds Docker. No package installs. Makefile is SACRED.

---

### Phase 5 -- Backend Processing Fix (BUG-016 + BUG-017)

**Objective**: Fix CallLimitCallback instantiation and add citation deduplication.

| Field | Value |
|-------|-------|
| Agent | python-expert (`eac71da4-ef0a-4954-9dd0-0f7178ccc0eb`) |
| /sc command | `/sc:implement --sequential --safe-mode` |
| MCPs | serena, gitnexus, sequential-thinking |
| Standby | root-cause-analyst (`e61358a8-9912-4a9e-9267-9d25b6d603de`) |

**Tasks**:

1. `gitnexus impact` on `CallLimitCallback` -- Report blast radius before editing.

2. **BUG-016 fix** -- `serena` edit `backend/api/chat.py` line 156:
   - Remove explicit args `(max_llm_calls=20, max_tool_calls=10)` from `CallLimitCallback()`
   - Use `CallLimitCallback()` with no args to inherit class defaults (100 LLM calls, 50 tool calls)

3. `serena find_symbol` -- Audit the `citations` field reducer in `backend/agent/state.py`. Confirm it uses `operator.add` (accumulator pattern). Document finding. No code change expected.

4. **BUG-017 fix** -- `serena` edit `backend/api/chat.py` lines 211-217:
   - After building `citation_dicts` list, deduplicate by `passage_id` before yielding the citation NDJSON event
   - Use a `seen_pids` set to track unique passage IDs
   - Only yield citations where `passage_id` has not been seen before

5. `gitnexus detect_changes` -- Verify only `chat.py` was modified. `state.py` should be read-only.

**Files modified**:
- `backend/api/chat.py` -- CallLimitCallback args removal + citation dedup logic

**Files read (not modified)**:
- `backend/agent/state.py` -- citations reducer audit

**PARALLEL EXECUTION**: This phase runs IN PARALLEL with Phase 4. Zero file overlap.

**Board gate after Phase 4 + Phase 5 complete**: CEO posts a comment asking the Board to rebuild and restart:
```
## Board Action Required — Rebuild

Phase 4 (sidebar) and Phase 5 (backend processing) code changes are complete.
Please rebuild and restart the containers:

  docker compose build backend frontend && docker compose up -d

Reply "rebuilt" when done so Phase 6 E2E verification can begin.
```

**Escalation protocol**: If ANY step fails, STOP. Post a BLOCKED comment. Wait for CEO to assign root-cause-analyst. NEVER retry without diagnosis. NEVER continue with partial fixes.

**Mandatory protocols**:
1. Read `/home/brunoghiberto/.paperclip/agents/memory-protocol.md` FIRST. Follow the triple-write rule.
2. Use sequential-thinking MCP before any non-trivial code change.
3. Run gitnexus impact BEFORE editing any symbol. Run gitnexus detect_changes AFTER finishing.
4. No builds. Board rebuilds Docker. No package installs. Makefile is SACRED.

---

### Phase 6 -- Full E2E Verification

**Objective**: Verify ALL 7 success criteria with fully rebuilt containers. This is the definitive pass/fail determination.

| Field | Value |
|-------|-------|
| Agent | quality-engineer (`7c3a6b0c-8c78-4249-b9f6-6ad5f742c29c`) |
| /sc command | `/sc:test --sequential --playwright --think-hard` |
| MCPs | playwright, chrome-devtools, browser-tools, sequential-thinking |
| Standby | root-cause-analyst (`e61358a8-9912-4a9e-9267-9d25b6d603de`) |

**SC Verification Matrix**:

| SC | Test Procedure | Expected Result | Verification Method |
|----|---------------|-----------------|---------------------|
| SC-001 | Select collection, send message, wait 40s | Response text renders in chat panel within 5s of backend completion | `playwright browser_snapshot` + `browser_take_screenshot` |
| SC-002 | With active conversation, click sidebar "New Chat" | Chat panel clears to empty state 100% of the time | `playwright browser_snapshot` before and after click |
| SC-003 | Complete a chat exchange, inspect sidebar | Conversation shows first user message as title (truncated to 40 chars) + correct message count within 3s | `playwright browser_snapshot` of sidebar |
| SC-004 | Click a conversation entry in sidebar | All messages from that conversation load into the chat panel | `playwright browser_snapshot` + verify message count |
| SC-005 | Send complex multi-part query, check backend logs | Zero "call limit exceeded" warnings | `docker compose logs backend --tail=50 \| rg "call_limit"` |
| SC-006 | curl chat endpoint, parse citation event | Zero duplicate `passage_id` values in the citation NDJSON line | curl output + `passage_id` uniqueness check |
| SC-007 | All SC-001 through SC-006 above | ALL PASS | Composite of all above |

**Deliverable**: SC matrix report with PASS/FAIL status for each criterion, screenshot evidence for browser-based tests, and curl output excerpts for backend tests.

**Board manual E2E verification (REQUIRED)**:

After the quality-engineer completes automated tests, the CEO MUST ask the Board to perform a full manual walkthrough. Post a comment on this issue requesting:

```
## Board Manual E2E Verification — Phase 6

Please start the app and run through this complete test:

1. Start the app using the TUI launcher (./embedinator.sh or your preferred method)
2. Open http://localhost:3001/chat

### BUG-013 — Chat response rendering
3. Select a collection → send a question → wait for response
4. Does the response text render? Is streaming visible? (PASS/FAIL)

### BUG-014 — New Chat button
5. Click "New Chat" in the sidebar
6. Does the chat panel clear completely? (PASS/FAIL)

### BUG-015 — Sidebar entries
7. Send another message in the new chat → wait for response
8. Does the sidebar show a conversation with the correct title and message count? (PASS/FAIL)

### BUG-014 continued — Conversation loading
9. Click back on the previous conversation in the sidebar
10. Do all messages from that conversation load? (PASS/FAIL)

### General
11. Any console errors visible? Any unexpected behavior? Any new bugs discovered?

Reply with PASS/FAIL for each and describe anything unusual.
```

Wait for Board response before proceeding. If the Board discovers NEW bugs not in the original 5, create new issues for them and escalate to decide whether they block this spec or are deferred.

**Gate decision**:
- Board PASS + quality-engineer ALL 7 PASS: Proceed to Phase 7
- ANY FAIL: CEO identifies which bug is not resolved, loops back to the relevant Phase (1, 2, 4, or 5) with new instructions

**Escalation protocol**: If verification encounters infrastructure issues, STOP. Post a BLOCKED comment. Wait for CEO.

**Mandatory protocols**:
1. Read `/home/brunoghiberto/.paperclip/agents/memory-protocol.md` FIRST. Follow the triple-write rule.
2. Use sequential-thinking MCP before deciding PASS/FAIL on ambiguous results.
3. No builds. No code changes. No package installs. Makefile is SACRED.

---

### Phase 7 -- Post-Fix Quality Gate

**Objective**: Run security, scope, and performance audits on the modified code to ensure no regressions, no scope drift, and no performance degradation.

**Three agents in parallel**:

#### Agent 1: Security Scan

| Field | Value |
|-------|-------|
| Agent | security-engineer (`fadc9672-723b-49f9-b412-7c959f6726cf`) |
| /sc command | `/sc:analyze --sequential --think-hard` |
| MCPs | sonarqube, gitnexus |

**Task**: Scan all files modified in the `024-chat-fix` branch. Report any security findings (XSS in streaming output, injection in NDJSON parsing, unsafe `eval`, hardcoded credentials). Focus on:
- `frontend/lib/api.ts` -- NDJSON parse safety
- `frontend/app/chat/page.tsx` -- user input handling
- `backend/api/chat.py` -- citation emission, streaming output

#### Agent 2: Scope Review

| Field | Value |
|-------|-------|
| Agent | self-review (`362cbfa3-cb8f-4f93-b28b-09adec8a475b`) |
| /sc command | `/sc:reflect --sequential` |
| MCPs | gitnexus (detect_changes), serena |

**Task**: Verify that the branch changes match the spec scope exactly:
- `gitnexus detect_changes` -- List all modified symbols and compare against the file touch matrix below
- Confirm no files outside the expected set were modified
- Confirm no NDJSON event types or API schemas were changed
- Confirm the Makefile is unchanged: `git diff Makefile` must produce no output

#### Agent 3: Performance Audit

| Field | Value |
|-------|-------|
| Agent | performance-engineer (`30874d8c-a601-47f3-9956-3d3a1b7a106a`) |
| /sc command | `/sc:analyze --sequential` |
| MCPs | chrome-devtools (lighthouse_audit) |

**Task**: Run Lighthouse audit on the chat page (`http://localhost:3000/chat`). Report Performance, Accessibility, and Best Practices scores. Flag any score below 80 as a concern.

**Standby for all three**: root-cause-analyst (`e61358a8-9912-4a9e-9267-9d25b6d603de`)

**Escalation protocol (all three agents)**: If you hit a problem, STOP. Post a BLOCKED comment. Wait for CEO to assign root-cause-analyst. NEVER retry without diagnosis.

**Mandatory protocols (all three agents)**:
1. Read `/home/brunoghiberto/.paperclip/agents/memory-protocol.md` FIRST. Follow the triple-write rule.
2. Use sequential-thinking MCP before any non-trivial analysis step.
3. Run gitnexus detect_changes as part of your verification.
4. No builds. No code changes. No package installs. Makefile is SACRED.

---

## File Touch Matrix (Parallel Safety)

This matrix guarantees zero file overlap between parallel phases. The CEO must verify this at every gate.

### Phase 1 (python-expert) -- Backend

| File | Action |
|------|--------|
| `backend/agent/research_nodes.py` | MODIFY (`collect_answer`: `ainvoke()` to `astream()`) |
| `backend/api/chat.py` | MODIFY (`graph.astream()` params: add `version="v2"`, `subgraphs=True`) |
| `backend/agent/nodes.py` | MODIFY (`init_session`: fix `db=None` gap, if confirmed) |

### Phase 2 (frontend-architect) -- Frontend

| File | Action |
|------|--------|
| `frontend/lib/api.ts` | MODIFY (`res.body` null guard, error handling in reader loop) |
| `frontend/app/chat/page.tsx` | MODIFY (remove `useChatStorage`, guard hydration effects) |
| `frontend/hooks/useChatStorage.ts` | DELETE (legacy dual system removed) |
| `frontend/hooks/useStreamChat.ts` | VERIFY/MODIFY (callback closures, only if needed) |

### Phase 4 (frontend-architect) -- Sidebar

| File | Action |
|------|--------|
| `frontend/components/SidebarNav.tsx` | MODIFY ("New Chat" onClick to `?new=1`) |
| `frontend/app/chat/page.tsx` | MODIFY (`?new=1` detection + `handleNewChat`) |

### Phase 5 (python-expert) -- Backend Processing

| File | Action |
|------|--------|
| `backend/api/chat.py` | MODIFY (remove `CallLimitCallback` explicit args + add citation dedup) |
| `backend/agent/state.py` | READ ONLY (audit citations reducer) |

### Parallel Safety Summary

```
Phase 1 + Phase 2:  SAFE (backend vs frontend -- zero overlap)
Phase 4 + Phase 5:  SAFE (frontend components vs backend -- zero overlap)
Phase 7 agents:     SAFE (all read-only -- no code changes)
```

### Files NEVER modified

- `Makefile` -- Verified at every gate via `git diff Makefile`
- `docker-compose.yml`, `docker-compose.dev.yml`, `docker-compose.gpu-*.yml`
- `Dockerfile.backend`, `frontend/Dockerfile`
- `embedinator.sh`, `embedinator.ps1`
- `backend/agent/conversation_graph.py`, `research_graph.py`, `edges.py`, `research_edges.py`
- `frontend/components/ui/**` (shadcn/ui components)
- `ingestion-worker/**` (Rust worker)
- NDJSON event types and request/response schemas

---

## Mandatory Protocols -- EVERY Sub-Issue

Include the following block in EVERY sub-issue created for EVERY phase:

### 1. Memory Protocol

Read `/home/brunoghiberto/.paperclip/agents/memory-protocol.md` FIRST before any other action. Follow the triple-write rule: persist findings to Serena memory, Engram memory, AND Paperclip issue comments.

### 2. Sequential Thinking

MUST use the `sequential-thinking` MCP tool (`sequentialthinking`) before any non-trivial action. This includes: planning an approach, diagnosing a failure, deciding PASS/FAIL on ambiguous evidence, and choosing between alternative fix strategies.

### 3. Escalation Protocol

If you hit a problem you cannot resolve:
1. STOP immediately
2. Post a BLOCKED comment on your issue with: what you attempted, what failed, the exact error or unexpected result, and the current state of the code
3. Wait for CEO to assign root-cause-analyst (`e61358a8-9912-4a9e-9267-9d25b6d603de`)
4. NEVER retry the same approach without a new diagnosis
5. NEVER continue with partial fixes
6. NEVER make guesses about root causes

### 4. gitnexus Protocol

- Run `gitnexus impact` BEFORE editing any symbol -- report blast radius to CEO
- Run `gitnexus detect_changes` AFTER finishing all code changes -- verify only expected files modified
- If impact analysis returns HIGH or CRITICAL risk, STOP and wait for CEO approval

### 5. No Builds

Agents NEVER run `docker compose build`. The Board rebuilds Docker containers at designated gates. Code changes are NOT live until the Board rebuilds.

### 6. Makefile SACRED

The Makefile must not be modified under any circumstances. Verified at every gate via `git diff Makefile`. If any agent touches it, revert immediately with `git checkout -- Makefile`.

### 7. No New Packages

No `npm install`, no `pip install`, no new dependencies of any kind. The spec explicitly forbids adding packages. If an agent's fix requires a new dependency, that fix is rejected -- find an alternative using existing packages.

---

## Success Criteria

All 7 must PASS for spec completion. No exceptions, no partial passes.

| SC | Criterion | Phase Verified |
|----|-----------|---------------|
| SC-001 | Response text renders in chat panel within 5s of backend completion | Phase 3, Phase 6 |
| SC-002 | "New Chat" clears state 100% of the time | Phase 6 |
| SC-003 | Sidebar title (first user message) + count correct within 3s | Phase 6 |
| SC-004 | Click conversation loads messages 100% of the time | Phase 6 |
| SC-005 | Zero "call limit exceeded" warnings in backend logs | Phase 6 |
| SC-006 | Zero duplicate citations (unique `passage_id` per citation) | Phase 6 |
| SC-007 | All 5 bugs (BUG-013 through BUG-017) resolved | Phase 6 (composite) |

---

## CEO Execution Model

### Phase 1: Plan

1. Read ALL spec artifacts listed in the table above
2. Create sub-issues for each of the 8 phases (Phase 0 through Phase 7)
3. Assign each sub-issue to the correct agent using the Agent IDs from the registry
4. Set dependencies: Phase 0 blocks Phase 1+2. Phase 1+2 block Phase 3. Phase 3 blocks Phase 4+5. Phase 4+5 block Phase 6. Phase 6 blocks Phase 7.
5. Mark parallel pairs: Phase 1 + Phase 2 (parallel). Phase 4 + Phase 5 (parallel). Phase 7 agents (all three parallel).
6. Post execution plan summary as a comment on this issue
7. Wait for Board "approved" before proceeding

### Phase 2: Execute

1. Move sub-issues to "todo" in dependency order ONLY after Board approves
2. At each gate, verify the success criteria before moving the next phase to "todo"
3. If a gate fails, create a diagnostic sub-issue for root-cause-analyst before retrying
4. Maximum 3 retry loops per gate before escalating to Board

---

## Verification Commands (Quick Reference)

```bash
# Backend health
curl -s http://localhost:8000/api/health | python3 -m json.tool

# Chat API (direct to backend)
curl -s -N -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"hello","collection_ids":["07d3308c-5bb9-49a8-bcf7-5edafbcb8dca"],"llm_model":"qwen2.5:7b"}' \
  | head -10

# Chat API (through Next.js proxy)
curl -s -N -X POST http://localhost:3000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"hello","collection_ids":["07d3308c-5bb9-49a8-bcf7-5edafbcb8dca"],"llm_model":"qwen2.5:7b"}' \
  | head -10

# Check call limit warnings
docker compose logs backend --tail=50 2>&1 | rg "call_limit"

# Check citation dedup (after curl output saved to file)
rg '"passage_id"' /tmp/spec24-curl-output.txt

# Check Makefile unchanged
git diff Makefile

# All container status
docker compose ps
```

---

## Completion Report

When ALL 7 SCs PASS and Phase 7 quality gate clears, the CEO posts the following to the Board:

```
==========================================
SPEC 024 -- FINAL REPORT
==========================================
Branch: 024-chat-fix
Bugs fixed: 5 (BUG-013 through BUG-017)

SC-001: Chat response renders           [PASS/FAIL] -- evidence: {screenshot}
SC-002: New Chat clears state            [PASS/FAIL] -- evidence: {screenshot}
SC-003: Sidebar title + count correct    [PASS/FAIL] -- evidence: {screenshot}
SC-004: Sidebar click loads messages     [PASS/FAIL] -- evidence: {screenshot}
SC-005: Zero call limit warnings         [PASS/FAIL] -- evidence: {log grep}
SC-006: Zero duplicate citations         [PASS/FAIL] -- evidence: {passage_id count}
SC-007: All 5 bugs resolved             [PASS/FAIL] -- evidence: {all above}

Quality gate:
  Security scan:      [PASS/FAIL] -- {summary}
  Scope review:       [PASS/FAIL] -- {summary}
  Performance audit:  [PASS/FAIL] -- {Lighthouse scores}
  Makefile unchanged: [PASS/FAIL]

Files modified:
  backend/agent/research_nodes.py -- collect_answer: ainvoke() -> astream()
  backend/api/chat.py -- streaming params + CallLimitCallback + citation dedup
  backend/agent/nodes.py -- init_session db=None fix (if applicable)
  frontend/lib/api.ts -- res.body null guard + error handling
  frontend/app/chat/page.tsx -- remove useChatStorage + guard effects + ?new=1
  frontend/hooks/useChatStorage.ts -- DELETED
  frontend/components/SidebarNav.tsx -- New Chat ?new=1

Commit: fix(chat): resolve 5 bugs in chat pipeline (BUG-013-BUG-017)
Ready for: git push origin 024-chat-fix && PR to main
==========================================
```

The CEO then recommends the Board approve merging `024-chat-fix` into `main`.
