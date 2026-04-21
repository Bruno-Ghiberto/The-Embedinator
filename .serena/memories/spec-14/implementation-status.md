# Spec-14 Implementation Status

**Status**: COMPLETE (2026-03-18)
**Branch**: `014-performance-budgets`
**Tests**: 1361 passing, 39 pre-existing failures (unchanged)

## Key Changes
- `ConversationState`: 14 fields (added `stage_timings: dict`)
- `create_query_trace()`: 16 params (added `stage_timings_json: str | None = None`)
- `query_traces` table: `stage_timings_json TEXT` column via idempotent ALTER TABLE
- 5 production modules instrumented with `time.perf_counter()`
- SC-006 + SC-007 automated gate tests: both PASS (no skip)

## timed_app Fixture Pattern (CRITICAL GOTCHA)
```python
import backend.main as main_module
tmp_db = str(tmp_path / "test_embedinator.db")
main_module.settings.sqlite_path = tmp_db  # must use tmp_path, not real data/embedinator.db
try:
    with patch("backend.main.QdrantClientWrapper", return_value=mock_qdrant), \
         patch("backend.main.ProviderRegistry", return_value=mock_registry), \
         patch("langgraph.checkpoint.sqlite.aio.AsyncSqliteSaver") as mock_saver_cls, \
         patch("backend.storage.qdrant_client.QdrantStorage", return_value=mock_qdrant_storage), \
         patch("backend.retrieval.reranker.Reranker", return_value=mock_reranker), \
         patch("backend.retrieval.searcher.HybridSearcher", return_value=mock_hybrid_searcher):
        ...
        with TestClient(app) as client:
            yield client
finally:
    main_module.settings.sqlite_path = original_sqlite_path
```

## Why tmp_path is Required
`data/embedinator.db` has Phase 1 collections schema (only `id, name, created_at, updated_at`).
Code SELECTs `description, embedding_model, chunk_profile, qdrant_collection_name` → OperationalError.
Fresh DB in tmp_path uses full current schema via `CREATE TABLE IF NOT EXISTS`.
