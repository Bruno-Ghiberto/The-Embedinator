# Implementation Plan: Master Debug --- Full-Stack Battle Test

**Branch**: `025-master-debug` | **Date**: 2026-03-31 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/025-master-debug/spec.md`

**Note**: This plan was filled by `/speckit.plan`. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Spec-25 is a testing-only spec that produces zero production code changes. It subjects the fully-built Embedinator application to a systematic 10-phase battle test covering infrastructure verification, core functionality, 7 LLM/embedding model combinations, chaos engineering, security probing, data quality audit, UX journey audit, performance profiling, and regression sweep. The output is a comprehensive quality report with a prioritized bug registry, model scorecard, and actionable fix recommendations.

Execution uses PaperclipAI multi-agent orchestration with a CEO agent directing a human tester through ACTION/OBSERVE/LOG CHECK/EXPECTED cycles. 7 specialist agents analyze findings, investigate bugs, and compile reports. All findings persist to Engram for cross-session durability.

## Technical Context

**Language/Version**: Python 3.14+ (backend), TypeScript 5.7 (frontend), Go 1.24+ (TUI installer), Rust 1.93.1 (ingestion worker)
**Primary Dependencies**: FastAPI >=0.135, LangGraph >=1.0.10, Next.js 16, React 19, Qdrant >=1.17.0, Ollama (local inference)
**Storage**: SQLite WAL (`data/embedinator.db`), Qdrant (vector search), localStorage (frontend sessions)
**Testing**: Manual human-in-the-loop testing orchestrated by PaperclipAI CEO agent. No automated test scripts produced.
**Target Platform**: Docker Compose on Linux (Fedora 43) with NVIDIA RTX 4070 Ti (12GB VRAM)
**Project Type**: Full-stack battle test / quality audit (testing-only, zero production code changes)
**Performance Goals**: Establish baselines --- TTFT, total latency, streaming throughput, GPU memory profiles per model combination
**Constraints**: 12GB GPU memory budget (one model at a time), single-user concurrency, system must be restored after every chaos test, all findings must survive session boundaries via Engram persistence
**Scale/Scope**: 10 testing phases, 78 FRs, 8 NFRs, 12 SCs, 7 model combinations, 98 test tasks (T001-T098) plus 12 gate check items (110 total), 3-5 testing sessions

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | Rationale |
|---|-----------|--------|-----------|
| I | Local-First Privacy | PASS | Testing-only spec. No code changes. All testing runs on local Docker stack with Ollama. No cloud dependencies introduced. |
| II | Three-Layer Agent Architecture | PASS | No modifications to agent architecture. Testing validates the existing 3-layer design (ConversationGraph -> ResearchGraph -> MetaReasoningGraph). |
| III | Retrieval Pipeline Integrity | PASS | No modifications to retrieval pipeline. Testing validates existing hybrid search + reranking behavior. Model comparison tests different embedding models but does not change pipeline logic. |
| IV | Observability from Day One | PASS | Testing validates trace recording, confidence scores, and observability dashboards. No modifications to observability infrastructure. |
| V | Secure by Design | PASS | Security probing (Phase 6) validates existing security controls (prompt injection resistance, XSS prevention, rate limiting, input validation). No security controls are weakened or bypassed. |
| VI | NDJSON Streaming Contract | PASS | Testing validates the existing NDJSON streaming contract (chunk events, metadata frame, error frames). No protocol changes. |
| VII | Simplicity by Default | PASS | No new services, dependencies, or infrastructure. Testing uses existing Docker Compose stack. Output is documentation artifacts only. |
| VIII | Cross-Platform Compatibility | PASS | Testing runs on the current platform (Linux/Docker). No platform-specific assumptions introduced. Report findings apply to all platforms since Docker abstracts infrastructure. |

**Result**: ALL 8 PRINCIPLES PASS. No violations. No complexity justifications needed.

## Project Structure

### Documentation (this feature)

```text
specs/025-master-debug/
  plan.md              # This file (speckit.plan output)
  spec.md              # Feature specification
  research.md          # Phase 0 output (minimal --- testing spec with clear requirements)
  data-model.md        # Phase 1 output (test entities, state machines, scoring models)
  quickstart.md        # Phase 1 output (how to launch PaperclipAI for spec-25)
  checklists/          # Pre-existing checklists directory
  contracts/
    bug-report.md        # Structured bug report template + severity classification
    scorecard.md         # Model comparison scorecard format + scoring rubric
    phase-summary.md     # Per-phase summary template
    final-report.md      # Final report structure (sections, content requirements)
    paperclipai-task.md  # PaperclipAI task format (CEO -> agent task creation)
    human-protocol.md    # Human-in-the-loop ACTION/OBSERVE/LOG CHECK/EXPECTED protocol
    engram-keys.md       # Engram topic key registry + persistence contracts
    gate-checks.md       # Gate check procedures (Gates 1-4)
```

### Source Code (repository root)

```text
# NO source code changes. This is a testing-only spec (NFR-001).
# The following existing structure is TESTED, not MODIFIED:

backend/
  agent/                 # Tested: conversation_graph, research_graph, nodes, edges, state
  retrieval/             # Tested: hybrid search, reranking, score normalization
  storage/               # Tested: SQLite parent chunks, Qdrant vectors
  api/                   # Tested: chat endpoint, collections, documents, settings, health
  config.py              # Tested: settings persistence, model switching
  main.py                # Tested: app startup, lifespan, service dependencies

frontend/
  src/                   # Tested: all 5 pages (chat, collections, settings, observability, home)
                         # Tested: dark/light themes, keyboard nav, responsive design, error states

data/
  embedinator.db         # Tested: data persistence across restarts, chaos recovery
  checkpoints.db         # Tested: session continuity, conversation history
```

**Structure Decision**: No source code modifications. All output artifacts go to `specs/025-master-debug/` and Engram persistent storage. The existing application stack is the test subject.

## Complexity Tracking

> No constitution violations detected. This table is empty by design.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| (none)    | ---        | ---                                 |
