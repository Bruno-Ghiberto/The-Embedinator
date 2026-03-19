# Spec 06: Ingestion Pipeline — Implementation Complete

## Status
- 52/52 tasks complete
- 468 Python tests passing (5 pre-existing failures unchanged)
- 40 Rust tests passing, clippy clean
- 0 regressions from spec-05 baseline

## Implementation Summary
- 5-wave Agent Teams: A1 (foundation) → A2+A3+A4+A5 (parallel core) → A6+A7 (parallel dedup+validation) → A8 (fault tolerance) → Lead (polish)
- A2 used Opus 4.6 (pipeline orchestrator complexity); all others Sonnet 4.6

## Files Created
- `backend/ingestion/__init__.py`, `pipeline.py`, `chunker.py`, `embedder.py`, `incremental.py`
- `ingestion-worker/` — full Rust Cargo workspace (7 source files)
- 6 unit test files + 1 integration test file (spec-06 specific)

## Files Modified
- `backend/config.py` — 3 new fields (rust_worker_path, embed_max_workers, qdrant_upsert_batch_size)
- `backend/storage/sqlite_db.py` — schema migration + new CRUD methods
- `backend/storage/parent_store.py` — SQL column aliases
- `backend/api/documents.py` — new ingest endpoint, SUPPORTED_FORMATS extended to 12
- `tests/unit/test_sqlite_db.py` — updated old Phase 1 tests for new create_document signature

## Post-Implementation Fixes (Lead Wave 5)
- test_sqlite_db.py: 3 Phase 1 tests used old `create_document(name=, collection_ids=[])` — updated to `create_document(filename=, collection_id=)`
- test_ingestion_api.py: 2 zero-content PDF tests failed because IncrementalChecker.compute_file_hash() tried to read non-existent `/tmp/empty.pdf` — fixed by passing `file_hash="abc123"` to skip hash computation
- .gitignore: added `target/` and `*.rs.bk` for Rust artifacts
