# Research Findings: Storage Architecture

**Date**: 2026-03-13 | **Phase**: Phase 0 (Research & Clarification Resolution)

## Summary

No research required. All technical unknowns resolved during specification clarification session (Session 2026-03-13 in spec.md). Architecture, technology choices, and design decisions are fully specified.

## Clarifications Integrated into Spec

Five key decisions were clarified and documented in spec.md Clarifications section:

1. **Scale**: Medium deployment (1K-10K documents per collection, <1K chunks per document). SQLite WAL acceptable for write serialization at this scale.

2. **Concurrency**: Sequential queue at orchestrator level. Single writer (document at a time), concurrent readers via SQLite WAL mode. Failed jobs logged but don't block queue.

3. **Idempotent Resume**: UUID5 deterministic parent IDs enable safe re-runs. Duplicate Qdrant vectors skipped (upsert replaces), duplicate SQLite parent chunks detected by UUID5 uniqueness constraint.

4. **Batch Failure Strategy**: Entire batch fails on Qdrant timeout/error. UUID5 idempotency makes retry safe. Per-vector tracking avoided (complexity tradeoff). Orchestrator resumes when Qdrant recovers.

5. **Trace Archival**: Out-of-scope. Traces stored indefinitely; users manage archival via external SQL dumps/cron. Medium scale won't hit constraints; deferring archival avoids over-engineering.

## Technology Decisions Confirmed

- **SQLite 3.45+** with WAL mode (concurrent readers, single serialized writer)
- **Qdrant** (external Docker container, hybrid dense+BM25 vectors)
- **Fernet symmetric encryption** for API key storage (cryptography >=44.0)
- **UUID5** for deterministic parent chunk IDs (content-based hashing)
- **SHA256** for file deduplication
- **aiosqlite** for async SQLite access
- **qdrant-client >=1.17.0** for vector database client with sparse vector support
- **tenacity >=9.0** for retry logic on Qdrant/external service failures

## No Additional Research Tasks

All dependencies are external libraries with well-established patterns. No internal architectural unknowns remain. Design phase can proceed directly to entity/contract definition.

**Status**: READY FOR PHASE 1 DESIGN
