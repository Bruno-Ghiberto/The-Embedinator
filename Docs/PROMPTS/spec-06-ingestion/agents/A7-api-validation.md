# Agent: A7-api-validation

**subagent_type**: security-engineer | **Model**: Sonnet 4.6 | **Wave**: 3

## Mission

Add MIME content-type validation for PDF uploads to the ingest endpoint and write comprehensive file validation and edge case tests. Ensure all 12 supported file types are accepted, unsupported types are rejected with clear error messages, and edge cases (zero-content files, missing worker binary, concurrent uploads) are handled correctly.

## Context Files (Read FIRST)

1. `Docs/PROMPTS/spec-06-ingestion/06-implement.md` -- full code specifications (the authoritative reference)
2. `specs/006-ingestion-pipeline/spec.md` -- FR-002 (reject unsupported + oversized), US5 acceptance scenarios
3. `specs/006-ingestion-pipeline/contracts/ingest-api.md` -- error response schemas (400, 413, 409)
4. `specs/006-ingestion-pipeline/research.md` -- R2: MIME validation strategy (PDF only, extension-only for code)
5. `specs/006-ingestion-pipeline/data-model.md` -- document upload validation rules table
6. `specs/006-ingestion-pipeline/tasks.md` -- T044-T046
7. `backend/api/documents.py` -- ingest endpoint (created by A2), SUPPORTED_FORMATS

## Assigned Tasks

- T044: [US5] Add MIME content-type validation for PDF uploads in `backend/api/documents.py`: check `file.content_type == "application/pdf"` for `.pdf` files per R2. For code files, skip MIME check (extension-only validation). Insert this check in the ingest endpoint after extension validation.
- T045: [US5] Write comprehensive file validation tests in `tests/unit/test_ingestion_api.py`:
  - All 12 supported types accepted (`.pdf`, `.md`, `.txt`, `.py`, `.js`, `.ts`, `.rs`, `.go`, `.java`, `.c`, `.cpp`, `.h`)
  - Unsupported types rejected (`.exe`, `.zip`, `.docx`, `.xlsx`) with HTTP 400 and error code `INVALID_FILE`
  - File > 100MB rejected with HTTP 413
  - PDF with wrong MIME type rejected with HTTP 400
  - `.ts` file with MIME `video/mp2t` accepted (extension-only for code files, per R2)
- T046: [US5] Write edge case tests in `tests/unit/test_ingestion_api.py`:
  - Zero-content PDF produces completed document with `chunk_count=0` (not failed)
  - Missing worker binary returns clear error
  - Concurrent upload of same file to same collection -- second rejected by UNIQUE constraint

## Files to Create/Modify

### Modify
- `backend/api/documents.py` (add MIME validation to ingest endpoint)
- `tests/unit/test_ingestion_api.py` (fill in comprehensive validation tests)

## Key Patterns

- **MIME validation (R2)**: Only check MIME for `.pdf` files. For all other types (markdown, text, code), rely on extension validation only. The rationale is that code files have unreliable MIME types across operating systems (e.g., `.ts` files report as `video/mp2t`).
- **MIME check placement**: Insert after extension validation but before hash computation in the ingest endpoint:
  ```python
  if suffix == ".pdf":
      if file.content_type != "application/pdf":
          raise HTTPException(status_code=400, detail={
              "error": "INVALID_FILE",
              "message": f"PDF file has invalid content type: {file.content_type}",
          })
  ```
- **Test setup**: Use FastAPI `TestClient` with `httpx`. Create mock file uploads via `UploadFile` or multipart form data.
- **SUPPORTED_FORMATS**: Already extended to 12 types by A2. Your tests verify all 12 are accepted.
- **Edge case: zero-content PDF**: The Rust worker produces zero chunks for image-only PDFs. The pipeline should complete with `chunk_count=0` and document status `completed` (not `failed`).
- **Edge case: missing worker**: If `settings.rust_worker_path` points to a nonexistent binary, the subprocess spawn raises `FileNotFoundError`. The pipeline should catch this and set job status=`failed`.
- **structlog**: Use `logger = structlog.get_logger(__name__)` if adding any logging.

## Constraints

- NEVER run pytest inside Claude Code. Use: `zsh scripts/run-tests-external.sh -n spec06-api tests/unit/test_ingestion_api.py`
- NEVER modify `backend/config.py`, `backend/storage/sqlite_db.py`, `backend/storage/parent_store.py`
- NEVER modify Rust files or `backend/ingestion/pipeline.py`
- When modifying `documents.py`, only add the MIME validation check. Do not change the endpoint structure or other validation logic.
- Your test file (`test_ingestion_api.py`) may already have tests from A2 (endpoint tests). Add your tests in separate test classes or at the end of existing classes -- do not overwrite A2's tests.

## Checkpoint

MIME validation added, all validation tests pass:

```bash
ruff check backend/api/documents.py
zsh scripts/run-tests-external.sh -n spec06-api tests/unit/test_ingestion_api.py
cat Docs/Tests/spec06-api.status
cat Docs/Tests/spec06-api.summary
```
