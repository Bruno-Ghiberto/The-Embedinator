# Agent: agent-polish

**subagent_type**: self-review | **Model**: Opus 4.6 | **Wave**: 5

## Mission

Fix any broken tests from Waves 2-4, verify all functional requirements are met (FR-016 retry, FR-017 logging, FR-009 confidence), ensure code quality, and update CLAUDE.md with spec-03 changes.

## Context Files (Read FIRST)

1. `Docs/PROMPTS/spec-03-research-graph/03-implement.md` -- done criteria checklist
2. `Docs/Tests/` -- check all `*.status` and `*.summary` files for failures
3. `CLAUDE.md` -- update with spec-03 project structure additions
4. `backend/agent/research_nodes.py` -- verify FR-016 retry-once in tools_node
5. `backend/agent/research_edges.py` -- verify F1 confidence-first ordering
6. `backend/agent/confidence.py` -- verify R8 5-signal formula
7. `backend/retrieval/searcher.py` -- verify C1 circuit breaker on all call sites
8. `backend/retrieval/reranker.py` -- verify R5 model.rank() usage
9. `backend/agent/tools.py` -- verify R6 closure-based factory

## Assigned Tasks

- T051: Run all tests, read summaries, fix any failures
- T052: Verify FR-016 (retry-once): `tools_node` retries failed tool calls exactly once, both attempts count against budget
- T053: Verify FR-017 (structured logging): structlog calls at loop start/end, each tool call, compression events, confidence changes, fallback triggers
- T054: Verify FR-009 (confidence): `compute_confidence()` uses 5-signal formula (R8), returns float 0.0-1.0, NOT LLM self-assessment
- T055: Verify C1 (circuit breaker): ALL Qdrant call sites in HybridSearcher are protected
- T056: Verify confidence scale mismatch is handled: `settings.confidence_threshold / 100` in edge function
- T057: Update `CLAUDE.md` project structure with new spec-03 files and patterns

## Files to Create/Modify

- MODIFY: Any files with test failures (from Wave 2-4 output)
- MODIFY: `CLAUDE.md` -- add spec-03 file structure and patterns

## Key Patterns

- Read test summaries first: `cat Docs/Tests/<name>.summary`
- Fix root causes, not symptoms -- if a test fails, understand why before patching
- For CLAUDE.md updates: add `backend/agent/research_graph.py`, `research_nodes.py`, `research_edges.py`, `tools.py` to project structure; add `backend/retrieval/` package; add `backend/storage/parent_store.py`
- Verify the Done Criteria checklist from 03-implement.md item by item

## Constraints

- NEVER run pytest inside Claude Code. Use: `zsh scripts/run-tests-external.sh -n <name> <target>`
- NEVER break existing spec-02 tests -- run the full suite, not just spec-03 tests
- Do NOT add new features -- only fix, verify, and document
- Do NOT modify `state.py` or `schemas.py`
- When fixing test failures, create NEW commits, do NOT amend existing ones

## Checkpoint

All tests pass (both spec-02 and spec-03). `CLAUDE.md` updated. Every item in the Done Criteria checklist from 03-implement.md is verified. Run full suite: `zsh scripts/run-tests-external.sh -n spec03-final tests/`. Check `Docs/Tests/spec03-final.status` for PASSED.
