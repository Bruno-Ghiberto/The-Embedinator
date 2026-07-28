# BUG-088: In-flight LLM call has no enforced timeout; backend hangs unbounded, leaks task

- **Severity**: CRITICAL
- **Layer**: Backend
- **Discovered**: 2026-07-08T19:50:19Z in Phase 4 (P4-S6)
- **Phase scenario**: P4-S6
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Submit a normal chat query while the LLM backend (Ollama) is available.
2. While an orchestrator LLM call is in-flight (`await llm_with_tools.ainvoke()`), make the LLM backend unresponsive (live repro: `docker pause embedinator-ollama` for ~40s, then unpause).
3. Observe: neither the provider's `request_timeout` NOR the graph's `max_loop_seconds` cap interrupts the in-flight call while it is stalled. The call is NOT permanently stuck — it eventually returns — but it runs unbounded for far longer than either configured limit: in the live repro it returned after **553.4s (9m13s)**, 4.6× the 120s `request_timeout` and 1.8× the 300s `max_loop_seconds` cap. Neither limit fired DURING the stall; the loop-deadline check only fired 1.7s AFTER the node had already returned on its own.

## Expected
A single in-flight LLM call has an enforced upper-bound timeout; if exceeded, the request fails gracefully within a bounded window (error surfaced to the user, task cancelled) rather than running unbounded for however long the underlying stall happens to last.

## Actual
Live-reproduced during P4-S6 (trace `8ba310a8-661e-4979-a9b3-b54480ec298b`, collection `nag-corpus-bm25`, `qwen2.5:7b`): query submitted 19:50:10Z; iteration-0 orchestrator + retrieval completed normally (dedup 5→4, a BUG-085 recurrence). Iteration-1 orchestrator LLM call started (`agent_orchestrator_start`) at 19:50:19.913Z. The LLM backend was paused at 19:50:59Z and unpaused at 19:51:40Z (~40s outage). Corrected timeline (log-analyst revision): the call did NOT hang forever — it RETURNED at 19:59:33.343860Z, **553.4s after start**, with a real decision (`agent_orchestrator_decision`, `num_tool_calls=2`). Immediately after, `agent_loop_exit_deadline` fired (elapsed 555.1s vs. `max_loop_seconds=300`) and correctly routed to `fallback_response()`. So the defect is not an infinite/permanent hang — it is that **neither configured limit can interrupt or even bound an in-flight node await**: `request_timeout=120.0` never fired despite the call running 4.6× past it, and `max_loop_seconds=300` could only be checked at the post-node iteration boundary (555.1s, AFTER the node had already returned), 1.8× past its own configured budget. From the user's perspective this reads as an indefinite hang regardless — the frontend had already given up with an empty bubble around the ~30s mark (see BUG-074), long before the backend call resolved on its own 553s later.

**Compounding discovery**: once `fallback_response()` produced its correct, deterministic answer (`agent_fallback_triggered`, 19:59:33.344987Z), the result was never delivered — it was silently discarded by the uncaught-`CancelledError` mechanism described in BUG-073 (no `query_traces` row through 20:03:37Z, no `done`/error event). The task ran orphaned for the full 553s stall duration while the client was already long gone; the correctly-recovered answer at the end of that work was then lost anyway.

## Artifacts
- Log excerpt: logs/BUG-088-orchestrator-hang.log (gitignored) — backend log window covering the full stall + eventual return + deadline-triggered fallback, trace `8ba310a8-661e-4979-a9b3-b54480ec298b`.
- Screenshot: null
- Trace: null

## Root-cause hypothesis
HIGH confidence, code-confirmed (log-analyst). Two compounding gaps, both confirmed by the corrected timeline:

**(a) No enforced per-call timeout.** `ChatOllama`'s `request_timeout=120.0` (`backend/providers/registry.py:89`) did NOT bound this call — it ran 553.4s, 4.6× that budget, with the call eventually completing normally rather than raising a timeout exception. Either `request_timeout` doesn't map to an enforced `httpx` client-level timeout in this `langchain-ollama` version, or it doesn't apply cleanly to a connection frozen by a `docker pause` — either way, in this build, it is not enforced as a hard ceiling.

**(b) `max_loop_seconds` is edge-checked, not node-bounded.** `max_loop_seconds=300` is only checked inside `should_continue_loop()` (`backend/agent/research_edges.py:19`, lines 49-56) — a LangGraph EDGE function that runs only AFTER a node returns control to the graph. `orchestrator()` (`research_nodes.py:87`) was stuck inside `await llm_with_tools.ainvoke()` (line 190) for the full 553.4s and could not return early, so the edge function could not run and the 300s cap could not fire during the stall — it only fired 1.7s after the node happened to return on its own (555.1s total), confirming `max_loop_seconds` bounds cumulative time across COMPLETED iterations, not a single in-flight node await.

**Open reconciliation item (not blocking, noted for follow-up)**: the interim diagnosis stated the request "never reached Ollama's application layer" (health polls resumed immediately post-unpause with no corresponding `/api/chat` log line at the app layer), yet the call ultimately returned a real, well-formed decision (`num_tool_calls=2`) at 553.4s. These two observations are not yet reconciled — it's unclear whether the request was queued/retried at a transport layer invisible to Ollama's request log, or another mechanism resumed it. This does not change the defect (neither timeout bounded the wait either way) but is flagged as unresolved.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: v1.0-fix
- **GitHub issue**: https://github.com/Bruno-Ghiberto/The-Embedinator/issues/156
- **Rationale**: Neither request_timeout=120s nor max_loop_seconds=300 can bound an in-flight node await — the call ran 553.4s (4.6x and 1.8x past those limits) while the user saw an indefinite hang, and the orphaned task's correct answer was then discarded.

## Notes
Dedup-check performed before minting: confirmed distinct from BUG-082 (`classify_intent ↔ request_clarification` infinite LOOP — a different mechanism where the graph keeps re-entering and returning from nodes each cycle; that loop is eventually cut short by the ~30s client-side idle-timeout cancellation chain, BUG-054→073→074) and from BUG-054/073/074/075 (the frontend-visible cancellation chain triggered by the client-side idle timeout). BUG-088 is a distinct failure: a SINGLE node's LLM call itself does not return control to the graph for 553s, with no enforced backend-side ceiling of any kind bounding that wait — worse than either prior mechanism even though (per the correction above) it is not a truly permanent/unrecoverable hang.

Fix surface: wrap the `ainvoke()` call in an explicit `asyncio.wait_for(...)` with a real deadline (don't rely solely on the provider's `request_timeout` reaching an enforced transport-level timeout), and/or enforce the wall-clock deadline against in-node awaits directly (not only in the edge function) so a single stalled node cannot run 4-9× past every configured limit before the graph even notices.

Cross-ref BUG-073 (STRONG UPDATE, 2026-07-08): the correctly-recovered `fallback_response()` answer this call eventually produced was silently discarded by BUG-073's uncaught-`CancelledError` mechanism — compounding this defect's impact from "a very slow but eventually-successful response" into "9 minutes of real backend work, including a correct fallback answer, permanently lost with no trace record." Cross-ref BUG-082 (sibling unbounded-hang class, different mechanism), BUG-054/074/075 (sibling cancellation-chain class, different mechanism).

Evidence: trace `8ba310a8-661e-4979-a9b3-b54480ec298b`; iteration-0 dedup 5→4 recurrence cross-refs BUG-085 (same collision mechanism, different collection).
