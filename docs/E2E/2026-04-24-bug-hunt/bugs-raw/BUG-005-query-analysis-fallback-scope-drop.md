# BUG-005: agent_query_analysis_fallback_used drops collection scope context

- **Severity**: Major
- **Layer**: Reasoning
- **Discovered**: 2026-04-28 14:38 UTC via Log scan (A5 Charter 1 — event first seen 2026-04-14 session `649f4c31`, confirmed consistently across all sessions)

## Steps to Reproduce

1. Stack up with ≥1 Qdrant collection scoped in the chat request.
2. Issue a chat request with `collection_ids` set (any query).
3. Observe backend logs: `agent_rewrite_query_first_attempt_failed` fires (BUG-003, 100% hit rate), then `agent_rewrite_query_fallback`, then `agent_query_analysis_fallback_used`.
4. Observe `agent_orchestrator_start` fires immediately after — the `sub_question` field contains the raw user query text, but NO collection scope constraint is present in the orchestrator's starting state.
5. Research graph executes scope-free → `retrieval_search_all_complete` with `collections_searched: 20`.

## Expected

When the query rewriter fails and the fallback path is taken, the collection scope context from `state["selected_collections"]` is preserved and forwarded to the research graph. The `agent_orchestrator_start` event should include the collection constraint so the research graph searches only authorized collections.

## Actual

`agent_query_analysis_fallback_used` routes from the failed query rewriter back to the research graph using the raw user query text as `sub_question` but silently drops the collection scope context. The research graph receives no collection constraint and fans out to all 20 available Qdrant collections. First seen 2026-04-14 (session `649f4c31`); confirmed on every session since — this is systematic, not intermittent. Observable log signature: `agent_query_analysis_fallback_used` in `backend.agent.nodes`, immediately followed by `agent_orchestrator_start` with no collection filter.

## Artifacts

- Log excerpt (Charter 1, trace `fc5518e8-99eb-4534-9b98-8dd81e51ace0`):
  ```
  14:34:44 [warning] agent_rewrite_query_first_attempt_failed component=backend.agent.nodes error=OutputParserException session_id=charter1-verify trace_id=fc5518e8-99eb-4534-9b98-8dd81e51ace0
  14:34:47 [warning] agent_rewrite_query_fallback component=backend.agent.nodes error=OutputParserException session_id=charter1-verify trace_id=fc5518e8-99eb-4534-9b98-8dd81e51ace0
  {"component": "backend.agent.research_nodes", "sub_question": "diámetro mínimo NAG-200", "event": "agent_orchestrator_start", "trace_id": "fc5518e8-...", "timestamp": "2026-04-28T14:34:49.018376Z"}
  ```
- Full Charter 1-verify chain outcome: `agent_loop_exit_exhausted` → `confidence_score=0, num_citations=0` (see BUG-002)
- First historical occurrence: session `649f4c31`, 2026-04-14
- All 6 spec-28 sessions show this event in the same position in the log chain
- File ref: `backend/agent/nodes.py` (query_analysis_fallback transition handler — the state forwarded to research graph does not carry `selected_collections`)

## Root-cause hypothesis

The `agent_query_analysis_fallback_used` transition in `backend/agent/nodes.py` was written to recover gracefully from parser failures by passing the raw query forward. However, the state object forwarded to the research graph is constructed from the fallback path without copying `state["selected_collections"]` — it likely constructs a fresh or partial state dict containing only the `sub_question` field. Since `selected_collections` is absent from the research graph's initial state, the graph treats the request as collection-scope-free and invokes `search_all_collections`. Fix: the fallback transition must explicitly forward `state["selected_collections"]` to the research graph's initial state. This is the proximate root cause of BUG-002's 20-collection blast; BUG-003 (OutputParserException, 100% hit rate) is the upstream trigger that forces every request through this broken path.

**Causal chain**: BUG-003 (OutputParserException on every query rewrite) → **BUG-005** (scope drop in query_analysis_fallback) → BUG-002 (20-collection fan-out, leaked chunks) → `confidence_score=0, num_citations=0` (user-facing Blocker impact).
