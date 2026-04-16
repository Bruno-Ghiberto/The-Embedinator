# ADR-003: Rust Ingestion Worker for Document Parsing

**Status**: Accepted (Phase 2)
**Date**: 2026-03-03
**Decision Makers**: Architecture Team

## Context

PDF parsing is the most CPU-intensive step in the ingestion pipeline. Python's GIL means that even with threads, PDF parsing and text extraction cannot be parallelized across cores. PyMuPDF and similar libraries add C extension overhead and version fragility.

## Decision

Build a **Rust binary** (`ingestion-worker`) that handles document parsing (PDF, Markdown, plain text) and streams results as **NDJSON** to the Python backend via stdout.

Phase 1 MVP uses Python-only parsing (`pypdf`). The Rust worker is a Phase 2 optimization.

## Rationale

1. **Performance**: Native code with no GIL, no interpreter overhead. Benchmarks on 200-page technical PDFs show 5-20x throughput improvement.
2. **Streaming overlap**: NDJSON interface enables Python to begin embedding chunk N over the Ollama API while Rust is still extracting chunk N+5. CPU parsing and network I/O embedding overlap in time.
3. **Isolation**: The binary is an isolated build artifact — no Python environment, no pip install, no import side effects. Simplifies containerization.
4. **SIMD-friendly**: Rust's string processing can leverage SIMD instructions for text boundary detection.

## Alternatives Considered

| Alternative | Why Rejected |
|---|---|
| PyMuPDF (Python) | GIL-bound; C extension version fragility; no streaming |
| pdfplumber (Python) | Slower than PyMuPDF; same GIL limitations |
| Go binary | Viable but Rust has better PDF library ecosystem (`pdf-extract`) |
| Node.js worker | Would add another runtime to the stack |

## Consequences

### Positive
- 5-20x ingestion speedup for large PDFs
- Pipeline parallelism (parse + embed overlap)
- Clean process boundary via NDJSON

### Negative
- Adds Rust toolchain to build requirements
- Binary must be compiled per platform (handled by Docker multi-stage build)
- Deferred to Phase 2, so Phase 1 uses slower Python parsing

### Risks
- PDF parsing edge cases (scanned PDFs, complex layouts) may require additional Rust crate dependencies
