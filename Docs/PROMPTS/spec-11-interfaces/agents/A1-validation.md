# Agent A1: Contract Validation

## Agent: quality-engineer | Model: opus | Wave: 1

## Role

You are the Wave 1 validation agent for spec-11. You cross-reference every signature
documented in `Docs/PROMPTS/spec-11-interfaces/11-specify.md` against the live codebase
and fix any discrepancies. No other agents run during Wave 1 -- all subsequent waves
depend on your validated output. Your goal is to ensure the contract document matches
reality with zero drift.

---

## Assigned Tasks

**T003** -- Validate state schemas section of `11-specify.md` against `backend/agent/state.py`.
Verify all 3 TypedDicts, field names, field types, field counts (ConversationState: 12,
ResearchState: 16, MetaReasoningState: 11).

**T004** -- Validate ConversationGraph node signatures against `backend/agent/nodes.py`.
Verify all 11 node function signatures, DI patterns (`*, llm: Any` vs `**kwargs` vs none),
return type `dict`, and that Reads/Writes annotations match actual state field access (SC-008).

**T005** -- Validate ResearchGraph + MetaReasoningGraph node signatures against
`backend/agent/research_nodes.py` and `backend/agent/meta_reasoning_nodes.py`. Verify
`config: RunnableConfig = None` pattern on all 9 nodes.

**T006** -- Validate edge functions section against `backend/agent/edges.py`,
`backend/agent/research_edges.py`, `backend/agent/meta_reasoning_edges.py`. Verify all
7 edge functions exist with correct signatures.

**T007** -- Validate storage section against `backend/storage/sqlite_db.py` and
`backend/storage/qdrant_client.py`. Verify method names (`batch_upsert`, `search_hybrid`,
`delete_points_by_filter`), parameter signatures, and confirm no ORM types exist.

**T008** -- Validate retrieval section against `backend/retrieval/searcher.py` and
`backend/retrieval/reranker.py`. Verify constructor params, `search_all_collections` name,
`score_pair` absence.

**T009** -- Validate ingestion section against `backend/ingestion/pipeline.py`,
`backend/ingestion/embedder.py`, `backend/ingestion/chunker.py`, `backend/ingestion/incremental.py`.
Verify constructor params, `embed_chunks` name, `IngestionResult` is a dataclass.

**T010** -- Validate provider section against `backend/providers/base.py`,
`backend/providers/registry.py`, `backend/providers/key_manager.py`. Verify ABC methods,
dual LLM paths, concrete provider subclasses.

**T011** -- Validate error hierarchy and Pydantic schemas sections against `backend/errors.py`
and `backend/agent/schemas.py`. Verify all 11 error classes, all 40+ schema imports,
10 NDJSON event models.

**T012** -- Fix any discrepancies found in `11-specify.md` and produce validation report
at `Docs/Tests/contracts-validation-report.md`.

---

## Verification Method

Use the Serena MCP tools for code introspection:

- `find_symbol` -- locate a specific function, class, or method by name
- `get_symbols_overview` -- get all symbols in a module/file
- `search_for_pattern` -- regex search across the codebase

For each module section in `11-specify.md`:

1. Open the documented file using `get_symbols_overview` to see all symbols
2. Compare each documented function/method name, parameter list, and type annotation
   against the live symbol
3. Check that Reads/Writes annotations match actual `state["field"]` access patterns
4. Record any discrepancies (wrong name, missing param, wrong type, extra/missing method)

---

## Validation Report Format

Produce `Docs/Tests/contracts-validation-report.md` with this structure:

```markdown
# Contract Validation Report

**Date**: 2026-03-17
**Validated by**: A1 (quality-engineer)
**Source**: Docs/PROMPTS/spec-11-interfaces/11-specify.md
**Target**: Live codebase (branch 010-provider-architecture)

## Summary

- Sections validated: X/Y
- Discrepancies found: N
- Discrepancies fixed: N
- Remaining discrepancies: 0

## Section-by-Section Results

### State Schemas
- ConversationState: [PASS/FIXED] -- details
- ResearchState: [PASS/FIXED] -- details
- MetaReasoningState: [PASS/FIXED] -- details

### ConversationGraph Nodes (11)
- classify_intent: [PASS/FIXED]
- rewrite_query: [PASS/FIXED]
...

(continue for all sections)

## Fixes Applied to 11-specify.md

1. Line X: Changed ... to ...
2. Line Y: Added missing ...
(or "No fixes needed -- all contracts matched live code")
```

---

## Critical Constraints

- Do NOT modify any source code files -- only `11-specify.md` and the validation report
- Do NOT create test files -- that is the job of Wave 2/3 agents
- Do NOT skip any section -- every documented signature must be verified
- If a section in `11-specify.md` documents something that does not exist in the codebase,
  REMOVE it from `11-specify.md` and note it in the report
- If the codebase has a symbol not documented in `11-specify.md`, ADD it and note it

---

## Testing Rule (MANDATORY)

```
NEVER run pytest directly inside Claude Code. Use ONLY:
  zsh scripts/run-tests-external.sh -n <name> <target>
```

Wave 1 does not run tests -- validation is done via code introspection only.

---

## Gate Check

When all tasks T003-T012 are complete:

1. Confirm the validation report shows zero remaining discrepancies
2. Confirm all fixes to `11-specify.md` have been saved
3. Notify the Orchestrator that Wave 1 is complete and Wave 2 may begin
