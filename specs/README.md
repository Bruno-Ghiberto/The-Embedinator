# specs/

Feature specifications for The Embedinator. Each spec defines user stories,
functional requirements, success criteria, and implementation tasks for a
specific subsystem.

## Specification Lifecycle

Each specification follows a structured process:

1. **Definition** -- User stories, functional requirements, and success criteria
2. **Task breakdown** -- Implementation tasks organized in phases
3. **Implementation** -- Code changes guided by the spec
4. **Validation** -- Success criteria verification and test coverage

## Specifications

| #   | Directory                 | Name                    | Scope                                              |
|-----|---------------------------|-------------------------|------------------------------------------------------|
| 001 | `001-vision-arch/`        | Vision & Architecture   | Overall system design, tech stack, layer definitions  |
| 002 | `002-conversation-graph/` | Conversation Graph      | Layer 1: session management, intent, history          |
| 003 | `003-research-graph/`     | Research Graph          | Layer 2: tools, hybrid search, iterative research     |
| 004 | `004-meta-reasoning/`     | Meta-Reasoning          | Layer 3: failure detection, strategy recovery         |
| 005 | `005-accuracy-robustness/`| Accuracy & Robustness   | Groundedness, citations, confidence scoring           |
| 006 | `006-ingestion-pipeline/` | Ingestion Pipeline      | Rust worker, chunking, embedding, Qdrant upsert       |
| 007 | `007-storage-architecture/`| Storage Architecture   | SQLite schema, Qdrant collections, encryption         |
| 008 | `008-api-reference/`      | API Reference           | FastAPI endpoints, schemas, rate limiting              |
| 009 | `009-next-frontend/`      | Next.js Frontend        | React 19 UI, pages, components, hooks                 |
| 010 | `010-provider-architecture/`| Provider Architecture | Multi-provider LLM support, registry pattern          |
| 011 | `011-component-interfaces/`| Component Interfaces   | Contract tests, interface signatures                  |
| 012 | `012-error-handling/`     | Error Handling          | Exception hierarchy, structured error responses       |
| 013 | `013-security-hardening/` | Security Hardening      | Input sanitization, CORS, rate limits                 |
| 014 | `014-performance-budgets/`| Performance Budgets     | Latency targets, stage timing, memory budgets         |
| 015 | `015-observability/`      | Observability           | Structured logging, traces, metrics, dashboards       |
| 016 | `016-testing-strategy/`   | Testing Strategy        | Test organization, coverage targets, fixtures         |
| 017 | `017-infra-setup/`        | Infrastructure Setup    | Docker Compose, Makefile, Dockerfile, CI setup        |

## How Specs Relate to Code

Each spec maps to specific source files and test files. The CLAUDE.md file
in the project root maintains a mapping of active technologies and paths
per spec. The specs are numbered in dependency order: lower-numbered specs
define foundational architecture that higher-numbered specs build upon.

## Current Status

All 17 specifications are **implementation complete** as of the current
branch. See [`../Docs/DEVELOPMENT-STATUS.md`](../Docs/DEVELOPMENT-STATUS.md)
for detailed status and known issues.
