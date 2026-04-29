# BUG-002: Collection-scope leak in search_child_chunks tool

- **Severity**: Blocker
- **Layer**: Retrieval
- **Discovered**: 2026-04-28 13:27 UTC via Exploratory probe (T008 pre-block warmup); escalated to Blocker 2026-04-28 14:38 UTC (Charter 1 blast-radius confirmation)
- **F/D/P decision**: P→F (fix in-session; commits 97bbe98 + 7c4203e; tests in tests/unit/test_research_tools.py — TestSearchChildChunksScope class + amendment tests test_scoped_fanout_calls_search_per_authorized_collection + test_unscoped_falls_through_to_search_all)

## Steps to Reproduce

1. Stack up: `docker compose up -d` with 4 services healthy and ≥2 Qdrant collections in the system (this stack has 20+ from prior Wave 1 e2e fixtures).
2. Create a target collection: `POST /api/collections {"name": "nag-corpus-spec28", ...}` → id `22923ab5-ea0d-4bea-8ef2-15bf0262674f`.
3. Ingest content into it (NAG corpus — 18 PDFs, 2633 chunks).
4. Issue a chat request scoped to ONLY that collection:
   ```
   POST /api/chat
   {"message": "diámetro mínimo NAG-200", "session_id": "p-only", "collection_ids": ["22923ab5-ea0d-4bea-8ef2-15bf0262674f"]}
   ```
5. Tail backend logs: `docker compose logs backend --tail=80 | grep retrieval_`.

## Expected

Backend searches ONLY the user-specified Qdrant collection `emb-22923ab5-ea0d-4bea-8ef2-15bf0262674f`. Single `retrieval_hybrid_search_complete` log line for that collection. `retrieval_search_all_complete` does NOT fire.

## Actual

Backend logs show 20 separate `retrieval_hybrid_search_complete` lines — one per Qdrant collection in the system — followed by `retrieval_search_all_complete` with `collections_searched: 20, total_results: 30`. The final `agent_fallback_triggered` log records 3 collections that produced chunks: the user-requested `emb-22923ab5-...` PLUS two leaked collections (`emb-0ea45e41-...`, `emb-9d465858-...`) that the user never authorized. User-facing answer echoes "I searched 3 collection(s) and found 9 passage(s)".

## Artifacts

- Trace_id: `f8a65272-a0f0-406e-94d3-e69ad6f3f9f5` (probe timestamp 2026-04-28 13:27:39 UTC)
- Log excerpt:
  ```
  retrieval_search_all_complete  collections_searched=20 total_results=30 trace_id=f8a65272-a0f0-406e-94d3-e69ad6f3f9f5
  agent_fallback_triggered       chunk_count=9 collections_searched=["emb-22923ab5-ea0d-4bea-8ef2-15bf0262674f","emb-0ea45e41-795b-409c-b987-dac21de28dbe","emb-9d465858-672a-435b-bcfd-6b4bc6a5dc67"] iterations=3 tool_calls=2 trace_id=f8a65272-a0f0-406e-94d3-e69ad6f3f9f5
  ```
- File refs:
  - `backend/agent/tools.py:64-70` — `search_child_chunks` tool with the `else: search_all_collections(...)` fallback when collection arg doesn't start with `emb-`
  - `backend/agent/research_nodes.py:728-732` — user-visible "I searched N collection(s)" message derived from `set(c.collection for c in retrieved_chunks)`
  - `backend/api/chat.py:150` — `selected_collections` set in state but never enforced as a hard boundary
  - `backend/retrieval/searcher.py:179-238` — `search_all_collections` fans out to ALL collections from `client.get_collections()` (no allowlist filter)

## Root-cause hypothesis

The `search_child_chunks` tool was designed to give the LLM flexibility — accept a friendly collection name and gracefully fall back to global search if the name doesn't match the `emb-{uuid}` form. But this fallback silently turns a SCOPED query into a GLOBAL query, the OPPOSITE of what the API caller requested. The user's `collection_ids` filter from `/api/chat` is set in `state["selected_collections"]` (chat.py:150) but the tool's invocation context never reads from it — the LLM has to remember to pass the correct `emb-{uuid}` form, and our LLM doesn't reliably do that. Constitution V (Secure by Design) concern: an authorization boundary set at the API edge is silently broken inside the agent's tool plumbing.

**A3/A5 correction (2026-04-28 14:50 UTC) — SCOPE LEAK IS UNCONDITIONAL**: A5 log analysis confirms `collections_searched=20` on EVERY query across ALL 9 traced sessions, regardless of `collection_ids` parameter and regardless of whether OutputParserException fires. The scope leak is NOT triggered by the OPE fallback path — it operates unconditionally at the base layer (`search_child_chunks` / `HybridSearcher`). BUG-003/BUG-005's causal link to BUG-002 is being revised: OPE and scope leak are concurrent issues, not causally chained. Root cause of BUG-002 is unconditional fan-out in the searcher layer.

OOS trace `f85602ba` A5-confirmed collection breakdown (10 of 20 returned non-zero hits): `emb-22923ab5` (NAG corpus, expected) 5 results; `emb-0ea45e41`, `emb-67f187b8`, `emb-9d465858` (contain `manual_wslpg_1.24.pdf`) 5 results each; `emb-0bbcfc45`, `emb-7706c19e`, `emb-cc844008` (contain `README.MD`) 1 result each; `emb-9286c892`, `emb-c5e9cce6`, `emb-719237f6` additional leaked collections.

**Charter 1 update — A3 blast-radius confirmation (2026-04-28 14:44 UTC)**: A3 confirmed that leaked chunks ARE presented to users as citations in the UI. Out-of-scope query "¿Cuál es la capital de Francia?" to nag-corpus-spec28 (trace `f85602ba`) returned citations including:
- `manual_wslpg_1.24.pdf` ×2 — NOT in nag-corpus-spec28 (leaked from another Qdrant collection)
- `README.MD` ×1 — NOT in nag-corpus-spec28 (leaked from another Qdrant collection)
- `NAG-200.pdf` ×2 — in corpus, but irrelevant to the query

This is a data-access boundary breach visible in the UI. A concurrent Blocker, BUG-007, has been filed for the OOS-not-deflected + citation hallucination combination.

**Charter 1 update — mechanism (2026-04-28 14:38 UTC; REVISED 14:50 UTC)**: Initial hypothesis linked scope leak to BUG-003→BUG-005 causal chain. A3/A5 correction: scope leak is UNCONDITIONAL — trace `ab12fe4b` shows 20-collection fan-out with NO OutputParserException. Root cause is base-layer: `search_child_chunks` tool falls back to `search_all_collections` when the LLM-passed `collection` arg doesn't start with `emb-`. LLM is given raw UUIDs in prompt (`nodes.py:267`) and never instructed to add the `emb-` prefix. BUG-003 and BUG-002 are concurrent but independent. BUG-005 causal hypothesis under review.

## Investigation notes (P-investigation, 14:43–14:51 UTC, 8-min duration)

- True proximate cause: `backend/agent/tools.py:64-70` `search_child_chunks` tool falls back to `search_all_collections` when LLM-passed `collection` arg doesn't start with `emb-`.
- LLM is given raw UUIDs in prompt (`nodes.py:267`); never instructed to add `emb-` prefix; tool fans out to all collections.
- GitNexus impact analysis on `search_child_chunks`: LOW risk, 0 statically-visible upstream callers (LangGraph hidden binding).
- A3+A5 confirmed BUG-002 is INDEPENDENT of BUG-003 (parser failure). Trace `ab12fe4b`: no parser failure, but still searched 20 collections.
- F-path: ~15 LOC across `backend/agent/tools.py` + `backend/api/chat.py` + 1 regression test. Closes BUG-002 100%, closes BUG-007 (OOS hallucination) ~100% as downstream symptom.
- BUG-003 (parser root) stays Major, deferred to v1.1.
- BUG-006 (rerank-dedup) independent, separate F/D/P gate to follow.

## A5 final queue addenda (2026-04-28 ~17:55 UTC)

**ANALYTICAL query scope leak confirmed (trace d073a61b)**:
`agent_fallback_triggered` for charter1-step3-analytical shows `collections_searched: ["emb-22923ab5-ea0d-4bea-8ef2-15bf0262674f", "emb-0ea45e41-795b-409c-b987-dac21de28dbe"]` — NAG corpus PLUS `emb-0ea45e41` (non-NAG collection, 5 hits). Scope leak affects ANALYTICAL queries as well as FACTOID; `emb-0ea45e41` contaminated analytical answer with non-regulatory citations. Consistent with the OOS trace `f85602ba` breakdown already documented above.

**Clean-path root cause confirmed (trace 3ba79d7f)**:
Post-`97bbe98` verify trace `3ba79d7f` took the CLEAN PATH (intent=rag_query, no OutputParserException, no fallback) and still showed `retrieval_search_all_complete collections_searched=20`. This definitively confirms BUG-002 is NOT solely caused by the OPE fallback path dropping scope (BUG-005). Even on the normal execution path, `collection_id` from the API request never reaches `HybridSearcher`. BUG-003/BUG-005 are contributing factors (forcing the fallback path) but BUG-002 exists independently on all execution paths. Initial fix `97bbe98` was insufficient — only patched `search_child_chunks`; amendment `7c4203e` completed the fix by also patching `semantic_search_all_collections`.
