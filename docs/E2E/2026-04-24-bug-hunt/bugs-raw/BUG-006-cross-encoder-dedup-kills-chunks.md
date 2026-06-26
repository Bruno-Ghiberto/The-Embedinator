# BUG-006: Dedup-after-rerank zeros out citations on 75% of queries

- **Severity**: Blocker
- **Layer**: Reasoning
- **Discovered**: 2026-04-28 14:38 UTC via Live Block Charter 1 (A5 log analysis of A3's blast-radius probe runs)
- **F/D/P decision**: F (fix in-session; commit 6d8b27a; tests in tests/unit/test_research_nodes.py — TestRerankScoreUpdate class, 3 tests; live verify deferred — see BUG-013)

## Steps to Reproduce

1. Stack up: 4 services healthy. Corpus seeded.
2. Issue same factoid query 4× with distinct session_ids:
   ```
   POST /api/chat
   {"message": "diámetro mínimo NAG-200", "session_id": "blast-N", "collection_ids": ["22923ab5-ea0d-4bea-8ef2-15bf0262674f"]}
   ```
3. For each, observe whether the agent uses 1 tool call (search only) or 2 tool calls (search + cross_encoder_rerank). The choice appears stochastic/non-deterministic across identical queries.

## Expected

Reranked chunks are passed forward to answer generation as evidence — they're the SAME chunks the search returned, just re-ordered by relevance. Dedup against prior-iteration chunks should NOT eliminate them, since they aren't duplicates — they're the only chunks the agent has.

## Actual

When the agent invokes cross_encoder_rerank as a 2nd tool call, `agent_dedup_filtered` fires immediately after with `original: 5, kept: 0` — every reranked chunk is filtered as a duplicate. The agent then exhausts iterations (3 max), exits via `agent_loop_exit_exhausted` with confidence=0 and 0 citations. User sees "I searched N collection(s) and found N passage(s), but none were sufficiently relevant" — even though rerank ranked them as relevant.

## Artifacts

- A5 log analysis traces:
  - charter1-blast-1 (`d01799b7`): confidence=0, num_citations=0, dedup `original: 5, kept: 0`
  - charter1-blast-2 (`2cb0daa4`): same — dedup `original: 5, kept: 0`
  - charter1-blast-3 (`dbc3da00`): same pattern → `agent_loop_exit_exhausted`, confidence=0
  - charter1-blast-4 (`4cdd47d6`): **CONTROL** — no rerank path → routing=sufficient → confidence=48, num_citations=4/16
  - charter1-verify (`fc5518e8`): `agent_dedup_filtered` original=5, kept=0, timestamp 14:35:08 UTC:
    ```
    {"tool": "cross_encoder_rerank", "original": 5, "kept": 0, "event": "agent_dedup_filtered",
     "trace_id": "fc5518e8-99eb-4534-9b98-8dd81e51ace0", "timestamp": "2026-04-28T14:35:08.201368Z"}
    {"tool": "cross_encoder_rerank", "new_chunks": 0, "tool_call_count": 2, "event": "agent_tool_call_complete",
     "trace_id": "fc5518e8-...", "timestamp": "2026-04-28T14:35:08.201497Z"}
    ```
- File refs (probable):
  - `backend/agent/research_nodes.py` — search for `agent_dedup_filtered` event
  - `backend/agent/research_nodes.py` — search for cross_encoder_rerank handling logic
  - Likely the dedup step compares incoming chunks (post-rerank) against `state["retrieved_chunks"]` which already contains those same chunks from the prior search step → all match by `chunk_id` → all dropped.

## Root-cause hypothesis

The dedup logic after `cross_encoder_rerank` is comparing the reranked output against `state["retrieved_chunks"]` (the chunks accumulated from PREVIOUS tool calls including the rerank's input). Since rerank doesn't change `chunk_id`, every reranked chunk matches an already-stored chunk by id and is dropped as a duplicate. The bug is conceptual: dedup should distinguish "new chunks from a NEW search" (real duplicates worth filtering) from "same chunks reordered by rerank" (legitimate re-evaluation, not duplicates). Likely fix: skip the dedup step when the prior tool call was rerank, OR compare chunks across iterations not within a single iteration's tool-call chain.

## Causal context

This is downstream of BUG-003 (OutputParserException loop) only insofar as both compound to make the agent produce empty answers. BUG-006 stands on its own: it would still fire even if BUG-003 were fixed, because the rerank-then-dedup logic is buggy independently. Hit rate: 75% (3 of 4 blast-phase traces that called rerank ended at confidence=0). The 25% (blast-4) escaped only because it exited via `routing=sufficient` after tool call 1 without invoking rerank.
