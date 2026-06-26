# BUG-012: Citation renderer may be upstream of dedup filter (tentative — pending Charter 2 UI probe)

- **Severity**: Major (tentative — downgrade to Minor or close if Charter 2 UI probe disproves)
- **Layer**: Frontend
- **Discovered**: 2026-04-28 14:50 UTC via Log hypothesis (A5 Charter 1 analysis + A3 correlation); NOT yet UI-confirmed

> ⚠️ **TENTATIVE BUG** — Filed based on log-side hypothesis. Charter 2 UI probe required to confirm or close. Do not use as basis for F/D/P decision until confirmed.

## Steps to Reproduce (hypothetical — pending UI confirmation)

1. Stack up. Issue a query that triggers two tool calls (search_child_chunks → cross_encoder_rerank).
2. Observe the citation panel in the frontend as the NDJSON stream arrives.
3. Count citations shown DURING streaming vs. citations in the final settled state.
4. If the UI shows more citations mid-stream than in the final answer, the renderer is emitting citation events before the dedup filter runs.

## Expected

Citation events are emitted AFTER dedup filtering. The UI renders only citations that the LLM received as evidence (post-dedup). No "ghost citations" appear mid-stream and then disappear.

## Actual (hypothetical — log-side inference only)

A5 hypothesis: `agent_tool_call_complete` citation stream events may be emitted before `agent_dedup_filtered` runs. If so, the UI citation panel initially populates with raw retrieval results (from all 20 collections), then partially clears as dedup completes — or worse, retains all pre-dedup citations if the renderer does not handle the dedup event.

Evidence for hypothesis: OOS trace `f85602ba` shows `agent_aggregate_answers_merged` with `num_citations=5` but `agent_format_response_formatted` with `num_citations=20`. The jump from 5 to 20 between aggregation and formatting suggests citation expansion happening in the formatting step, which is AFTER dedup. A3 notes this may instead be normal citation-list expansion (1 chunk → N formatted citations). Needs UI charter to confirm.

## Artifacts

- Trace: `f85602ba-16b5-41ea-8313-7732e78c4fe0` (OOS probe)
  - `agent_aggregate_answers_merged`: confidence_score=34, num_citations=5
  - `agent_format_response_formatted`: confidence_score=34, num_citations=20
- A5 log hypothesis note: "Citation rendering is upstream of dedup. Flag for Charter 2 if UI charter confirms this."
- A3 alternative hypothesis: num_citations jump from 5→20 may be normal (1 chunk → multiple formatted citation entries), not a renderer ordering issue

## Root-cause hypothesis

If confirmed: the citation streaming pipeline emits chunk-level citation events before the dedup step finalizes the working memory, causing the UI to display pre-dedup citations from all 20 leaked collections before the dedup removes them. If dedup then removes them server-side but the client does not receive a "remove citation" event, the UI retains the ghost citations permanently.

If disproved (Charter 2 confirms 5→20 is normal formatting expansion): close this bug and update BUG-002 with a note that the 20-citation count in `format_response` is formatting-level expansion, not a renderer ordering issue.

**Charter 2 action**: navigate to chat page, issue a query, inspect the citation panel as the NDJSON stream arrives. Count citation elements appearing in real-time vs. in the settled final state. Screenshot both states.
