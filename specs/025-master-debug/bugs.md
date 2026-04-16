# Spec-25 Bug Registry

**Last updated**: 2026-04-01 | **Phase**: P4 (Model Experimentation Matrix)

---

### BUG-P4-001: mistral:7b runaway research graph loop (Q3 — 591s TTFT)

- **Severity**: P1-HIGH
- **Phase**: P4 (Model Experimentation Matrix)
- **Component**: Backend — Inference Service / LangGraph Research Graph
- **Affected Spec**: Spec-02 (Conversation Graph), Spec-03 (Research Graph)
- **Steps to Reproduce**:
  1. Set default LLM to `mistral:7b` via `PUT /api/settings {"default_llm_model": "mistral:7b"}`.
  2. Send Q3 query: "¿Cuál es la diferencia entre WSFEV1 y WSBFEV1? ¿Qué tipo de comprobantes maneja cada servicio?"
  3. Observe TTFT measurement.
- **Expected Behavior**: Research graph completes in ≤120s (typical for 6-8 iterations at ~15s/iter).
- **Actual Behavior**: TTFT=591,074ms (591 seconds). Final response: "none sufficiently relevant" (1 chunk). Model consumed 9.8 minutes for a retrieval failure.
- **Log Evidence**:
  ```
  Q3 Comparison TTFT: 591074ms | Total: 591180ms | Chunks: 1 | Confidence: 0
  ```
- **Root Cause Analysis**: mistral:7b likely fails to emit a stop condition signal that the LangGraph research graph uses to terminate the iteration loop. The graph continues iterating until an external timeout or max-iterations guard. Mistral's instruction-following for JSON-structured termination signals appears to be weaker than the other tested models.
- **Fix Recommendation**: In `backend/agent/research_edges.py`, the `should_continue_loop` edge function should enforce a hard max-iterations guard (e.g., `max_iterations=8`) independent of model output. Additionally, add a wall-clock timeout check (e.g., `elapsed > 120s → force_stop=True`) in the research node loop.
- **Regression Test**: Integration test that sets `max_iterations=3` and asserts the research graph returns within 45s regardless of model termination signal. Add as `@pytest.mark.require_docker` test in `tests/integration/test_research_graph.py`.

---

### BUG-P4-002: Citation NDJSON events never emitted despite successful retrieval

- **Severity**: P1-HIGH
- **Phase**: P4 (Model Experimentation Matrix)
- **Component**: Backend — Research Graph / Chat API
- **Affected Spec**: Spec-03 (Research Graph), Spec-08 (API Reference)
- **Steps to Reproduce**:
  1. Run any chat query with a collection that has indexed documents.
  2. Observe the NDJSON stream from `POST /api/chat`.
  3. Check for events of type `citations`.
- **Expected Behavior**: When retrieval returns relevant chunks, a `{"type": "citations", "citations": [...]}` event is emitted in the NDJSON stream before the `done` event.
- **Actual Behavior**: No `citations` event is ever emitted across all 7 model combos and 35 query runs. All combos show `citation_count=0`. Models do produce inline `[N]` citation markers in text responses, confirming retrieval is working.
- **Log Evidence**:
  ```
  All 35 query runs: citation_count=0
  Example C1-Q2: 203 chunks retrieved, response contains "[9, 10]" inline markers, citation event=none
  Example C7-Q1: 159 chunks retrieved, response contains "[3][4]" inline markers, citation event=none
  ```
- **Root Cause Analysis**: The citation assembly node in the research/conversation graph likely populates `ConversationState.citations` but the chat streaming endpoint (`backend/api/chat.py`) does not serialize and emit the citations field as a separate NDJSON event. Alternatively, the citations event emission was removed or never connected during a recent graph refactor.
- **Fix Recommendation**: In `backend/api/chat.py`, after streaming all `chunk` events, check `state.get("citations", [])` and emit `{"type": "citations", "citations": state["citations"]}` if non-empty. Verify the research graph nodes populate `citations` in `ResearchState`.
- **Regression Test**: E2E test: ingest a document, send a domain query, stream the response, assert at least one `citations` event with `len(citations) > 0` appears in the stream.
