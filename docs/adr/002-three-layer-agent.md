# ADR-002: Three-Layer LangGraph Agent Architecture

**Status**: Accepted
**Date**: 2026-03-03
**Decision Makers**: Architecture Team

## Context

Single-loop agentic RAG systems fail silently: the agent exhausts its tool budget, generates a hallucinated or "I don't know" response, and offers the user no path to improvement. Both analyzed source systems had this failure mode:
- GRAVITEA had no agent loop at all (single-pass retrieval)
- agentic-rag-for-dummies had a two-level loop with a fallback node but no strategy switching

## Decision

Implement a **three-layer nested LangGraph state machine** architecture:
1. **ConversationGraph** — Session lifecycle, intent classification, query rewriting, fan-out
2. **ResearchGraph** — Per-sub-question tool-based retrieval with iteration budget
3. **MetaReasoningGraph** — Retrieval failure diagnosis and autonomous strategy switching

## Rationale

1. **Failure recovery**: When ResearchGraph fails to meet confidence threshold, MetaReasoningGraph asks "Why did retrieval fail?" instead of falling back immediately.
2. **Quantitative diagnosis**: Cross-encoder evaluation provides a signal — low chunk scores indicate routing problems; moderate scores with low coherence indicate filter over-restriction.
3. **Strategy switching**: Each diagnosis maps to a concrete action (widen search, change collection, relax filters), enabling autonomous recovery.
4. **Bounded meta-reasoning**: Maximum 2 meta-attempts prevents infinite loops while giving meaningful recovery opportunity.

## Alternatives Considered

| Alternative | Why Rejected |
|---|---|
| Single-loop agent (LangChain AgentExecutor) | Fails silently on hard queries; no diagnostic capability |
| Two-layer (Conversation + Research only) | Better than single-loop but no failure recovery mechanism |
| Prompt-based retry ("try again") | No diagnostic signal; wastes tokens on same strategy |

## Consequences

### Positive
- Primary architectural differentiator over both source systems
- Measurable improvement in answer quality for hard queries
- Observable failure recovery through query traces

### Negative
- Higher complexity: three graph definitions, more state to manage
- Increased latency when MetaReasoningGraph triggers (1-2 seconds additional)
- MetaReasoningGraph deferred to Phase 2 — Phase 1 MVP uses 2 layers only

### Risks
- MetaReasoningGraph strategies may not always improve results — bounded by 2 attempts to limit wasted compute
