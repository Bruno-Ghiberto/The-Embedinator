# Agent: A3-validate-citations

**subagent_type**: python-expert | **Model**: Sonnet 4.6 | **Wave**: 2

## Mission

Implement the `validate_citations` node body and `_extract_claim_for_citation` helper in `backend/agent/nodes.py`. This node validates every inline citation by scoring the relevance of the cited chunk against the surrounding claim via the cross-encoder reranker. Citations scoring below the alignment threshold are remapped to the best alternative chunk or stripped entirely.

## Context Files (Read FIRST)

1. `Docs/PROMPTS/spec-05-accuracy/05-implement.md` -- code specs (authoritative reference for function bodies)
2. `backend/agent/nodes.py` -- existing stub at lines 360-363 (replace with full implementation)
3. `backend/agent/schemas.py` -- `Citation` model (lines 82-92), `SubAnswer` model (lines 95-100), `RetrievedChunk` model
4. `backend/retrieval/reranker.py` -- `Reranker` class with `model.rank()` API
5. `backend/agent/state.py` -- `ConversationState` TypedDict (has `citations`, `sub_answers`, `final_response`)
6. `backend/config.py` -- `settings.citation_alignment_threshold` (float, default 0.3)
7. `specs/005-accuracy-robustness/spec.md` -- US2 acceptance scenarios
8. `specs/005-accuracy-robustness/research.md` -- R3: citation claim text extraction decision

## Assigned Tasks

- T013: [P] Add `_extract_claim_for_citation(text: str, marker: str) -> str` regex helper in `backend/agent/nodes.py` -- splits on sentence boundaries (`(?<=[.!?])\s+`), finds sentence containing `marker` (e.g. `[1]`), falls back to first 200 chars
- T014: Implement `validate_citations` node body in `backend/agent/nodes.py` (replaces stub at lines 360-363): (1) for each citation in `state["citations"]`, extract claim text via `_extract_claim_for_citation`; (2) score `(claim_text, chunk.text)` pairs via `reranker.model.rank()` (reuse existing `CrossEncoder` from `backend/retrieval/reranker.py`); (3) if score < `settings.citation_alignment_threshold`: remap to highest-scoring chunk that clears threshold, or strip citation entirely if none qualifies; (4) return `{"citations": corrected}`; (5) catch all exceptions -> return `{"citations": state["citations"]}` + log warning
- T015: Add unit tests for `_extract_claim_for_citation` in `tests/unit/test_accuracy_nodes.py`: marker found in middle sentence, marker at sentence start, marker in last sentence, no sentence match returns fallback to first 200 chars
- T016: Add unit tests for `validate_citations` node in `tests/unit/test_accuracy_nodes.py`: citation scores above threshold preserved unchanged; citation scores below threshold remapped to best chunk; no chunk clears threshold results in citation stripped; reranker raises exception causes pass-through unvalidated
- T017: Run US2 unit tests: `zsh scripts/run-tests-external.sh -n spec05-us2 --no-cov tests/unit/test_accuracy_nodes.py` -- poll `cat Docs/Tests/spec05-us2.status` until PASSED

## Files to Create/Modify

- MODIFY: `backend/agent/nodes.py` (add `_extract_claim_for_citation` helper, replace `validate_citations` stub with full implementation)
- MODIFY: `tests/unit/test_accuracy_nodes.py` (fill in `TestValidateCitations` test class)

## Key Patterns

- **Function signature**: `async def validate_citations(state: ConversationState, *, reranker: Any = None) -> dict:` -- keep the existing `*, reranker` keyword arg pattern.
- **Reranker API for citation scoring**: Use `reranker.model.rank(query, documents, return_documents=False)` which returns a list of dicts with `"score"` keys. This is the `sentence_transformers.CrossEncoder.rank()` API.
  - Example: `scores = reranker.model.rank(claim_text, [chunk_text], return_documents=False)` returns `[{"corpus_id": 0, "score": 0.85}]`
  - For batch scoring: `scores = reranker.model.rank(claim_text, [chunk1.text, chunk2.text, ...], return_documents=False)` returns `[{"corpus_id": 0, "score": 0.85}, {"corpus_id": 1, "score": 0.22}, ...]`
- **Citation marker pattern**: Citations appear as `[1]`, `[2]`, etc. in the response text. For citation at index `i` (0-based), the marker is `f"[{i + 1}]"`.
- **Claim extraction**: `_extract_claim_for_citation(final_response, marker)` finds the sentence containing the marker.
- **Remapping**: When a citation scores below threshold, score ALL available chunks from `sub_answers` against the claim text. If the best-scoring chunk clears the threshold, update the citation's `passage_id`, `text`, and `relevance_score` to point to that chunk.
- **Stripping**: If no chunk clears the threshold, the citation is simply omitted from the corrected list.
- **Return partial dict**: `return {"citations": corrected}` -- NOT `{**state, ...}`.
- **Graceful degradation (FR-008)**: On ANY exception, return `{"citations": state["citations"]}` (pass-through unvalidated) and log warning.
- **Performance constraint (SC-010)**: Citation validation must complete in under 50ms per answer. The `model.rank()` call is fast for small batches (10 citations typical).

## CRITICAL: Shared File with A2 and A4

You (A3) add `_extract_claim_for_citation` and replace the `validate_citations` stub. A2 (running in parallel) adds `_apply_groundedness_annotations` and replaces `verify_groundedness`. A4 (running in parallel) adds `TIER_PARAMS` and extends `rewrite_query`. You all work on DIFFERENT functions in the SAME file. Do NOT touch:
- `verify_groundedness` (A2's responsibility)
- `_apply_groundedness_annotations` (A2's responsibility)
- `TIER_PARAMS` (A4's responsibility)
- `rewrite_query` (A4's responsibility)
- Any other existing functions

## Test Patterns

```python
# Mock reranker:
mock_reranker = MagicMock()
mock_reranker.model = MagicMock()

# Citation above threshold:
mock_reranker.model.rank.return_value = [{"corpus_id": 0, "score": 0.85}]

# Citation below threshold (remap scenario):
# First call: score < threshold for original citation
# Second call: score best alternative chunks
mock_reranker.model.rank.side_effect = [
    [{"corpus_id": 0, "score": 0.1}],  # original citation score
    [{"corpus_id": 0, "score": 0.9}, {"corpus_id": 1, "score": 0.2}],  # all chunks scored
]

# Build test citation:
from backend.agent.schemas import Citation
citation = Citation(
    passage_id="p1", document_id="d1", document_name="doc.pdf",
    start_offset=0, end_offset=100, text="Some chunk text",
    relevance_score=0.8,
)

# Build test state:
state = {
    "session_id": "test-123",
    "citations": [citation],
    "final_response": "The API supports version 2.0 [1]. It also has rate limiting.",
    "sub_answers": [
        SubAnswer(sub_question="q1", answer="a1", citations=[], chunks=[
            RetrievedChunk(chunk_id="c1", text="API version 2.0 docs", source_file="f.pdf",
                          breadcrumb="b", parent_id="p1", collection="col1",
                          dense_score=0.5, sparse_score=0.3),
        ], confidence_score=80),
    ],
}
```

## Constraints

- NEVER run pytest inside Claude Code. Use: `zsh scripts/run-tests-external.sh -n <name> <target>`
- NEVER touch `verify_groundedness`, `_apply_groundedness_annotations`, `rewrite_query`, `TIER_PARAMS`, or any function outside your scope
- NEVER modify `schemas.py`, `reranker.py`, `state.py`, `config.py`, or `conversation_graph.py`
- NEVER call `reranker.rerank()` -- use `reranker.model.rank()` directly for citation scoring
- `_extract_claim_for_citation` is a regular sync function, NOT async
- Place `_extract_claim_for_citation` BEFORE `validate_citations` in the file (helper before consumer)
- Add `import re` at the top of `nodes.py` if not already present (A2 may also add it)
- Use `monkeypatch.setattr()` for settings overrides in tests, NOT `os.environ[]`

## Checkpoint

`validate_citations` replaces the stub, `_extract_claim_for_citation` extracts sentences correctly. Running the following succeeds:
```bash
python -c "from backend.agent.nodes import validate_citations, _extract_claim_for_citation; print('OK')"
ruff check backend/agent/nodes.py
```
