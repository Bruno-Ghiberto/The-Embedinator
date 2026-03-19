# A1: Pre-Flight Performance Audit

**Agent type**: `quality-engineer`
**Model**: **Opus 4.6** (`model="opus"`)

You are the pre-flight auditor for spec-14. Your job is to verify the exact pre-implementation
state of all 5 target production files before any code changes begin. Your audit report is the
Wave 1 gate — Wave 2 cannot spawn until it is complete and shows PASS.

## Assigned Tasks

T001–T008 from `Docs/PROMPTS/spec-14-performance/14-plan.md` (Wave 1 — Pre-Flight Audit).

| Task | Description |
|------|-------------|
| T001 | Read `specs/014-performance-budgets/spec.md` — confirm 8 FRs, 8 SCs; primary new work is FR-005 (`stage_timings_json`) and FR-008 (traces API extension) |
| T002 | Read `backend/agent/state.py` — confirm `ConversationState` has 13 fields (session_id through iteration_count); confirm `stage_timings: dict` does NOT yet exist |
| T003 | Read `backend/agent/nodes.py` — identify the 7 instrumentation target nodes: `classify_intent`, `rewrite_query`, the node embedding call, the `HybridSearcher.search()` invocation (retrieval), the reranker call (ranking), the LLM generation call (answer_generation), `verify_groundedness` (conditional grounded_verification) |
| T004 | Read `backend/storage/sqlite_db.py` lines 429–461 — confirm `create_query_trace()` has 15 parameters (id through provider_name); confirm `stage_timings_json` parameter is absent; note the INSERT column list |
| T005 | Read `backend/api/chat.py` — confirm `time.monotonic()` already used for `latency_ms`; confirm `stage_timings` is NOT extracted from `final_state`; note exact line where `create_query_trace()` call begins and ends (the `generate()` function starts at approximately line 58) |
| T006 | Read `backend/api/traces.py` lines 75–130 — confirm SELECT does NOT include `stage_timings_json`; note the `parse_json()` helper that already exists; confirm `stage_timings` key is absent from the response dict |
| T007 | Read `tests/integration/test_performance.py` — confirm 2 existing tests (`test_parent_retrieval_latency_target`, `test_search_latency_target`) are present; document the file structure for A4 |
| T008 | Write audit report to `Docs/Tests/spec14-a1-audit.md` with one section per target file, line-level insertion points, and overall PASS/FAIL verdict |

## Source Documents to Read

Read these files in order before starting any work:

1. `Docs/PROMPTS/spec-14-performance/14-plan.md` — full orchestration protocol and Appendix with exact insertion points
2. `specs/014-performance-budgets/spec.md` — 8 FRs and 8 SCs
3. `specs/014-performance-budgets/data-model.md` — complete `query_traces` schema and ConversationState field list
4. `specs/014-performance-budgets/contracts/trace-detail-api.md` — FR-008 API extension contract

## What You Must Do

Use Serena MCP tools (`get_symbols_overview`, `find_symbol` with `include_body=true`) to read code
efficiently. For each target file, confirm the exact pre-FR state.

### 1. backend/agent/state.py

Use `find_symbol` with name_path `ConversationState`, `include_body=true`. Verify:
- The TypedDict contains exactly 13 fields (session_id, messages, query_analysis, sub_answers,
  selected_collections, llm_model, embed_model, intent, final_response, citations,
  groundedness_result, confidence_score, iteration_count)
- The field `stage_timings: dict` does NOT exist
- Note the exact line of the last field (`iteration_count`) — this is A2's insertion point

### 2. backend/agent/nodes.py

Use `get_symbols_overview` to list all node functions. Then use `find_symbol` with `include_body=true`
on each instrumentation target to identify:
- The embedding call location (which node calls query embedding)
- The `HybridSearcher.search()` call location (retrieval node)
- The reranker call location (ranking node)
- The LLM generation call that produces `final_response` (answer_generation node)
- The `verify_groundedness()` function body (conditional grounded_verification)
- Confirm `time` is NOT yet imported at module level (A2 will add it)
- Document the exact function names and approximate lines for each stage

### 3. backend/storage/sqlite_db.py

Use `find_symbol` with name_path `SQLiteDB/create_query_trace`, `include_body=true`. Confirm:
- Method signature ends with `provider_name: str | None = None` — NO `stage_timings_json` parameter
- The INSERT column count (expected: 15)
- Note the exact INSERT statement structure (A3 must extend it)
- Use `find_symbol` for `SQLiteDB/_migrate` or the equivalent migration method to confirm the
  pattern used for adding columns (how `provider_name` or `reasoning_steps_json` were added)

### 4. backend/api/chat.py

Use `find_symbol` with name_path `generate`, `include_body=true`. Confirm:
- `time.monotonic()` is used for `latency_ms` (NOT `perf_counter`)
- `final_state = graph.get_state(config).values` exists
- `stage_timings` is NOT extracted from `final_state`
- The `create_query_trace()` call's last argument ends with `provider_name=provider_name`
- Note the exact line after `final_state` where `latency_ms` is computed (A3's insertion point)

### 5. backend/api/traces.py

Use `find_symbol` with name_path `get_trace`, `include_body=true`. Confirm:
- `stage_timings_json` is NOT in the SELECT column list
- `parse_json()` helper is already imported and used for other fields
- `"stage_timings"` key is absent from the response dict
- Note the last key-value pair in the response dict (A3's insertion point)

### 6. tests/integration/test_performance.py

Read the file. Confirm:
- `test_parent_retrieval_latency_target` exists
- `test_search_latency_target` exists
- No spec-14 tests exist yet (no `test_stage_timings_present`, no `test_concurrent_queries_no_errors`)
- Document the file structure and import pattern for A4

## Output

Write the audit report to `Docs/Tests/spec14-a1-audit.md` using this structure:

```
# Spec-14 Pre-Flight Audit Report
Date: [today's date]

## Summary
Overall Verdict: PASS / FAIL

## Target File 1: backend/agent/state.py
Pre-FR state: CONFIRMED / NOT CONFIRMED
ConversationState field count: [N]
stage_timings field present: NO / YES (⚠️ unexpected)
Insertion point for A2: line [N] (after `iteration_count: int`)

## Target File 2: backend/agent/nodes.py
Pre-FR state: CONFIRMED / NOT CONFIRMED
Node instrumentation targets:
- intent_classification: [function name, line ~N]
- embedding: [function name, line ~N]
- retrieval: [function name, line ~N]
- ranking: [function name, line ~N]
- answer_generation: [function name, line ~N]
- grounded_verification: [function name, line ~N] (conditional)
time module imported: NO / YES (⚠️ unexpected)

## Target File 3: backend/storage/sqlite_db.py
Pre-FR state: CONFIRMED / NOT CONFIRMED
create_query_trace() parameter count: [N] (expected: 15)
stage_timings_json parameter present: NO / YES (⚠️ unexpected)
INSERT column count: [N]
Migration pattern reference: [method name, line ~N]

## Target File 4: backend/api/chat.py
Pre-FR state: CONFIRMED / NOT CONFIRMED
time.monotonic() used for latency_ms: YES
stage_timings extracted from final_state: NO / YES (⚠️ unexpected)
Insertion point for A3: line ~[N] (after final_state line, before create_query_trace)

## Target File 5: backend/api/traces.py
Pre-FR state: CONFIRMED / NOT CONFIRMED
stage_timings_json in SELECT: NO / YES (⚠️ unexpected)
stage_timings in response dict: NO / YES (⚠️ unexpected)
parse_json() helper present: YES
Insertion point for A3: [last key in response dict, line ~N]

## Existing tests/integration/test_performance.py
test_parent_retrieval_latency_target: PRESENT
test_search_latency_target: PRESENT
Spec-14 tests already present: NONE / [list if found]

## Overall Verdict
PASS — all 5 target files confirmed in pre-FR state; all insertion points documented.
```

## Key Constraints

- **NEVER run pytest directly** — use `zsh scripts/run-tests-external.sh -n <name> <target>`
- **Read-only audit** — do NOT modify any production or test files
- **Use Serena MCP** for all code reading (`find_symbol`, `get_symbols_overview`)
- **Pre-existing baseline**: 39 failures (established in spec-13) — do NOT run a full test suite
  during audit (it takes time and is not needed for the gate condition)
- **If insertion points differ** from the plan appendix: document the discrepancy in detail so
  A2 and A3 can adjust — do NOT attempt to fix them yourself

## Success Criteria

- Audit report written to `Docs/Tests/spec14-a1-audit.md`
- All 5 target files confirmed in pre-FR state (no spec-14 changes already applied)
- Line-level insertion points documented for A2 and A3
- `stage_timings_json` column confirmed absent from `create_query_trace()` signature
- `ConversationState` confirmed to have no `stage_timings` field
- Overall verdict is PASS

## After Completing All Tasks

Report completion to the orchestrator. The orchestrator will read your audit report at
`Docs/Tests/spec14-a1-audit.md` and verify the PASS verdict before spawning Wave 2 agents.
