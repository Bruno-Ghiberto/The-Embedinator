# BUG-007: Out-of-scope query returns confident answer from leaked-collection citations

- **Severity**: Blocker
- **Layer**: Reasoning (intent classifier + answer aggregation); secondary: Retrieval (BUG-002 scope leak provides the polluted chunk source)
- **Discovered**: 2026-04-28 14:41 UTC via Live Block Charter 1 step 3 (A3 query, A5 log analysis)
- **F/D/P decision**: D (defer to v1.1; rationale: user-facing demo-blocking symptom auto-closed by BUG-002 fix commits 97bbe98 + 7c4203e — OOS query trace b95d971d returns 1 collection / 0 leaked citations; deeper architectural work — intent classifier OOS guard + citation validator — belongs in a v1.1 security-hardening micro-spec)

## Steps to Reproduce

1. Stack up. Corpus seeded with `nag-corpus-spec28` (id `22923ab5-...`).
2. Issue an OOS query scoped to that collection only:
   ```
   POST /api/chat
   {"message": "¿Cuál es la capital de Francia?", "session_id": "step3-oos", "collection_ids": ["22923ab5-ea0d-4bea-8ef2-15bf0262674f"]}
   ```
3. Observe NDJSON stream: `intent` event classifies as `rag_query` (NOT deflected); `citation` events fire with 20 entries; final `confidence` event reads ~34/100.

## Expected

OOS query is deflected by the intent classifier OR the agent reaches a graceful-decline answer per H4 hypothesis ("La información no está en los documentos cargados"). No citations should appear since no scoped-corpus chunks are relevant.

## Actual

Intent classifier routes as `rag_query` (no OOS guard). Backend then:
- `retrieval_search_all_complete`: collections_searched=20, total_results=30 (BUG-002 scope leak — A5 confirms scope leak is unconditional: 20 collections searched on every query regardless of collection_ids)
- agent exits via `agent_loop_exit_tool_exhaustion` (1-tool-call path, BUG-006 doesn't fire)
- `agent_aggregate_answers_merged`: confidence_score=34, num_citations=5
- `agent_format_response_formatted`: confidence_score=34, num_citations=20 (20 citations surfaced to user)

User sees a confident-sounding answer with 20 citations from collections like `manual_wslpg_1.24.pdf` and `README.MD` — none of which are in the user-authorized `nag-corpus-spec28`.

A5 OOS trace breakdown: 10 of 20 collections returned non-zero results — `emb-22923ab5` (NAG corpus, expected): 5 results; `emb-0ea45e41`, `emb-67f187b8`, `emb-9d465858` (likely contain `manual_wslpg_1.24.pdf`): 5 results each; `emb-0bbcfc45`, `emb-7706c19e`, `emb-cc844008` (likely contain `README.MD`): 1 result each; additional leaked collections: `emb-9286c892`, `emb-c5e9cce6`, `emb-719237f6`.

## Artifacts

- trace_id: `f85602ba-16b5-41ea-8313-7732e78c4fe0`
- Cited (leaked) sources (A3 verbatim): `manual_wslpg_1.24.pdf` (×2), `README.MD` (×1), unrelated collection chunks (rest of the 20)
- File refs (probable):
  - `backend/agent/nodes.py` — intent_classifier node (no OOS deflection logic)
  - `backend/agent/tools.py:66-70` — scope-leak source (BUG-002)
  - `backend/agent/research_nodes.py` — answer aggregation that doesn't validate citation sources against `state["selected_collections"]`

## Root-cause hypothesis

The intent classifier currently routes everything as `rag_query` regardless of corpus content. There's no OOS-detection step that checks "would the query be answerable from the user-authorized collections?" Combined with BUG-002 (scope leak provides cross-corpus chunks — A5 confirms this is unconditional, not OPE-triggered) and BUG-006 not firing on the 1-tool-call path, the agent confidently assembles an answer from polluted retrieval. The H4 hypothesis (out-of-scope graceful decline) is REFUTED — the system fails to decline.

## Fix leverage

Three layers of defense, any one would close the user-facing impact:
1. **BUG-002 fix** (highest leverage): with scope respected, retrieval returns 0 relevant chunks for OOS query → confidence floor logic kicks in → graceful decline. This is the recommended fix path.
2. **Intent classifier**: add OOS guard that runs after retrieval — if all scoped-corpus chunks score below threshold, return graceful-decline.
3. **Citation validator**: before format_response, validate every citation's source_doc is from `state["selected_collections"]`'s collection. Belt-and-suspenders.

## Causal context

BUG-007 = downstream symptom of BUG-002 (unconditional scope leak) + missing OOS guard. Fixing BUG-002 (collection_ids filter enforced at HybridSearcher level) likely resolves BUG-007's user-facing symptom even without a dedicated OOS guard — with correct scoping, the OOS query finds zero relevant chunks from the authorized corpus and the existing confidence-floor logic should decline gracefully.
