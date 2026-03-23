# Contract: Smoke Test Script

**File**: `scripts/smoke_test.py`
**FR coverage**: FR-022, FR-023, FR-024

---

## Interface

```
Usage: python scripts/smoke_test.py [OPTIONS]

Options:
  --base-url TEXT    Backend API base URL [default: http://localhost:8000]
  --frontend-url TEXT Frontend base URL [default: http://localhost:3000]
  --timeout INT      Per-check timeout in seconds [default: 30]
  --skip-chat        Skip chat checks (useful when Ollama is downloading models)
  --cleanup          Delete test data after run [default: True]
```

## Exit Codes (FR-023)

| Code | Meaning |
|------|---------|
| 0 | All checks passed |
| 1 | One or more checks failed |
| 2 | Script error (cannot connect, invalid args) |

## Checks (FR-024)

| # | Check Name | Endpoint/Action | Pass Condition |
|---|-----------|-----------------|----------------|
| 1 | Backend health | `GET /api/health` | HTTP 200 |
| 2 | Backend liveness | `GET /api/health/live` | HTTP 200 |
| 3 | Frontend health | `GET {frontend}/healthz` | HTTP 200 |
| 4 | Frontend serves HTML | `GET {frontend}/` | Response contains `<html` or `__next` |
| 5 | Collections API | `GET /api/collections` | HTTP 200, valid JSON array |
| 6 | Models API | `GET /api/models/llm` | HTTP 200, valid JSON |
| 7 | Settings API | `GET /api/settings` | HTTP 200, valid JSON |
| 8 | Create collection | `POST /api/collections` | HTTP 201, returns `id` |
| 9 | Upload document | `POST /api/collections/{id}/ingest` | HTTP 202, returns `job_id` |
| 10 | Ingestion complete | Poll `GET .../ingest/{job_id}` | Status = "complete" within 2 min |
| 11 | Chat response | `POST /api/chat` (skippable) | NDJSON response received |
| 12 | Chat has citation | Parse NDJSON (skippable) | At least 1 citation in metadata frame |
| 13 | Cleanup | `DELETE /api/collections/{id}` | HTTP 200 or 204 |

## Output Format (FR-024)

```
The Embedinator — Smoke Test
============================

[PASS]  1. Backend health (0.12s)
[PASS]  2. Backend liveness (0.08s)
[PASS]  3. Frontend health (0.15s)
[PASS]  4. Frontend HTML (0.22s)
[PASS]  5. Collections API (0.09s)
[PASS]  6. Models API (0.11s)
[PASS]  7. Settings API (0.07s)
[PASS]  8. Create collection (0.31s)
[PASS]  9. Upload document (0.45s)
[PASS] 10. Ingestion complete (12.3s)
[PASS] 11. Chat response (3.2s)
[PASS] 12. Chat citation (0.01s)
[PASS] 13. Cleanup (0.18s)

============================
Results: 13/13 passed
Exit code: 0
```

On failure:
```
[FAIL] 11. Chat response (30.0s)
         Error: Timeout after 30s — no response received

============================
Results: 10/13 passed, 3 failed
Failed: 11, 12, 13
Exit code: 1
```

## Dependencies

- `httpx` (existing dependency — async HTTP client)
- `asyncio` (stdlib)
- `json` (stdlib)
- `time` (stdlib)
- `argparse` (stdlib)
- NO new pip packages required

## Test Data Contract

- Creates collection: `"__smoke_test_{timestamp}"` (unique per run)
- Uploads: `tests/fixtures/sample.md` (must exist)
- Chat query: `"What topics are covered in this document?"` (generic)
- Cleanup: Deletes the test collection after all checks (unless `--no-cleanup`)

## Idempotency

The script is safe to run multiple times. Each run creates a uniquely-named collection
(timestamp-based) and cleans up after itself. No persistent side effects.
