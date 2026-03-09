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
→ Can run qwen2.5:32b comfortably (GPU+RAM split)

## Key Files
- Architecture doc: claudedocs/architecture-design.md (4163 lines, 13 Mermaid diagrams, 27 sections)
- Analysis report: claudedocs/rag-analysis-report.md

## Build Phases
1. MVP: Python FastAPI + 2-layer LangGraph + hybrid retrieval + parent/child + Next.js chat+collections + Ollama + OpenRouter
2. Performance: Rust worker + MetaReasoningGraph + GAV + parallel embedding + incremental ingest + observability
3. Polish: Additional providers + per-doc-type chunk profiles + query cache + citation highlighting

## Clarified System Design Decisions (2026-03-04)
- No authentication on web interface — trusted local network model, any LAN device can access
- Multiple concurrent query sessions supported — each browser tab is fully independent
- Document↔Collection: many-to-many (one doc can belong to multiple collections simultaneously)
- Document deletion: traces retain captured passage text with "source removed" indicator
- Confidence score: user-facing — displayed in main answer view alongside every response

## Speckit Splitting (17 specs) — COMPLETED
Location: SPECS/ (51 files, 14,530 lines) — legacy context prompt files
spec-01-vision, spec-02-conversation-graph, spec-03-research-graph, spec-04-meta-reasoning,
spec-05-accuracy, spec-06-ingestion, spec-07-storage, spec-08-api, spec-09-frontend,
spec-10-providers, spec-11-interfaces, spec-12-errors, spec-13-security, spec-14-performance,
spec-15-observability, spec-16-testing, spec-17-infra

## Speckit Workflow (active)
Location: specs/ (speckit-managed, with git branches per feature)
- `001-vision-arch` branch: spec DONE + clarified → ready for /speckit.plan
  - spec: specs/001-vision-arch/spec.md
  - checklist: specs/001-vision-arch/checklists/requirements.md

## Developer Environment
- WSL2 Ubuntu on Windows, project lives at /home/bruno_linux/projects/the-embedinator
- IDE: Cursor via WSL extension (`cursor .` from WSL terminal)
- Claude Code runs in WSL natively
