# Agent A7: Quality Engineer

**Agent Type**: `quality-engineer`
**Model**: Sonnet
**Wave**: 5 (serial)
**Tasks**: T038-T046

## Mission

Set up the vitest and Playwright test infrastructure, write comprehensive unit tests for the API client (NDJSON parsing for all 10 event types), component behavior, and SWR hooks, then write E2E tests for all major user flows. Perform a final TypeScript strict audit.

## Authoritative Sources

Read these files FIRST before writing any code:

- `specs/009-next-frontend/contracts/api-client.ts` -- All interfaces, NDJSON event types, API function signatures
- `specs/009-next-frontend/data-model.md` -- Entity definitions, confidence tiers, error shape
- `specs/009-next-frontend/tasks.md` -- Task list with exact descriptions for T038-T046
- `Docs/PROMPTS/spec-09-frontend/09-implement.md` -- Code patterns, NDJSON parsing, component props

Also read the actual source files created by previous agents:

- `frontend/lib/api.ts` -- Actual API client implementation to test
- `frontend/lib/types.ts` -- Actual type definitions
- `frontend/components/*.tsx` -- All components to test
- `frontend/hooks/*.ts` -- All hooks to test

## Tasks

### Test Infrastructure (T038-T039)

1. **T038** [P] Create `frontend/vitest.config.ts` -- jsdom environment, `@vitejs/plugin-react`, coverage provider `v8`, coverage threshold lines >= 70%; add `test` script to `frontend/package.json`: `vitest run`; add `test:coverage` script
2. **T039** [P] Create `frontend/playwright.config.ts` -- `baseURL: 'http://localhost:3000'`; screenshots on failure; trace on first retry; `testDir: './tests/e2e'`; add `test:e2e` script to `frontend/package.json`

### Unit Tests (T040-T042)

3. **T040** [P] Write unit tests in `frontend/tests/unit/api.test.ts`:
   - `streamChat()` NDJSON parsing for all 10 event types: session, status, chunk, clarification, citation, meta_reasoning, confidence, groundedness, done, error
   - `chunk` event dispatches `onToken` with `event.text` (NOT `event.content`)
   - `clarification` event calls `onClarification` AND releases `isStreaming` (no `done` follows)
   - `updateSettings` sends `PUT` not `PATCH`
   - Error response parsed as `ApiError` with `code` and `message` from `error.code`/`error.message` body shape
   - `source_removed` field preserved in `Citation` from citation event

4. **T041** [P] Write unit tests in `frontend/tests/unit/components.test.ts`:
   - `ConfidenceIndicator` tier boundaries: score 0 -> red, 39 -> red, 40 -> yellow, 69 -> yellow, 70 -> green, 100 -> green (INTEGER 0-100, not float)
   - `CitationTooltip` renders "source removed" badge when `source_removed === true`
   - `CollectionCard` delete confirmation dialog appears before action
   - `CreateCollectionDialog` invalid slug shows error, valid slug does not

5. **T042** [P] Write unit tests in `frontend/tests/unit/hooks.test.ts`:
   - `useStreamChat` `isStreaming` released on `done` event
   - `isStreaming` released on `error` event
   - `isStreaming` released on `clarification` event
   - Message array appended correctly
   - Functional setState prevents stale closure on rapid chunks

### E2E Tests (T043-T046)

6. **T043** Write E2E test in `frontend/tests/e2e/chat.spec.ts` -- submit query with collection selected; streaming tokens appear; send button disabled during stream; send button re-enabled on completion; confidence indicator rendered after `done`; citation `[1]` marker visible; hover shows tooltip

7. **T044** [P] Write E2E test in `frontend/tests/e2e/collections.spec.ts` -- create with valid name -> card in grid; invalid name (`-foo`) -> inline error; duplicate name -> dialog stays open with conflict error; delete -> dialog -> confirmed -> card removed

8. **T045** [P] Write E2E test in `frontend/tests/e2e/documents.spec.ts` -- upload file >50 MB -> inline error, no network request; upload `.exe` -> inline error; upload valid PDF -> progress shown -> polling -> completed badge

9. **T046** [P] Write E2E test in `frontend/tests/e2e/settings.spec.ts` -- change `confidence_threshold`, save -> toast "Settings saved" appears; refresh -> value persisted; enter provider key -> field shows masked value; delete key -> has_key indicator shows false

## Key Constraints

- **NDJSON, NOT Server-Sent Events**: All tests for `streamChat()` must use raw JSON lines. NEVER test for `data:` prefix stripping. The stream format is NDJSON.
- **chunk event has field `text`**: Test that `onToken` receives `event.text`, NOT `event.content`.
- **clarification releases isStreaming**: This is the most critical test -- `clarification` ends the stream without a `done` event. If `isStreaming` is not released on `clarification`, the send button locks permanently.
- **Confidence is INTEGER 0-100**: Test boundary values: 0, 39, 40, 69, 70, 100. NOT float values like 0.7, 0.4.
- **Error shape**: API errors have `{ error: { code, message }, trace_id }` body. NOT `{ detail }`.
- **source_removed**: Test that `CitationTooltip` renders a "source removed" badge when `source_removed === true`.
- **Settings uses PUT**: Verify the HTTP method is PUT, not PATCH.
- **Mock patterns**: Use `vi.fn()` for callbacks, mock `fetch` for API tests, use `@testing-library/react` `render` + `screen` for component tests.

## Testing Protocol

- NEVER run vitest or playwright inline inside Claude Code
- Run unit tests: `cd frontend && npm run test -- --run`
- Run E2E tests: `cd frontend && npx playwright test`
- Run coverage: `cd frontend && npm run test:coverage`
- TypeScript audit: `cd frontend && npx tsc --noEmit`
- Python regression: `zsh scripts/run-tests-external.sh -n spec09-regression tests/`

## Done Criteria

- `frontend/vitest.config.ts` and `frontend/playwright.config.ts` created
- `npm run test -- --run` passes all unit tests
- `npx playwright test` passes all E2E tests
- Coverage >= 70% lines
- `npx tsc --noEmit` exits 0 (TypeScript strict audit)
- All 10 NDJSON event types tested in `api.test.ts`
- `clarification` isStreaming release tested
- Confidence integer boundaries tested (NOT float)
- `source_removed` badge rendering tested
