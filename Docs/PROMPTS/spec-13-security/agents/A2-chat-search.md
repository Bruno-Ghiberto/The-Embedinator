# A2: Chat + Search Hardening

**Agent type**: `python-expert`
**Model**: **Sonnet 4.6** (`model="sonnet"`)

You implement FR-001 (chat message truncation) and FR-002 (filter key whitelist). You modify 2 production files and create 2 test files.

## Assigned Tasks

T012-T018 from `specs/013-security-hardening/tasks.md` (Phase 3: US2 + Phase 4: US3).

| Task | FR | Description |
|------|-----|-------------|
| T012 | FR-001 | Create `tests/unit/api/test_chat_security.py` with ~4 tests |
| T013 | FR-001 | Add `message = body.message[:10_000]` in `generate()` in `backend/api/chat.py`; replace both `body.message` refs with `message` |
| T014 | FR-001 | Run US2 tests via external runner |
| T015 | FR-002 | Create `tests/unit/retrieval/test_searcher_security.py` with ~4 tests |
| T016 | FR-002 | Add `ALLOWED_FILTER_KEYS` constant at module level in `backend/retrieval/searcher.py` |
| T017 | FR-002 | Add `if key not in ALLOWED_FILTER_KEYS: continue` guard in `_build_filter()` |
| T018 | FR-002 | Run US3 tests via external runner |

## Source Documents to Read

Read these files in order before starting any work:

1. `Docs/PROMPTS/spec-13-security/13-implement.md` -- read the "Exact Insertion Points" section for FR-001 and FR-002
2. `Docs/Tests/spec13-a1-audit.md` -- A1's audit report (confirms insertion points and line numbers)
3. `specs/013-security-hardening/tasks.md` -- your task definitions (Phase 3 + Phase 4)
4. `specs/013-security-hardening/contracts/chat-endpoint.md` -- FR-001 contract details
5. `specs/013-security-hardening/data-model.md` -- chat message and search filter validation rules

## FR-001: Chat Message Truncation

### Production Change (backend/api/chat.py)

Inside `generate()` (inner async generator in `chat()`), after the session event yield and before `initial_state` construction:

```python
        message = body.message[:10_000]  # FR-001: silent truncation
```

Then replace BOTH `body.message` references with `message`:
1. `HumanMessage(content=message)` -- was `HumanMessage(content=body.message)`
2. `query=message` -- was `query=body.message` in the `db.create_query_trace(...)` call

**No new imports needed.**

### Test File (tests/unit/api/test_chat_security.py)

Write ~4 tests covering:
- Message over 10,000 chars is truncated to exactly 10,000
- Message under 10,000 chars is unchanged
- Message exactly 10,000 chars is preserved (no off-by-one)
- Truncated message is used in both `HumanMessage(content=...)` and `db.create_query_trace(query=...)`

**Test approach**: You can test by patching `generate()` or by testing the truncation logic directly. The simplest approach is to mock the graph and db, call the `chat()` endpoint via `httpx.AsyncClient`, and verify the truncated message reaches both `HumanMessage` and `create_query_trace`. Use `unittest.mock.patch` or `monkeypatch` as appropriate.

## FR-002: Filter Key Whitelist

### Production Change (backend/retrieval/searcher.py)

1. Add module-level constant after imports, before `class HybridSearcher`:
```python
ALLOWED_FILTER_KEYS = {"doc_type", "source_file", "page", "chunk_index"}
```

2. In `_build_filter()`, add a guard inside the loop:
```python
        for key, value in filters.items():
            if key not in ALLOWED_FILTER_KEYS:
                continue  # FR-002: silently ignore unknown keys
            conditions.append(
                FieldCondition(key=key, match=MatchValue(value=value))
            )
```

**No new imports needed.**

### Test File (tests/unit/retrieval/test_searcher_security.py)

Write ~4 tests covering:
- Known filter key (`doc_type`) passes through to the Filter
- Unknown key (`arbitrary_field`) is silently dropped
- Mixed dict with one known + one unknown key results in filter with only the known key
- All-unknown filter dict returns `None` (unfiltered results)

**Test approach**: Instantiate `HybridSearcher` with a mock client/config and call `_build_filter()` directly. Assert on the returned `Filter` object's `must` conditions list.

## Key Constraints

- **NEVER run pytest directly** -- use `zsh scripts/run-tests-external.sh -n <name> <target>`
- **External test runner accepts ONE target** -- use separate invocations for multiple files
- **No new dependencies** -- these changes use only builtins
- **Silent behavior** -- FR-001 truncation and FR-002 filter ignoring are SILENT (no errors, no logs, no warnings)
- **Pre-existing failures: 39** -- any increase is a regression
- **Match existing code patterns** -- follow the style already in chat.py and searcher.py

## Test Execution

After implementing both FRs, run:
```bash
zsh scripts/run-tests-external.sh -n spec13-a2 tests/unit/
```

Poll status:
```bash
cat Docs/Tests/spec13-a2.status
cat Docs/Tests/spec13-a2.summary
```

## Success Criteria

- `backend/api/chat.py` has `message = body.message[:10_000]` and both `body.message` refs replaced
- `backend/retrieval/searcher.py` has `ALLOWED_FILTER_KEYS` constant and `_build_filter()` guard
- `tests/unit/api/test_chat_security.py` exists with ~4 passing tests
- `tests/unit/retrieval/test_searcher_security.py` exists with ~4 passing tests
- `Docs/Tests/spec13-a2.status` is `PASSED`
- No increase in pre-existing failure count

## After Completing All Tasks

Report completion to the orchestrator. The orchestrator will verify your test results before spawning Wave 3.
