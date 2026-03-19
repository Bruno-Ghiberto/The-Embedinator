# Agent: Polish

**Mission**: Perform cross-cutting validation of the full implementation: coverage verification, NDJSON contract compliance, source_removed field, quickstart validation, and CLAUDE.md documentation update.

**Subagent Type**: `self-review`
**Model**: `opus`
**Wave**: 6 (Sequential -- after all Wave 5 test agents complete)

## Assigned Tasks

- **T048**: Run `pytest --cov=backend --cov-report=term-missing` and verify >=80% line coverage; add targeted unit tests for any uncovered branches in `nodes.py` or `edges.py`
- **T049**: Verify all NDJSON output frames match `contracts/chat-api.md` schema -- write a frame-schema validation helper in `tests/unit/test_ndjson_frames.py` that parses each frame type and validates required fields
- **T050**: Add `source_removed: bool` field to Citation serialization in `format_response` -- check document deletion status before building metadata frame (Constitution Principle IV requires `source_removed: true` indicator)
- **T051**: Run `quickstart.md` validation steps manually -- verify graph compiles, mock ResearchGraph works, all 3 intent routes produce valid NDJSON output
- **T052**: Update `CLAUDE.md` with new agent modules: `nodes.py`, `edges.py`, `conversation_graph.py`, `data/checkpoints.db` location

## Files Created

| File | Purpose |
|------|---------|
| `tests/unit/test_ndjson_frames.py` | Frame-schema validation for all NDJSON frame types |

## Files Modified

| File | Changes |
|------|---------|
| `backend/agent/nodes.py` | Add `source_removed` to Citation serialization in `format_response` (T050) |
| `CLAUDE.md` | Add new module documentation (T052) |
| `tests/unit/test_nodes.py` | Add coverage gap tests if needed (T048) |
| `tests/unit/test_edges.py` | Add coverage gap tests if needed (T048) |

## Constraints

### Coverage (T048)

- Run `pytest --cov=backend --cov-report=term-missing`
- Target: >=80% line coverage for `backend/` directory
- Focus on uncovered branches in `nodes.py` and `edges.py`
- If coverage is below 80%, write targeted tests for the uncovered lines
- Do NOT write redundant tests for already-covered paths

### NDJSON Frame Validation (T049)

Validate against `specs/002-conversation-graph/contracts/chat-api.md`:

**Chunk frame**:
- Required fields: `type` (must be `"chunk"`), `text` (string)
- No extra required fields

**Clarification frame**:
- Required fields: `type` (must be `"clarification"`), `question` (string)

**Metadata frame**:
- Required fields: `type` (must be `"metadata"`), `trace_id` (string), `confidence` (int 0-100), `citations` (list), `latency_ms` (int)
- Each citation in list: `passage_id`, `document_id`, `document_name`, `text`, `relevance_score`, `source_removed`

**Error frame**:
- Required fields: `type` (must be `"error"`), `message` (string), `code` (string)
- Valid codes: `NO_COLLECTIONS`, `EMPTY_COLLECTIONS`, `EMPTY_MESSAGE`, `MESSAGE_TOO_LONG`, `INTERNAL_ERROR`

### source_removed Field (T050)

- In `format_response` or in the metadata frame construction in `chat.py`, each `Citation` must include `source_removed: bool`
- This indicates whether the source document has been deleted since the passage was indexed
- Check document existence before building the metadata frame
- Default to `false` if check fails or cannot be performed
- This is required by Constitution Principle IV (Observability from Day One)

### Quickstart Validation (T051)

Follow the steps in `specs/002-conversation-graph/quickstart.md`:

1. Verify `langgraph-checkpoint-sqlite` is installed
2. Verify Phase 1 modules are importable
3. Verify existing 61 tests still pass
4. Verify graph compiles with mock ResearchGraph
5. Verify all 3 intent routes produce valid output:
   - `rag_query`: graph proceeds through full RAG path
   - `collection_mgmt`: graph returns stub response
   - `ambiguous`: graph triggers clarification interrupt

### CLAUDE.md Update (T052)

Add entries for new modules under the project structure:

```
backend/agent/conversation_graph.py  # StateGraph definition + compile
backend/agent/nodes.py               # 11 node function implementations
backend/agent/edges.py               # 3 conditional edge functions
data/checkpoints.db                  # LangGraph checkpoint storage (auto-created)
```

Also update the commands section if any new test commands apply.

## Dependencies

- Wave 5 (both test agents) must be complete: all tests written and passing
- All implementation files must be finalized
- No pending merge conflicts from worktree agents

## Done Criteria

- [ ] `pytest --cov=backend --cov-report=term-missing` shows >=80% line coverage
- [ ] `tests/unit/test_ndjson_frames.py` validates all 4 frame types against contract
- [ ] All NDJSON frames include required fields per `contracts/chat-api.md`
- [ ] Citation serialization includes `source_removed: bool` field
- [ ] Quickstart validation passes: graph compiles, mock works, all intent routes valid
- [ ] Existing 61 Phase 1 tests still pass (no regressions)
- [ ] `CLAUDE.md` updated with new module paths and checkpoint DB location
- [ ] Full test suite passes: `pytest -v`
- [ ] `ruff check .` reports no linting errors in new files
