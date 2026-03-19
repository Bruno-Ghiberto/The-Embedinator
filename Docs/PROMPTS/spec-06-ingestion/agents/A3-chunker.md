# Agent: A3-chunker

**subagent_type**: python-expert | **Model**: Sonnet 4.6 | **Wave**: 2

## Mission

Implement the `ChunkSplitter` class that transforms raw Rust worker NDJSON output into parent chunks (2000-4000 chars) and child chunks (~500 chars) with structural breadcrumb prefixes and deterministic UUID5 point IDs. Write comprehensive unit tests.

## Context Files (Read FIRST)

1. `Docs/PROMPTS/spec-06-ingestion/06-implement.md` -- full code specifications (the authoritative reference)
2. `specs/006-ingestion-pipeline/spec.md` -- FR-007 (parent/child chunking), FR-008 (deterministic UUID5)
3. `specs/006-ingestion-pipeline/data-model.md` -- ParentChunk entity, ChildChunk entity, validation rules
4. `specs/006-ingestion-pipeline/contracts/worker-ndjson.md` -- NDJSON schema (raw chunk fields: text, page, section, heading_path, doc_type, chunk_index)
5. `specs/006-ingestion-pipeline/tasks.md` -- T021, T026
6. `backend/config.py` -- `settings.parent_chunk_size` (3000), `settings.child_chunk_size` (500)

## Assigned Tasks

- T021: [P] [US1] Implement `ChunkSplitter` class in `backend/ingestion/chunker.py`:
  - `split_into_parents(raw_chunks: list[dict], source_file: str) -> list[ParentChunkData]`: accumulate raw worker chunks into parent chunks (2000-4000 chars). Each raw_chunk has fields from the NDJSON contract.
  - `split_parent_into_children(parent_text: str, target_size: int = 500) -> list[str]`: split on sentence boundaries (`.`, `!`, `?` followed by whitespace).
  - `prepend_breadcrumb(text: str, heading_path: list[str]) -> str`: produce `[A > B] text` format.
  - `compute_point_id(source_file: str, page: int, chunk_index: int) -> str`: UUID5 with `EMBEDINATOR_NAMESPACE`.
- T026: [P] [US1] Write unit tests for ChunkSplitter in `tests/unit/test_chunker.py`:
  - Parent chunks within 2000-4000 chars
  - Child chunks approximately 500 chars
  - Breadcrumb prefix format `[A > B] text`
  - UUID5 determinism (same input produces same ID)
  - UUID5 uniqueness (different input produces different ID)
  - Edge cases: empty input, very short text, very long single paragraph

## Files to Create/Modify

### Create
- `backend/ingestion/chunker.py`

### Modify
- `tests/unit/test_chunker.py` (fill in test implementations in scaffold created by A1)

## Key Patterns

- **EMBEDINATOR_NAMESPACE**: Use a fixed UUID as the namespace for UUID5 generation. Define as a module-level constant: `EMBEDINATOR_NAMESPACE = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")`
- **UUID5 formula**: `uuid.uuid5(EMBEDINATOR_NAMESPACE, f"{source_file}:{page}:{chunk_index}")` per data-model.md
- **Parent chunk accumulation**: Iterate raw worker chunks. Accumulate text until reaching `parent_chunk_size` (default 3000). Start a new parent when adding the next raw chunk would exceed 4000 chars or when there is a clear section break (heading change).
- **Child chunk splitting**: Split parent text on sentence boundaries. Accumulate sentences until reaching `child_chunk_size` (default 500). Do not split mid-sentence.
- **Breadcrumb format**: `[Chapter 2 > 2.3 Auth] The actual text content...`
- **ParentChunkData dataclass**: Internal representation with `chunk_id`, `text`, `source_file`, `page`, `breadcrumb`, `children` (list of child dicts with text, point_id, chunk_index)
- **structlog**: `logger = structlog.get_logger(__name__)`
- **Settings access**: `from backend.config import settings` at module level

## Constraints

- NEVER run pytest inside Claude Code. Use: `zsh scripts/run-tests-external.sh -n spec06-chunker tests/unit/test_chunker.py`
- NEVER modify files outside your assignment (only `chunker.py` and `test_chunker.py`)
- UUID5 IDs must be deterministic -- same (source_file, page, chunk_index) always produces the same ID
- Parent chunks must be 2000-4000 characters (configurable via settings)
- Child chunks must be approximately 500 characters (configurable via settings)
- Breadcrumb prefix is prepended to child text BEFORE embedding (the prefix is part of the searchable text)

## Checkpoint

ChunkSplitter importable and tests pass:

```bash
python -c "from backend.ingestion.chunker import ChunkSplitter, EMBEDINATOR_NAMESPACE; print('Chunker OK, namespace:', EMBEDINATOR_NAMESPACE)"
ruff check backend/ingestion/chunker.py
zsh scripts/run-tests-external.sh -n spec06-chunker tests/unit/test_chunker.py
cat Docs/Tests/spec06-chunker.status
cat Docs/Tests/spec06-chunker.summary
```
