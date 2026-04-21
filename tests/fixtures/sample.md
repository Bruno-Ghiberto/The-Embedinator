## Overview

This document describes a sample system for testing document ingestion, embedding, and retrieval pipelines. It is used as a fixture in the automated test suite for The Embedinator project.

The system processes documents through a multi-stage pipeline that extracts text from various formats including PDF and Markdown, generates dense and sparse vector embeddings, and stores the results in a Qdrant vector database for semantic search and retrieval.

## Features

- Text extraction from PDF, Markdown, and plain text formats
- Hybrid dense and sparse (BM25) vector search via Qdrant
- Cross-encoder reranking for precision improvement
- Overlapping chunk strategy to preserve context across boundaries
- Incremental ingestion with content-hash deduplication

## Architecture

The retrieval pipeline consists of several distinct stages. First, documents are submitted via the REST API. A background job orchestrator manages the ingestion lifecycle, calling the Rust binary for format-specific extraction when needed.

After extraction, the chunker splits text into fixed-size overlapping segments. Each segment is embedded using a sentence-transformer model. The embeddings are written to Qdrant as point vectors alongside sparse BM25 representations for hybrid retrieval.

## Code Example

```python
from backend.retrieval.searcher import HybridSearcher

searcher = HybridSearcher(settings=settings)
results = await searcher.search(
    query="document processing pipeline",
    collection="test_collection",
    top_k=5,
)
for chunk in results:
    print(chunk.chunk_id, chunk.dense_score, chunk.text[:80])
```

## Query and Reranking

The results are returned in descending relevance order after reranking. A cross-encoder model scores each candidate pair `(query, chunk_text)` and the top-k chunks are surfaced to the language model for answer synthesis.

Score normalization ensures that dense and sparse scores are on a comparable scale before combination. The `normalize_scores` function applies per-collection min-max normalization to `dense_score` values across the result set.
