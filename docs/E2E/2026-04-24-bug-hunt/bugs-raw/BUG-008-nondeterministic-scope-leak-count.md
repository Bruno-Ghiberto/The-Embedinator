# BUG-008: Scope leak count non-deterministic across identical queries

- **Severity**: Major
- **Layer**: Retrieval
- **Discovered**: 2026-04-28 14:44 UTC via Exploratory (Charter 1 blast-radius probe — A3 Finding 2)

## Steps to Reproduce

1. Stack up: 4 services healthy. Corpus seeded with NAG corpus (nag-corpus-spec28).
2. Issue the same factoid query 4× with distinct session_ids, same collection_ids:
   ```
   POST /api/chat
   {"message": "diámetro mínimo NAG-200", "session_id": "blast-N",
    "collection_ids": ["22923ab5-ea0d-4bea-8ef2-15bf0262674f"]}
   ```
3. Observe the "I searched N collection(s)" string in each response and the collections_searched value in `retrieval_search_all_complete` log events.

## Expected

Each run of the same scoped query returns a consistent collection count: 1 (the authorized collection only). The scope should be deterministic given identical inputs.

## Actual

The number of collections reported in the user-facing response varies across 4 identical runs (A3 Charter 1 blast-radius probe, same query "diámetro mínimo NAG-200"):

| Run | Trace | Response | collections_searched | confidence | num_citations |
|-----|-------|----------|---------------------|------------|---------------|
| BLAST-1 | d01799b7 | "1 collection(s)" | 20 (log) | 48 | 1 |
| BLAST-2 | 2cb0daa4 | "3 collection(s)" | 20 (log) | 0 | 0 |
| BLAST-3 | dbc3da00 | "1 collection(s)" | 20 (log) | 0 | 0 |
| BLAST-4 | 4cdd47d6 | "1 collection(s)" | 1 (log) | 48 | 4 |

The logs show `collections_searched: 20` on most runs, but the user-facing message says "1" or "3" depending on how many collections returned non-zero chunks. The user-visible count is computed from `set(c.collection for c in retrieved_chunks)` — which is the number of unique collections that contributed chunks to the answer, not the number searched. The search is deterministically broken (20 collections searched every time), but the symptoms vary non-deterministically based on which cross-collection chunks happen to be relevant on each run.

## Artifacts

- A3 Charter 1 blast-phase blast-matrix (see session-log Charter 1 scorecard)
- Trace IDs: `d01799b7`, `2cb0daa4`, `dbc3da00`, `4cdd47d6`
- File ref: `backend/agent/research_nodes.py:728-732` — "I searched N collection(s)" message derived from `set(c.collection for c in retrieved_chunks)`

## A3/A5 Correction (2026-04-28 14:50 UTC) — MERGE INTO BUG-002

A5 log analysis confirms: `collections_searched=20` on EVERY query across ALL traced sessions — the underlying search count is always 20. The variation in the user-facing "N collection(s)" message reflects how many of the 20 searched collections returned non-zero chunk hits (varies by query content), NOT variation in how many collections were searched. This makes the "non-determinism" an artifact of hit-distribution, not scope-variation. BUG-008 is a manifestation of BUG-002, not an independent bug. Treat as merged into BUG-002. The correction to report the REQUESTED `collection_ids` count (not the hit-contributing count) remains a valid improvement item, to be addressed when BUG-002 is fixed.

## Root-cause hypothesis

This is a symptom of BUG-002 (scope leak) rather than an independent root cause, but it surfaces a distinct problem: the user-facing collection count is computed post-retrieval from returned chunks, not from the requested scope. If BUG-002 causes 20 collections to be searched, the user-visible count reflects how many happened to return relevant chunks — making the experience non-deterministic and misleading. Even after BUG-002 is fixed, the metric should be verified to report the REQUESTED collection count (from `collection_ids`), not the retrieved-chunk source count. The two should agree when scope is correct, but the semantic should be "scope you requested" not "collections that happened to contribute."
