# Agent: Dispatch & Aggregation

**Mission**: Implement the `handle_collection_mgmt` stub, `aggregate_answers` node, and `format_response` node for answer merging, citation deduplication, and response formatting.

**Subagent Type**: `python-expert`
**Model**: `sonnet`
**Wave**: 2 (Parallel -- runs in worktree alongside Agents A, B, D)

## Assigned Tasks

- **T017**: Implement `handle_collection_mgmt(state: ConversationState) -> dict` stub in `backend/agent/nodes.py` -- sets `final_response` to `"Collection management is not yet implemented. Please use the Collections page."` and `confidence_score` to `0`
- **T022**: Implement `aggregate_answers(state: ConversationState) -> dict` in `backend/agent/nodes.py` -- collect all `SubAnswer` objects from `state["sub_answers"]`; merge answer texts with sub-question headers; deduplicate citations by `passage_id` keeping highest `relevance_score`; compute `confidence_score` as `int(weighted_avg * 100)` using `compute_confidence()` from `backend/agent/confidence.py`; write `state["final_response"]` and `state["citations"]`
- **T025**: Implement `format_response(state: ConversationState) -> dict` in `backend/agent/nodes.py` -- call `FORMAT_RESPONSE_SYSTEM` with `final_response` + citations as numbered list `[1] passage_text...`; apply inline `[N]` citation markers by matching citation indices; append confidence summary if `confidence_score < 70`; handle `groundedness_result=None` (Phase 1: skip annotation); update `state["final_response"]`

## Files Modified

| File | Changes |
|------|---------|
| `backend/agent/nodes.py` | Replace `handle_collection_mgmt`, `aggregate_answers`, and `format_response` stubs with implementations |

## Constraints

### handle_collection_mgmt

- This is a stub -- out of scope for this spec
- Must return `{"final_response": "Collection management is not yet implemented. Please use the Collections page.", "confidence_score": 0}`
- No LLM call, no side effects

### aggregate_answers

- Collect `SubAnswer` objects from `state["sub_answers"]`
- If `sub_answers` is empty or all failed: set `final_response` to an appropriate "no results" message
- Merge answer texts: prefix each with its sub-question as a header for context
- Deduplicate citations by `passage_id`: when duplicates exist, keep the one with the highest `relevance_score`
- Compute `confidence_score` using `compute_confidence()` from `backend/agent/confidence.py` -- this returns a weighted average. Convert to `int` on 0-100 scale: `int(weighted_avg * 100)`
- Import `compute_confidence` from `backend.agent.confidence`
- Return `dict` with `{"final_response": merged_text, "citations": deduped_citations, "confidence_score": score}`
- Handle partial failures: if some sub-answers have `answer=None`, skip them and aggregate the rest. Note gaps in the merged text.

### format_response

- Use `FORMAT_RESPONSE_SYSTEM` prompt from `backend.agent.prompts`
- Build a numbered citation reference list: `[1] citation.text`, `[2] citation.text`, etc.
- Apply inline `[N]` markers in the response text where claims are supported
- If `confidence_score < 70`: append a confidence summary note to the response
- If `groundedness_result is None` (Phase 1 default): skip groundedness annotations entirely -- do NOT annotate `[unverified]` or remove claims
- When `groundedness_result` is populated (Phase 2): annotate unsupported claims with `[unverified]`, remove contradicted claims
- Return `dict` with `{"final_response": formatted_text}`
- Use `format_passages_for_prompt()` from `backend.agent.citations` if helpful for building the citation list

### General

- Use `structlog.get_logger()` for logging
- All functions return `dict` (partial state update)
- Reuse existing schemas from `backend.agent.schemas`: `SubAnswer`, `Citation`
- Reuse existing utilities: `compute_confidence` from `backend.agent.confidence`, `format_passages_for_prompt` from `backend.agent.citations`

## Dependencies

- Wave 1 (Scaffold) must be complete: `nodes.py` exists with stubs, `prompts.py` has `FORMAT_RESPONSE_SYSTEM`
- `SubAnswer`, `Citation` models exist in `backend/agent/schemas.py`
- `compute_confidence` exists in `backend/agent/confidence.py`
- `format_passages_for_prompt` exists in `backend/agent/citations.py`

## Done Criteria

- [ ] `handle_collection_mgmt` returns stub response with `confidence_score=0`
- [ ] `aggregate_answers` merges multiple `SubAnswer` texts with sub-question headers
- [ ] `aggregate_answers` deduplicates citations by `passage_id`, keeping highest `relevance_score`
- [ ] `aggregate_answers` computes `confidence_score` as int 0-100 via `compute_confidence()`
- [ ] `aggregate_answers` handles empty `sub_answers` list gracefully
- [ ] `aggregate_answers` handles partial failures (some sub-answers with `answer=None`)
- [ ] `format_response` applies inline `[N]` citation markers
- [ ] `format_response` appends confidence summary when `confidence_score < 70`
- [ ] `format_response` skips groundedness annotations when `groundedness_result is None`
- [ ] No function raises unhandled exceptions
