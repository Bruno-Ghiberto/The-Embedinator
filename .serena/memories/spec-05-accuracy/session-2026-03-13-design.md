# Spec-05 Accuracy — Design Session 2026-03-13

## Session Summary
Rewrote `05-implement.md` and created 7 agent instruction files for Agent Teams workflow.

## What Was Done
1. **Rewrote** `Docs/PROMPTS/spec-05-accuracy/05-implement.md` (843 lines)
   - Full codebase verification via Serena MCP (15 facts checked against live code)
   - Agent Teams + tmux multi-pane orchestration protocol prominently enforced
   - Code specifications for all 6 user stories aligned with spec artifacts
   - Shared file conflict resolution documented (Wave 2: A2/A3/A4 all touch nodes.py)

2. **Created 7 agent instruction files** in `Docs/PROMPTS/spec-05-accuracy/agents/`:
   - A1-setup-foundations.md — python-expert, Sonnet (setup scaffolding, test skeletons, final polish)
   - A2-verify-groundedness.md — python-expert, Opus (GAV node, structured LLM output)
   - A3-validate-citations.md — python-expert, Sonnet (cross-encoder citation scoring)
   - A4-tier-params-rewrite.md — python-expert, Sonnet (TIER_PARAMS + rewrite_query)
   - A5-circuit-breakers.md — python-expert, Opus (full CB state machine + Tenacity retry)
   - A6-ndjson-metadata.md — python-expert, Sonnet (metadata frame with groundedness)
   - A7-integration-tests.md — quality-engineer, Sonnet (integration test suite)

## Key Codebase Findings (via Serena)
- nodes.py uses `*, llm` / `*, reranker` keyword injection (spec-02 pattern), NOT `config: RunnableConfig`
- QdrantClientWrapper has rudimentary inline CB logic → upgraded to full state machine per ADR-001
- schemas.py already has ClaimVerification, GroundednessResult, QueryAnalysis stubs
- conversation_graph.py already has node stubs wired

## Wave Structure (4 waves, 7 agents)
- Wave 1: A1 (setup + test skeletons)
- Wave 2: A2, A3, A4 (parallel — GAV / citations / tier params)
- Wave 3: A5, A6, A7 (parallel — circuit breakers / NDJSON / integration tests)
- Wave 4: A1 (final polish + full test suite)

## Status: READY FOR IMPLEMENTATION
Next step: Run Agent Teams with tmux orchestration per 05-implement.md
