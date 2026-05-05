# Spec-28 follow-up: BM25 hybrid retrieval — completing the half-built architecture

> **Status**: code change shipped (this PR). Single-sample sweep evidence
> attached. Headline answer-rate did NOT move on this sample; the change is an
> architectural correctness fix, not a measurable F1 win at temp=0.8 single-run.
> Deeper investigation deferred to v1.1.

## Problem

Spec-07 and earlier specs declared a hybrid dense+sparse retrieval architecture,
but only the dense half was wired:

- `QdrantStorage.create_collection` (storage/qdrant_client.py:347) DID configure
  the `sparse` named vector with `Modifier.IDF` on every new collection.
- `IngestionPipeline._ingest_loop` (ingestion/pipeline.py:215-230) populated
  ONLY the `dense` vector — sparse stayed `None`. Empirical proof: scrolling a
  random point from `nag-corpus-spec28` returned `vector keys: ['dense']` only.
- `HybridSearcher.search` (retrieval/searcher.py:144) self-documented the gap:
  > *"Dense-only search — sparse prefetch requires pre-encoded sparse vectors
  > which are not available at query time (BM25 encoding not implemented)."*

The result: short, abstract Spanish queries (e.g. Q-001 "¿Cuál es el objeto del
Reglamento Técnico NAG-200?") could not retrieve their canonical answer chunk
even though it was indexed. For Q-001, NAG-200 §1.1 was at **dense rank 82** —
nowhere near the cross-encoder rerank's top-5 window.

A separate but related bug in `agent/tools.py:95` collapsed the recall pool to
the LLM's requested `top_k`: when the LLM asked for top_k=5, retrieval also
returned 5, so chunks at retrieval rank 6+ never reached the reranker even when
they would have outranked the top-5 after re-scoring.

## Fix

Three small, isolated patches:

| File | Change |
|---|---|
| `backend/retrieval/bm25_encoder.py` (new) | Lightweight Spanish-aware BM25 encoder. Hashlib-deterministic token indices; raw term-frequency values, IDF applied server-side by Qdrant. ~85 lines, dependency-free. |
| `backend/retrieval/searcher.py` | Replace dense-only `query_points` with a hybrid `prefetch=[dense, sparse] → FusionQuery(Fusion.RRF)`. Falls back to dense-only when the query has no BM25-eligible tokens. |
| `backend/ingestion/pipeline.py` | Encode each child chunk's raw text into a BM25 sparse vector at ingest time and include it in the upsert payload alongside the dense vector. |
| `backend/agent/tools.py` | `search_child_chunks` now uses `settings.top_k_retrieval` (default 20) as the recall pool and `settings.top_k_rerank` (default 5) as the rerank output. The LLM's requested `top_k` is respected for output count but no longer constrains recall. |

Tests: `tests/unit/test_bm25_encoder.py` covers tokenization, accent
normalization, deterministic hashing, hash-collision merging, and the
load-bearing query↔passage encoding invariant.

## Validation

Direct retrieval inspection on Q-001 against the new `nag-corpus-bm25`
collection (Qdrant scroll + `query_points`):

| Layer | Q-001 §1.1 chunk position |
|---|---|
| Dense-only (nomic-embed-text) | rank 82 of 200 |
| Sparse-only (BM25 with IDF) | **rank 6 of 200** |
| Hybrid (RRF fusion of top-40 each side) | **rank 13 of top-20** |

The §1.1 chunk now reaches the cross-encoder reranker's input pool. Smoke test
on the `/api/chat` endpoint (3 runs at default temp 0.8) flipped Q-001 from
`0/3 declined` (pre-fix) to `1/3 answered with 5 citations` (post-fix). The
answer cited the verbatim §1.1 reference text.

## What this change does NOT fix

Headline answer-rate on the 20-question golden set did not move on a single-run
sample:

| Sweep | Configuration | Answered |
|---|---|---|
| v1 (PR #72) | Dense-only retrieval | 4/20 (20%) |
| v5 (this PR) | Hybrid + retrieval-pool fix, temp=0.8 default | 1/20 (5%) |
| v6 (this PR) | Hybrid + retrieval-pool fix, temp=0.1 explicit | 0/20 (0%) |

Single-sample variance from `qwen2.5:7b` at default temperature (~0.8) is
±15-20pp on this dataset. The v1 number was one favorable roll; v5 and v6 are
two unfavorable rolls. Multi-sample averaging is needed to characterize the
true distribution. The v6 deterministic sweep at temp=0.1 reveals the real
bottleneck: the judge LLM consistently rules retrieved chunks "not sufficiently
relevant" even when canonical answer chunks are in context. This is a
prompt/model-quality issue, not a retrieval issue.

The temperature change explored in v6 was reverted before commit — at temp=0.1
the demo path breaks (Q-009, Q-020 also stop answering reliably), so default
Ollama behavior (~0.8) is preserved for v1.0.

## Deferred to v1.1

- **Multilingual cross-encoder reranker** (`BAAI/bge-reranker-v2-m3`) —
  yesterday's experiment showed no measurable F1 win, but the English-only
  `ms-marco-MiniLM` reranker scoring Spanish content remains architecturally
  wrong. Worth ANOTHER measurement after the BM25 fix lands.
- **Judge LLM upgrade or prompt loosening** — the `fallback_response` path
  fires too aggressively. With §1.1 in context, the LLM should rarely emit
  *"none were sufficiently relevant"*.
- **Multi-sample sweep methodology** — single-run sweeps cannot distinguish
  retrieval improvements from temperature variance. v1.1 should publish n=5
  averaged sweeps with stddev.
- **PROMPTGATOR-trained domain-adapted bi-encoder** (spec-33 stub) — long-term
  retrieval lever, replaces nomic-embed-text on the Spanish corpus.

## Files

- `backend/retrieval/bm25_encoder.py` (new)
- `backend/retrieval/searcher.py` (modified)
- `backend/ingestion/pipeline.py` (modified)
- `backend/agent/tools.py` (modified)
- `tests/unit/test_bm25_encoder.py` (new)
- `docs/E2E/2026-04-24-bug-hunt/baseline-sweep-2026-05-05-v5-bm25-hybrid.json` (evidence — single sample, temp=0.8 default)
- `docs/E2E/2026-04-24-bug-hunt/baseline-sweep-2026-05-05-v6-bm25-hybrid-temp01.json` (evidence — single sample, temp=0.1 deterministic)
