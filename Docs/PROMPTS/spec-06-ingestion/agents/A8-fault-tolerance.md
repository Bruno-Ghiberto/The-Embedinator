# Agent: A8-fault-tolerance

**subagent_type**: quality-engineer | **Model**: Sonnet 4.6 | **Wave**: 4

## Mission

Add fault tolerance to the ingestion pipeline: skip-and-continue for embedding validation failures, UpsertBuffer for Qdrant outages with pause/resume, Ollama outage handling with pause/retry, and Rust worker crash handling that processes all received chunks before marking failure. Write comprehensive unit and integration tests for all fault tolerance scenarios.

## Context Files (Read FIRST)

1. `Docs/PROMPTS/spec-06-ingestion/06-implement.md` -- full code specifications (the authoritative reference)
2. `specs/006-ingestion-pipeline/spec.md` -- FR-010 (validate + skip), FR-012 (upsert buffer), FR-013 (Ollama outage), FR-016 (worker crash), US3 acceptance scenarios
3. `specs/006-ingestion-pipeline/data-model.md` -- IngestionJob state machine (paused state, pause triggers, resume behavior)
4. `specs/006-ingestion-pipeline/research.md` -- R4: partial output handling
5. `specs/006-ingestion-pipeline/tasks.md` -- T037-T043
6. `backend/ingestion/pipeline.py` -- IngestionPipeline (created by A2, modified by A6)
7. `backend/ingestion/embedder.py` -- BatchEmbedder, validate_embedding (created by A4)
8. `backend/errors.py` -- CircuitOpenError (line 43-44), IngestionError (line 27-28)
9. `backend/storage/qdrant_client.py` -- QdrantClientWrapper with circuit breaker

## Assigned Tasks

- T037: [US3] Add skip-and-continue behavior to `BatchEmbedder.embed_chunks()` in `backend/ingestion/embedder.py`: when `validate_embedding()` fails for a chunk, log the reason via structlog, increment a skipped counter, continue with remaining chunks. Return both valid embeddings and skip count. The method signature should change to return `tuple[list[list[float]], int]` where the int is `chunks_skipped`.
- T038: [US3] Implement `UpsertBuffer` class in `backend/ingestion/pipeline.py`:
  - `_buffer: list` with `MAX_CAPACITY = 1000`
  - `add(points: list[dict]) -> bool`: add points to buffer, return `False` if buffer is at capacity
  - `flush(qdrant: QdrantClientWrapper, collection_id: str) -> int`: batch upsert all buffered points and clear buffer, return count flushed
  - `pending_count` property: return current buffer size
- T039: [US3] Wire upsert buffering into `IngestionPipeline`: on Qdrant upsert failure, add to UpsertBuffer. If buffer is full (`add()` returns False), set job status=`paused`. Poll for Qdrant recovery (simple retry loop with backoff). On recovery, flush buffer and resume embedding. Update job status back to `embedding`.
- T040: [US3] Implement Ollama outage handling in `backend/ingestion/pipeline.py`: detect embedding failures (CircuitOpenError or connection errors from httpx), set job status=`paused`, retry with exponential backoff (using tenacity or manual loop), resume when embedding succeeds.
- T041: [US3] Implement worker crash handling in `backend/ingestion/pipeline.py`: if Rust worker exits non-zero, process all successfully streamed chunks (per R4), log stderr output, set job status=`failed`, set document status=`failed`, record `chunks_processed` count for successfully processed chunks.
- T042: [US3] Write unit tests for fault tolerance in `tests/unit/test_ingestion_pipeline.py`:
  - Validation failure skips chunk, rest of batch succeeds, `chunks_skipped` incremented
  - UpsertBuffer `add()` and `flush()` mechanics
  - Buffer full triggers job pause
  - Ollama outage triggers job pause
  - Worker crash (non-zero exit) processes received chunks and sets status=`failed`
- T043: [US3] Write integration test in `tests/integration/test_ingestion_pipeline.py`: mock Qdrant to be temporarily unreachable, verify job pauses, restore connectivity, verify job completes with all points flushed.

## Files to Create/Modify

### Modify
- `backend/ingestion/embedder.py` (add skip-and-continue to embed_chunks)
- `backend/ingestion/pipeline.py` (add UpsertBuffer class, wire pause/resume, worker crash handling)
- `tests/unit/test_ingestion_pipeline.py` (add fault tolerance tests)
- `tests/unit/test_embedder.py` (add skip-and-continue test if needed)
- `tests/integration/test_ingestion_pipeline.py` (add Qdrant outage integration test)

## Key Patterns

- **Skip-and-continue**: After calling `validate_embedding(vector, dim)`, if it returns `(False, reason)`, log a warning with the reason and chunk index, increment `skipped` counter, and continue to the next chunk. Do NOT raise an exception. The pipeline counts skipped chunks in `ingestion_jobs.chunks_skipped`.
- **UpsertBuffer**: Simple list-based buffer with capacity check. `add()` appends and returns True normally, returns False when len >= MAX_CAPACITY. `flush()` calls `qdrant.upsert()` in batches (reusing `settings.qdrant_upsert_batch_size`).
- **Pause/resume flow**:
  1. Qdrant upsert fails (exception from QdrantClientWrapper)
  2. Add failed points to UpsertBuffer
  3. If buffer full: set job status=`paused`
  4. Enter retry loop: sleep with backoff (e.g., 5s, 10s, 20s), try flush
  5. On successful flush: set job status=`embedding`, continue pipeline
- **Ollama outage**: Similar pattern -- catch `CircuitOpenError` or `httpx.ConnectError` from BatchEmbedder, set status=`paused`, retry with backoff, resume on success.
- **Worker crash (R4)**: The pipeline reads NDJSON lines from stdout as they arrive. If `proc.wait()` returns non-zero, `_read_worker_output()` has already collected all successfully streamed chunks. Process them normally (chunk, embed, upsert), then set job/document status=`failed` and store stderr in `error_msg`.
- **structlog**: `logger = structlog.get_logger(__name__)` -- log all fault tolerance events (pause, resume, skip, crash).
- **CircuitOpenError**: Import from `backend.errors`. Already exists -- do not define a new one.
- **Test mocking**: For UpsertBuffer tests, mock QdrantClientWrapper. For Ollama outage, mock BatchEmbedder._embed_batch to raise. For worker crash, mock subprocess.Popen with a non-zero returncode.
- **Integration test**: Use `MemorySaver()` for LangGraph checkpointer if needed. Mock Qdrant to raise on first N calls, then succeed.

## Constraints

- NEVER run pytest inside Claude Code. Use: `zsh scripts/run-tests-external.sh -n spec06-fault tests/unit/test_ingestion_pipeline.py tests/unit/test_embedder.py`
- NEVER modify `backend/config.py`, `backend/storage/sqlite_db.py`, `backend/storage/parent_store.py`
- NEVER modify Rust files
- When modifying `embedder.py`, only change `embed_chunks()` to add skip-and-continue behavior and update the return type. Do NOT change `validate_embedding` or `_embed_batch`.
- When modifying `pipeline.py`, add the UpsertBuffer class and modify `ingest_file()` to use it. Do not change the core flow (subprocess spawn, chunking, status updates) -- only add fault tolerance wrappers around existing operations.
- Buffer overflow triggers **pause** (not fail/abort). This is a critical spec requirement. The job resumes automatically.
- Tenacity retry wraps the inner retry logic. Circuit breaker recording happens in the outer public method (after all retries exhausted). Follow the same pattern as `QdrantClientWrapper`.
- Existing tests from A2 in `test_ingestion_pipeline.py` must not be broken. Add fault tolerance tests in a new test class (e.g., `TestFaultTolerance`).

## Checkpoint

Fault tolerance implemented, all tests pass:

```bash
ruff check backend/ingestion/pipeline.py backend/ingestion/embedder.py
zsh scripts/run-tests-external.sh -n spec06-fault tests/unit/test_ingestion_pipeline.py tests/unit/test_embedder.py
cat Docs/Tests/spec06-fault.status
cat Docs/Tests/spec06-fault.summary

# Integration test:
zsh scripts/run-tests-external.sh -n spec06-fault-integ tests/integration/test_ingestion_pipeline.py
cat Docs/Tests/spec06-fault-integ.status
cat Docs/Tests/spec06-fault-integ.summary
```
