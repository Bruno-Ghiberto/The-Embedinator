# Release Notes — v0.2.0

## The Embedinator

**Self-hosted agentic RAG system for private document intelligence.**

The Embedinator is a self-hosted retrieval-augmented generation (RAG) system that turns your private documents into a conversational knowledge base. Upload PDFs, Markdown, or plain text files, and ask natural-language questions to receive grounded, citation-backed answers with transparent confidence scoring.

Unlike simple "chat with your docs" tools, The Embedinator uses a **three-layer agentic architecture** powered by LangGraph — with meta-reasoning recovery, grounded answer verification, and 5-signal confidence scoring.

## Key Features

- **3-layer agentic RAG** — ConversationGraph, ResearchGraph, and MetaReasoningGraph orchestrated by LangGraph
- **Hybrid search** — Dense vector + BM25 sparse retrieval via Qdrant, followed by cross-encoder reranking
- **Grounded answers** — Claim-level groundedness verification with citation alignment scoring
- **5-signal confidence scoring** — Composite score from retrieval quality, reranker agreement, coverage, coherence, and source diversity
- **Meta-reasoning recovery** — Automatic strategy switching when initial retrieval produces poor results
- **Dark mode UI** — Polished Next.js 16 frontend with shadcn/ui, command palette, and responsive layout
- **Multi-provider LLM support** — Ollama (local), OpenAI, Anthropic, and OpenRouter with encrypted API key storage
- **Rust ingestion worker** — High-performance document parsing for PDF, Markdown, and plain text
- **Full observability** — Structured logging, per-query traces, stage timing, latency charts, and a metrics dashboard
- **Single-command startup** — Cross-platform launcher scripts with automatic GPU detection

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows, macOS, or Linux)

That's it. No Python, Node.js, or Rust installation required.

## Quick Start

```bash
git clone https://github.com/Bruno-Ghiberto/The-Embedinator.git
cd The-Embedinator
./embedinator.sh          # macOS / Linux
# .\embedinator.ps1       # Windows (PowerShell)
```

The launcher will:
1. Check that Docker is running
2. Generate a `.env` file with a Fernet encryption key (first run only)
3. Detect GPU availability (NVIDIA, AMD, Intel) and configure Docker accordingly
4. Build and start all four services (Qdrant, Ollama, backend, frontend)
5. Pull the default AI models (~4 GB on first run)
6. Open the application in your browser at `http://localhost:3000`

## What's in This Release

This is the first public release of The Embedinator, built across 19 detailed specifications:

| Area | Specifications |
|------|---------------|
| Agent Architecture | Vision & Architecture, Conversation Graph, Research Graph, Meta-Reasoning |
| Accuracy & Trust | Accuracy & Robustness (groundedness, citations, confidence) |
| Data Pipeline | Ingestion Pipeline (Rust worker), Storage Architecture (SQLite + Qdrant) |
| API & Frontend | API Reference (15+ REST endpoints), Next.js Frontend, UX/UI Redesign |
| Providers | Multi-Provider Architecture (Ollama, OpenAI, Anthropic, OpenRouter) |
| Quality | Component Interfaces, Error Handling, Security Hardening, Performance Budgets |
| Infrastructure | Observability, Testing Strategy, Infrastructure Setup, Cross-Platform DX |

**Test suite:** 1,487 tests across unit, integration, and E2E tiers with 87% code coverage.

## Links

- [Full Changelog](CHANGELOG.md)
- [Contributing Guide](CONTRIBUTING.md)
- [Architecture Design](docs/architecture-design.md)
- [API Reference](docs/api-reference.md)
- [Security Policy](SECURITY.md)

---

## Post-Push Manual Steps

After pushing the release to GitHub, complete these steps in the repository settings:

### 1. Enable GitHub Discussions

Go to **Settings > General > Features** and enable **Discussions**. Create four categories:
- **Announcements** (maintainer-only posting)
- **Q&A** (question/answer format)
- **Ideas** (open-ended discussion)
- **Show and Tell** (community showcase)

### 2. Set Repository Topics

Go to **Settings** (or click the gear icon next to "About") and add these topics:
`rag`, `retrieval-augmented-generation`, `llm`, `self-hosted`, `python`, `fastapi`, `nextjs`, `docker`, `langgraph`, `qdrant`, `ollama`

### 3. Upload Social Preview Image

Go to **Settings > General** and upload the social preview image from `docs/images/social-preview.png` (1280x640 pixels).

### 4. Create Good First Issues

Create issues from the descriptions in `specs/020-open-source-launch/good-first-issues.md`. Label each with `good first issue`. These can be created via the GitHub UI or with:

```bash
gh issue create --title "Issue title" --body "Issue body" --label "good first issue"
```

### 5. Make Repository Public

If the repository is currently private, go to **Settings > General > Danger Zone** and change visibility to **Public**.

### 6. Create GitHub Release

Push the version tag and let the release workflow create the GitHub Release:

```bash
git push origin v0.2.0
```

The release workflow (`.github/workflows/release.yml`) will automatically create a GitHub Release with the tag name and release notes.
