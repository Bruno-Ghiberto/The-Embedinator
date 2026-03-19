# Agent A3: Storage and Retrieval Contract Tests

## Agent: python-expert | Model: sonnet | Wave: 2

## Role

You are a Wave 2 agent for spec-11. You write two test files:
`tests/unit/test_contracts_storage.py` and `tests/unit/test_contracts_retrieval.py`.
You run in PARALLEL with A2 (who writes agent contract tests). You have no file
conflicts with A2.

---

## Assigned Tasks

### Storage Contracts (test_contracts_storage.py)

**T023** -- Create `tests/unit/test_contracts_storage.py` with imports. Import `inspect`,
`SQLiteDB` from `backend.storage.sqlite_db`, `QdrantStorage` from
`backend.storage.qdrant_client`, `ParentStore` from `backend.storage.parent_store`.

**T024** -- Write SQLiteDB method existence tests (FR-008): verify all 35+ methods exist
on `SQLiteDB` class. Organize by category:
- Collections: `create_collection`, `get_collection`, `list_collections`,
  `update_collection`, `delete_collection`, `get_collection_stats`
- Documents: `create_document`, `get_document`, `get_document_by_hash`,
  `list_documents`, `update_document_status`, `delete_document`
- Ingestion jobs: `create_ingestion_job`, `get_ingestion_job`, `update_ingestion_job`,
  `list_ingestion_jobs`
- Parent chunks: `create_parent_chunk`, `get_parent_chunk`, `list_parent_chunks`,
  `delete_parent_chunks_by_document`, `count_parent_chunks`
- Query traces: `create_query_trace`, `get_trace`, `list_traces`,
  `get_trace_detail`, `get_trace_stats`
- Settings: `get_setting`, `set_setting`, `get_all_settings`, `delete_setting`
- Providers: `upsert_provider`, `get_provider`, `list_providers`,
  `get_active_provider`, `set_active_provider`, `delete_provider_key`,
  `get_provider_key`
- Health: `health_check`
- Context manager: `connect`, `close`

**IMPORTANT**: The above method list is a starting point. Verify the actual method names
on the class using `inspect` or `dir()`. Some may differ -- the test must match reality.

**T025** -- Write SQLiteDB key method signature tests (FR-008): verify parameter names
and counts for critical methods:
- `create_query_trace` has 16 params including `provider_name`
- `create_document` uses individual params (not a Pydantic model)
- `list_traces` has `session_id`/`collection_id`/`min_confidence`/`max_confidence`/
  `limit`/`offset` params

**T026** -- Write QdrantStorage tests (FR-009): verify:
- Method names: `batch_upsert` (NOT `upsert_batch`), `search_hybrid` (NOT
  `hybrid_search`), `delete_points_by_filter` (NOT `delete_by_filter`)
- Data classes: `SparseVector`, `QdrantPoint`, `SearchResult` exist in the module
- `QdrantClientWrapper` coexists in the same file as `QdrantStorage`

**T027** -- Write ParentStore tests: verify constructor takes `db` param, and methods
`get_by_ids` and `get_all_by_collection` exist.

**T028** -- Write negative assertion tests (SC-006, Pattern 7): verify phantom methods
do NOT exist:
- `SQLiteDB.find_by_hash` -- correct name is `get_document_by_hash`
- `SQLiteDB.store_parent_chunks` -- correct name is `create_parent_chunk`
- `SQLiteDB.store_trace` -- correct name is `create_query_trace`
- `SQLiteDB.set_provider_key` -- does not exist as a direct method
- `SQLiteDB.delete_provider_key` -- verify actual name (may exist or not)
- `SQLiteDB.update_document_status` -- verify actual name

**IMPORTANT on negative assertions**: Before asserting a method does NOT exist, verify
against the live code first. The phantom list above comes from common confusion in earlier
specs. If a method actually does exist, do NOT assert it is absent.

**T029** -- Run storage contract tests and fix any failures.

### Retrieval Contracts (test_contracts_retrieval.py)

**T035** -- Create `tests/unit/test_contracts_retrieval.py` with imports. Import `inspect`,
`HybridSearcher` from `backend.retrieval.searcher`, `Reranker` from
`backend.retrieval.reranker`.

**T036** -- Write HybridSearcher tests (FR-010): verify:
- Constructor params are `["self", "client", "settings"]` (NOT storage/embedder/reranker)
- `search` method has an `embed_fn` param
- Method is `search_all_collections` (NOT `search_multi_collection`)
- Circuit breaker methods exist: `_check_circuit`, `_record_success`, `_record_failure`

**T037** -- Write Reranker tests (FR-011): verify:
- Constructor params are `["self", "settings"]` (NOT `model_name: str`)
- `rerank` method has params `["self", "query", "chunks", "top_k"]`
- `score_pair` does NOT exist (`assert not hasattr`)

**T038** -- Write ScoreNormalizer test: verify `normalize_scores` is a module-level
function in `backend/retrieval/score_normalizer.py` (not a class method). Import it
directly and check it is callable.

---

## Output Files

- `tests/unit/test_contracts_storage.py`
- `tests/unit/test_contracts_retrieval.py`

---

## Key Technical Facts

1. **No ORM types**: `SQLiteDB` methods return raw `dict` values, not typed row models.
   There are no `CollectionRow`, `DocumentRow`, `JobRow`, etc.

2. **Method names matter**: The following are commonly confused:
   - `batch_upsert` (correct) vs `upsert_batch` (wrong)
   - `search_hybrid` (correct) vs `hybrid_search` (wrong)
   - `get_document_by_hash` (correct) vs `find_by_hash` (wrong)
   - `search_all_collections` (correct) vs `search_multi_collection` (wrong)

3. **QdrantClientWrapper vs QdrantStorage**: Both classes exist in `qdrant_client.py`.
   `QdrantClientWrapper` is the legacy Phase 1 class. `QdrantStorage` is the spec-07
   class with full CRUD. Both coexist.

4. **ParentStore** is in `backend/storage/parent_store.py` with a `db` constructor param.

5. **Reranker** constructor takes `settings: Settings`, not `model_name: str`.

---

## Test Patterns to Use

- **Pattern 1** (Function Signature): For key method signatures
- **Pattern 2** (Method Existence): For all 35+ SQLiteDB methods and QdrantStorage methods
- **Pattern 7** (Negative Assertions): For phantom method verification

---

## Testing Rule (MANDATORY)

```
NEVER run pytest directly inside Claude Code. Use ONLY:
  zsh scripts/run-tests-external.sh -n contracts-storage tests/unit/test_contracts_storage.py
  zsh scripts/run-tests-external.sh -n contracts-retrieval tests/unit/test_contracts_retrieval.py

Poll: cat Docs/Tests/<name>.status     (RUNNING | PASSED | FAILED | ERROR)
Read: cat Docs/Tests/<name>.summary    (~20 lines, token-efficient)
Full: cat Docs/Tests/<name>.log
```

Run the two test files separately -- each gets its own test runner invocation.

---

## Gate Check

After completing all tasks:

1. Run both test files via external runner
2. Poll both status files until PASSED or FAILED
3. If FAILED, read the summary, fix the test, and re-run
4. When BOTH pass, notify the Orchestrator that A3 is complete
