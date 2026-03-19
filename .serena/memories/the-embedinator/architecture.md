# The Embedinator — Architecture Summary

## What It Is
Self-hosted agentic RAG system: Python + Rust + LangGraph + Next.js + Qdrant + SQLite + Ollama.

## Tech Stack (pinned versions)
- Python 3.14.3, Rust 1.93.1, Next.js 16, React 19
- LangGraph >=1.0.10, LangChain >=1.2.10, FastAPI >=0.135
- Qdrant >=1.17.0, sentence-transformers >=5.2.3
- Ollama (default local), OpenRouter (default cloud)

## Core Architecture
- 3-layer LangGraph agent: ConversationGraph → ResearchGraph → MetaReasoningGraph
- Rust ingestion worker: PDF/MD/TXT → NDJSON stream → Python embeds → Qdrant
- Parent/child chunking + breadcrumbs + hybrid dense+BM25 + cross-encoder reranking
- Provider Hub: Ollama + OpenRouter + OpenAI + Anthropic (encrypted API keys in SQLite)
- Grounded Answer Verification (NLI claim checking), citation alignment, computed confidence
- Circuit breaker + retry on all external calls, embedding integrity validation

## Target Hardware
i7-12700K, 64GB DDR5, RTX 4070 Ti 12GB VRAM, NVMe SSDs

## Documentation Library (claudedocs/)
19 files total in claudedocs/:
- `architecture-design.md` — Full system architecture (4163 lines, 27 sections)
- `rag-analysis-report.md` — Source system analysis
- `prd.md` — Product Requirements Document
- `api-reference.md` — All API endpoints and schemas
- `data-model.md` — SQLite + Qdrant schemas + ER diagram
- `security-model.md` — Threat model, encryption, validation
- `testing-strategy.md` — Test pyramid, coverage targets, CI
- `performance-budget.md` — Latency/memory/throughput budgets
- `runbook.md` — Operations: deploy, backup, troubleshoot
- `changelog.md` — Version history
- `contributing.md` — Dev setup, code style, extension guides
- `adr/` — 8 Architecture Decision Records (001-008)

## Build Phases
1. **MVP (COMPLETE)**: Python FastAPI + 2-layer LangGraph + hybrid retrieval + parent/child + Next.js chat+collections + Ollama + OpenRouter. 75/75 tasks done. 61 tests passing. Docker stack validated.
2. Performance: Rust worker + MetaReasoningGraph + GAV + parallel embedding + incremental ingest + observability
3. Polish: Additional providers + per-doc-type chunk profiles + query cache + citation highlighting

## Clarified System Design Decisions
- No authentication on web interface — trusted local network model
- Multiple concurrent query sessions — each browser tab independent
- Document↔Collection: many-to-many
- Document deletion preserves traces with "source removed" marker
- Confidence score: user-facing, displayed alongside every answer

## Developer Environment
- Fedora Linux, project at /home/brunoghiberto/Documents/Projects/The-Embedinator
- Branch: `001-vision-arch`
- Claude Code runs natively
