# Spec-13 Security Hardening — Implementation Summary

**Date**: 2026-03-18
**Branch**: `013-security-hardening`
**Status**: COMPLETE (28/28 tasks, 26 new tests, 1326 total passing, 0 regressions)

## Production Changes (4 files, ~30 lines net-new)

| FR | File | Change |
|----|------|--------|
| FR-001 | `backend/api/chat.py:75` | `message = body.message[:10_000]` silent truncation + 2 reference replacements |
| FR-002 | `backend/retrieval/searcher.py:28,74` | `ALLOWED_FILTER_KEYS` constant + `continue` guard in `_build_filter()` |
| FR-003 | `backend/api/ingest.py:4,22-30,85` | `import re as _re`, `_SAFE_FILENAME` regex, `_sanitize_filename()` function |
| FR-004 | `backend/api/ingest.py:69-79` | PDF magic byte check after size check, before collection check |
| FR-006 | `backend/main.py:29-36,45` | `_strip_sensitive_fields()` + insertion at processor chain position -2 |
| FR-007 | *(none)* | Already implemented in spec-10 — verification tests only |

## Test Files (5 files, 26 tests)

- `tests/unit/api/test_ingest_security.py` — 10 tests (FR-003, FR-004, FR-005, FR-008)
- `tests/unit/api/test_chat_security.py` — 4 tests (FR-001)
- `tests/unit/retrieval/test_searcher_security.py` — 5 tests (FR-002)
- `tests/unit/test_main_security.py` — 5 tests (FR-006)
- `tests/unit/api/test_providers_security.py` — 2 tests (FR-007)

## Existing Tests Fixed

- `tests/unit/test_ingest_router.py` — 2 tests updated: b"test content" → b"%PDF-1.4 test content" for PDF uploads
- `tests/unit/test_ingestion_api.py` — 1 test updated with same fix

## Key Decisions

- No new dependencies (stdlib `re` only) — SC-007 enforced
- All truncation/filtering is silent (no errors, no logs)
- PDF magic check is PDF-only (FR-005 implicit)
- `_SENSITIVE_KEYS` case-insensitive matching on top-level keys only
- 39 pre-existing failures unchanged
