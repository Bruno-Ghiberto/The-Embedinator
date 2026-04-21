# Research: Spec 25 --- Master Debug Battle Test

**Date**: 2026-03-31
**Status**: Complete (minimal unknowns --- testing spec with well-defined requirements)

## Research Summary

Spec-25 is a testing-only spec with zero production code changes. The research phase focused on validating assumptions about the test environment, model availability, and PaperclipAI orchestration feasibility. All technical decisions are pre-resolved from the spec and the 25-plan.md design document.

## Decision Log

### D1: Model Combination Feasibility on 12GB GPU

**Decision**: Test all 7 combinations sequentially. Expect phi4:14b (combo 4) to potentially OOM. Mark infeasible combos as "VRAM-exceeded" rather than skipping them silently.

**Rationale**: The RTX 4070 Ti has 12GB VRAM. Combos 1-3, 5 use ~4.4-5.0GB (safe). Combo 4 (phi4:14b) uses ~9.1GB, leaving only ~3GB for KV cache --- may fail on long-context queries. Combos 6-7 use ~5.4GB (safe but require re-ingestion due to different embedding dimensions).

**Alternatives Considered**:
- Skip phi4:14b entirely --- rejected because the VRAM stress test is explicitly required (FR-031) and the failure behavior itself is valuable data.
- Run phi4:14b with reduced context length --- rejected because we want to observe the natural failure mode, not a pre-optimized configuration.

### D2: Embedding Swap Protocol for Combos 6-7

**Decision**: Create new Qdrant collections with a "spec25-mxbai-" prefix for mxbai-embed-large testing. Re-ingest the same seed documents. Clean up test collections after scoring.

**Rationale**: nomic-embed-text and mxbai-embed-large produce different vector dimensions. Qdrant collections are dimension-fixed at creation time. Reusing existing collections is impossible. FR-027 explicitly requires documenting re-ingestion time and errors.

**Alternatives Considered**:
- Modify existing collection dimensions --- impossible in Qdrant. Collections are immutable once created.
- Skip combos 6-7 entirely --- rejected because embedding model comparison is a core spec requirement.

### D3: PaperclipAI vs Claude Code Agent Teams

**Decision**: Use PaperclipAI orchestration exclusively. This is NOT a Claude Code Agent Teams spec.

**Rationale**: The 25-plan.md explicitly states: "This is NOT a Claude Code Agent Teams spec. This runs on PaperclipAI." The human-in-the-loop protocol, heartbeat-based agent scheduling, and atomic task checkout are PaperclipAI features that do not exist in Claude Code Agent Teams.

**Alternatives Considered**:
- Claude Code Agent Teams --- rejected because the spec requires real-time human direction (browser actions), Docker log monitoring, and multi-session persistence. PaperclipAI's CEO agent + heartbeat model is designed for exactly this orchestration pattern.

### D4: Engram Topic Key Schema

**Decision**: Use the registry defined in 25-plan.md: `spec-25/p{N}-{phase-name}` for phase results, `spec-25/bugs` for the running bug registry, `spec-25/session-{N}` for session snapshots.

**Rationale**: Structured topic keys enable precise retrieval across sessions. The per-phase granularity matches the phase summary requirement (NFR-003). The session snapshot keys enable mid-phase recovery.

**Alternatives Considered**:
- Single key per session --- rejected because it would make phase-level retrieval impossible without parsing.
- Nested keys (e.g., `spec-25/p3/combo-1`) --- considered but rejected for simplicity. Phase-level granularity is sufficient; sub-phase detail goes in the topic content.

### D5: Scoring Rubric Weight Calibration

**Decision**: Use the weights defined in spec.md: Answer Quality (0.30), Citation Accuracy (0.25), Response Coherence (0.15), Latency Score (0.15), VRAM Efficiency (0.10), Streaming Smoothness (0.05).

**Rationale**: The weights reflect RAG system priorities. Answer quality and citation accuracy are the primary value proposition. Latency matters but is secondary to correctness. VRAM efficiency matters for the hardware constraint but is less important than quality. Streaming smoothness is a minor UX factor.

**Alternatives Considered**:
- Equal weights --- rejected because it would overweight VRAM and streaming (less impactful dimensions).
- Drop VRAM weight entirely --- rejected because the 12GB constraint makes VRAM efficiency a real differentiator between combos.

### D6: Edge Case Test Execution Context

**Decision**: Edge case tests (FR-034 through FR-045) are executed during Phase 2 (Core Functionality Sweep) as part of the broader functional testing, with SC-007 tracking them separately.

**Rationale**: The 25-plan.md assigns edge case testing to Phase 2 with A2 (quality-engineer) and CEO direction. This makes sense because edge cases are boundary conditions of core functionality, not a separate testing domain.

**Alternatives Considered**:
- Separate edge case phase --- rejected because it would add an unnecessary sequential dependency. Edge cases are naturally tested alongside core functionality.

## Open Questions

None. All technical decisions are resolved from the spec, 25-plan.md, and project constitution. The spec was thoroughly clarified in the 2026-03-31 session.

## Environment Assumptions

| Assumption | Verified? | Source |
|------------|-----------|--------|
| RTX 4070 Ti with 12GB VRAM | Yes | Project memory, GPU/Docker notes |
| Docker Compose 4-service stack | Yes | Constitution Principle VII |
| Ollama serving models locally | Yes | Constitution Principle I |
| Seed data exists (collections + documents) | Assumption | Verified at P1 runtime (T006) |
| PaperclipAI agents available | Yes | 25-plan.md agent roster (all existing agents) |
| Engram persistent storage operational | Yes | Project memory protocol (CLAUDE.md) |
| Frontend at localhost:3000 | Yes | Docker Compose configuration |
| Backend at localhost:8000 | Yes | Docker Compose configuration |
| Qdrant at localhost:6333 | Yes | Docker Compose configuration |
| Ollama at localhost:11434 | Yes | Docker Compose configuration |
