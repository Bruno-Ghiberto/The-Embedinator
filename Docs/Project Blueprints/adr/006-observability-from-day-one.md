# ADR-006: Observability from Day One

**Status**: Accepted
**Date**: 2026-03-03
**Decision Makers**: Architecture Team

## Context

Without query traces, it is impossible to systematically improve retrieval quality after deployment. Most open-source RAG systems rely on stdout logging, which requires a log aggregation pipeline to be useful.

## Decision

Persist every query's execution trace in the SQLite `query_traces` table and expose it through a `/observability` UI page.

## Rationale

1. **Zero incremental cost**: Writing a trace record adds microseconds to a query that already takes seconds
2. **Durable history**: Data survives process restarts (unlike in-memory or stdout logs)
3. **Actionable insights**: The observability page derives insights directly from the SQLite table — no external tooling required
4. **Debugging support**: Trace ID propagation via `contextvars` correlates all log entries for a single request

## What Traces Capture

- Query text and decomposed sub-questions
- Collections searched
- Chunks retrieved with relevance scores
- Whether MetaReasoningGraph was triggered
- LLM and embedding model used
- End-to-end latency
- Confidence score

## Consequences

### Positive
- Systematic retrieval quality improvement cycle
- Confidence distribution analysis reveals weak query patterns
- Meta-reasoning rate metric shows system resilience

### Negative
- SQLite table grows linearly with query count (mitigated by optional cleanup/archival)
- Trace detail view requires additional API endpoint and UI work (Phase 2)
