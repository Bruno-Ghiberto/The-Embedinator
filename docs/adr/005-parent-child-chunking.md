# ADR-005: Parent/Child Chunking with Breadcrumbs

**Status**: Accepted
**Date**: 2026-03-03
**Decision Makers**: Architecture Team

## Context

RAG systems face a precision/recall tension in chunking:
- Small chunks produce precise vector matches but lack context for LLM reasoning
- Large chunks provide context but embed poorly (noisy vectors)

The two source systems each solved part of this:
- agentic-rag-for-dummies: Parent/child chunk hierarchy
- GRAVITEA: Breadcrumb-aware chunking with structural metadata

## Decision

Combine **parent/child chunking** with **breadcrumb prepending**:
- **Child chunks** (~500 chars): Embedded and stored in Qdrant for precision retrieval
- **Parent chunks** (2000-4000 chars): Stored in SQLite, retrieved as LLM context when a child matches
- **Breadcrumbs**: Document hierarchy path prepended to child text before embedding (but not stored in Qdrant text payload)

## Rationale

1. **Precision retrieval**: Small child chunks produce focused vector matches
2. **Rich LLM context**: Large parent chunks prevent the LLM from reasoning about sentence fragments in isolation
3. **Structural awareness**: Breadcrumbs encode position ("Chapter 2 > 2.3 Authentication > Token Formats") into the embedding vector
4. **No payload bloat**: Breadcrumb is used only for embedding input; Qdrant stores it as a separate metadata field, not in the text payload

## Consequences

### Positive
- More powerful than either technique alone (neither source system combined both)
- Retrieval is sensitive to document structure, not just lexical content
- Parent chunks in SQLite provide indexed access and foreign key relationships

### Negative
- More complex ingestion pipeline (two-stage chunking)
- Storage overhead: parent chunks duplicated in SQLite alongside child vectors in Qdrant
- Breadcrumb extraction requires document structure parsing (heading tracker)
