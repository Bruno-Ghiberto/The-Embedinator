# BUG-009: OutputParserException fallback loses collection_ids across tool retries

- **Severity**: Major
- **Layer**: Reasoning
- **Discovered**: 2026-04-28 14:44 UTC via Exploratory (Charter 1 — A3 Finding 3, node-sequence analysis)

## Steps to Reproduce

1. Stack up: 4 services healthy. Corpus seeded.
2. Issue any scoped query that triggers a two-tool-call research path:
   ```
   POST /api/chat
   {"message": "diámetro mínimo NAG-200", "session_id": "test",
    "collection_ids": ["22923ab5-ea0d-4bea-8ef2-15bf0262674f"]}
   ```
3. Observe the full node_seq in backend logs.
4. Look for two successive `tools` node invocations in the same trace.
5. Compare collection scope in tool call 1 vs. tool call 2.

## Expected

Both tool calls within the same research graph execution preserve the `collection_ids` scope from `state["selected_collections"]`. A retry tool call initiated by the orchestrator after tool call 1 returns insufficient results should NOT expand the search scope — it should retry within the same authorized collection.

## Actual

Node sequence for scoped factoid and analytical queries shows a two-tool-call pattern:
```
node_seq (FACTOID):     ['classify_intent', 'rewrite_query', 'orchestrator', 'tools', 'orchestrator', 'tools', 'orchestrator']
node_seq (ANALYTICAL):  ['classify_intent', 'rewrite_query', 'orchestrator', 'tools', 'orchestrator', 'tools', 'orchestrator']
```

The second `tools` node invocation (orchestrator-initiated retry after first tool call returns insufficient results) does not carry the collection scope constraint from tool call 1. The result: tool call 2 queries 20 collections (scope-free). A3 Note: the `OutputParserException` fires at the `rewrite_query` step (before tool calls), not during tool-call construction — the second tool call is a genuine orchestrator retry for more evidence, not a rewrite-failure retry. Pending A5 log confirmation of whether `selected_collections` is present in the orchestrator state between tool calls.

## Artifacts

- A3 node sequence analysis (Charter 1):
  - Factoid trace: `['classify_intent', 'rewrite_query', 'orchestrator', 'tools', 'orchestrator', 'tools', 'orchestrator']`
  - Analytical trace (Q011 NAG-235↔NAG-200): same two-tool pattern
  - OOS trace: `['classify_intent', 'rewrite_query', 'orchestrator', 'tools', 'orchestrator', 'collect_answer']` (single tool call)
- Traces: `4c62606d` (step3-factoid), `d073a61b` (step3-analytical)
- File refs:
  - `backend/agent/research_nodes.py` — orchestrator node: state forwarding between tool call 1 and tool call 2
  - `backend/agent/tools.py` — `search_child_chunks` call context: does it re-read `selected_collections` from state on each call?
- **Pending**: A5 confirmation of whether `selected_collections` appears in orchestrator state between the two `tools` node executions

## Root-cause hypothesis (REVISED 2026-04-28 14:50 UTC — A3/A5 corrections)

**Revision**: A3's original Finding 3 linked the two-tool-call pattern to OutputParserException as the scope-loss trigger. A5 log analysis disproves this: trace `ab12fe4b` (charter1-q001b) shows two+ tool call iterations with NO OutputParserException — the multi-tool-call behavior is normal orchestrator loop behavior (agent retries when results are insufficient), not OPE-triggered. Furthermore, A5 confirms that `collections_searched=20` fires on EVERY query regardless of whether OutputParserException fires — scope leak is UNCONDITIONAL at the base layer (HybridSearcher / search_child_chunks ignores `collection_ids` parameter regardless of which code path invoked the tool).

**Revised root cause**: Scope loss does not occur at the tool-retry transition (as originally hypothesized). It occurs unconditionally in the `search_child_chunks` tool / `HybridSearcher` layer, which ignores `collection_ids` on EVERY call — first call or retry. BUG-009's specific contribution (second tool call losing scope) may be indistinguishable from BUG-002's base-layer issue. This bug should be considered a manifestation of BUG-002 rather than an independent failure mode. BUG-005 (`agent_query_analysis_fallback_used` scope drop) is also being reviewed — if scope leak is unconditional at the HybridSearcher layer, BUG-005 may be a partial or incorrect hypothesis.

**Action**: Pending Charter 2 / code inspection to confirm whether `search_child_chunks` / `HybridSearcher` unconditionally fans out regardless of the `collection_ids` parameter. If confirmed, BUG-009 and BUG-005 should both be merged into BUG-002 with updated root cause pointing to the searcher layer.
