# Contract: Seed Data Script

**File**: `scripts/seed_data.py`
**FR coverage**: FR-009, FR-010

---

## Interface

```
Usage: python scripts/seed_data.py [OPTIONS]

Options:
  --base-url TEXT    Backend API base URL [default: http://localhost:8000]
  --timeout INT      Ingestion timeout in seconds [default: 120]
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Seeding completed successfully |
| 1 | Seeding failed (API error, timeout, ingestion failure) |
| 2 | Cannot connect to backend |

## Behavior

### Idempotent Seeding

1. `GET /api/collections` — check if "Sample Knowledge Base" exists
2. If exists: skip creation, report existing collection
3. If not: `POST /api/collections` with `{"name": "Sample Knowledge Base", "description": "Sample documents for testing and demonstration"}`
4. Check if `sample.md` already ingested (by filename in documents list)
5. If not: `POST /api/collections/{id}/ingest` with `tests/fixtures/sample.md`
6. Poll `GET /api/collections/{id}/ingest/{job_id}` until complete or timeout
7. Report final state

### Output

```
Seed Data — The Embedinator
============================
Collection: Sample Knowledge Base (id: 1)
  Status: created (new)
Document: sample.md
  Status: ingested (14 chunks)
============================
Seeding complete.
```

On idempotent re-run:
```
Seed Data — The Embedinator
============================
Collection: Sample Knowledge Base (id: 1)
  Status: exists (skipped)
Document: sample.md
  Status: already ingested (skipped)
============================
Already seeded. Nothing to do.
```

## Dependencies

- `httpx` (existing dependency)
- `asyncio` (stdlib)
- `pathlib` (stdlib — for fixture file path)
- `argparse` (stdlib)
- NO new pip packages required

## File Dependency

- `tests/fixtures/sample.md` MUST exist (already present in repository)
- Script resolves the path relative to repository root using `pathlib.Path`
