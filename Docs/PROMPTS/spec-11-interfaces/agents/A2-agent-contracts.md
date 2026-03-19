# Agent A2: Agent Layer Contract Tests

## Agent: python-expert | Model: sonnet | Wave: 2

## Role

You are a Wave 2 agent for spec-11. You write `tests/unit/test_contracts_agent.py`,
covering state schemas, 20 node functions, 7 edge functions, the tool factory, 3 graph
builders, and confidence scoring. You run in PARALLEL with A3 (who writes storage and
retrieval tests). You have no file conflicts with A3.

---

## Assigned Tasks

**T013** -- Create `tests/unit/test_contracts_agent.py` with imports and test structure.
Import `inspect`, `typing`, all node/edge modules.

**T014** -- Write state schema field tests (FR-001, FR-002): verify `ConversationState`
has 12 fields, `ResearchState` has 16 fields (including `_no_new_tools`,
`_needs_compression`), `MetaReasoningState` has 11 fields (including
`attempted_strategies`). Verify dual confidence scale (int vs float) using Pattern 6.

**T015** -- Write ConversationGraph node signature tests (FR-003, FR-004): verify all
11 nodes in `backend/agent/nodes.py`:
- `classify_intent` -- `*, llm: Any` (KEYWORD_ONLY)
- `rewrite_query` -- `*, llm: Any` (KEYWORD_ONLY)
- `verify_groundedness` -- `*, llm: Any = None` (KEYWORD_ONLY, with default)
- `validate_citations` -- `*, reranker: Any = None` (KEYWORD_ONLY, with default)
- `init_session`, `fan_out`, `aggregate_answers`, `summarize_history`, `format_response`,
  `handle_collection_mgmt` -- `**kwargs` (VAR_KEYWORD)
- `request_clarification` -- no DI (only `state` param)

**T016** -- Write ResearchGraph node signature tests (FR-007): verify all 5 nodes in
`backend/agent/research_nodes.py`:
- `orchestrator`, `tools_node`, `compress_context`, `collect_answer` have
  `config: RunnableConfig = None`
- `fallback_response` -- check its actual params

**T017** -- Write MetaReasoningGraph node signature tests (FR-007): verify all 4 nodes
in `backend/agent/meta_reasoning_nodes.py` (NOT `nodes.py`):
- `generate_alternative_queries`, `evaluate_retrieval_quality`, `decide_strategy`,
  `report_uncertainty` -- all have `config` param

**T018** -- Write edge function tests (FR-005): verify 7 functions across 3 files:
- `edges.py`: `route_intent`, `should_clarify`, `route_after_rewrite`, `route_fan_out`
- `research_edges.py`: `should_continue_loop`, `route_after_compress_check`
- `meta_reasoning_edges.py`: `route_after_strategy`

**T019** -- Write tool factory tests (FR-006): verify `create_research_tools` in
`backend/agent/tools.py` has params `["searcher", "reranker", "parent_store"]` and
returns `list`.

**T020** -- Write graph builder tests (FR-019): verify `build_conversation_graph`
in `conversation_graph.py`, `build_research_graph` in `research_graph.py`,
`build_meta_reasoning_graph` in `meta_reasoning_graph.py` exist and are callable.

**T021** -- Write confidence scoring tests (FR-002): verify `compute_confidence` exists
in `backend/agent/confidence.py`.

**T022** -- Run agent contract tests and fix any failures.

---

## Output File

Write ALL tests into a single file: `tests/unit/test_contracts_agent.py`

---

## Key Technical Facts

These facts override anything in the old `11-implement.md`:

1. **3 DI patterns** exist across conversation nodes -- not all are keyword-only:
   - Pattern A: `def node(state, *, llm: Any)` -- KEYWORD_ONLY after `*`
   - Pattern B: `def node(state, **kwargs)` -- VAR_KEYWORD
   - Pattern C: `def node(state)` -- no DI at all
   Check `inspect.Parameter.KEYWORD_ONLY` and `inspect.Parameter.VAR_KEYWORD`.

2. **All nodes return `dict`**, not full State TypedDicts. Do not assert return annotation
   is `ConversationState` -- it is `dict` (or may lack annotation).

3. **`llm` type is `Any`** (from `typing`), not `BaseChatModel`.

4. **MetaReasoningGraph nodes are in `meta_reasoning_nodes.py`** -- a separate file from
   `nodes.py` and `research_nodes.py`.

5. **ResearchGraph/MetaReasoningGraph nodes use `config: RunnableConfig = None`** -- this is
   POSITIONAL_OR_KEYWORD with a default of `None`, NOT keyword-only.

6. **`route_fan_out`** is the edge function that performs `Send()` dispatch -- the `fan_out`
   node in `nodes.py` is a dead stub.

7. **Dual confidence scale**: `ConversationState.confidence_score` is `int` (0-100).
   `ResearchState.confidence_score` is `float` (0.0-1.0). Use `typing.get_type_hints()`.

---

## Test Patterns to Use

- **Pattern 1** (Function Signature): For all node/edge functions
- **Pattern 6** (Dual Confidence Scale): For state schemas
- **Pattern 2** (Method Existence): For graph builder functions

---

## Testing Rule (MANDATORY)

```
NEVER run pytest directly inside Claude Code. Use ONLY:
  zsh scripts/run-tests-external.sh -n contracts-agent tests/unit/test_contracts_agent.py

Poll: cat Docs/Tests/contracts-agent.status     (RUNNING | PASSED | FAILED | ERROR)
Read: cat Docs/Tests/contracts-agent.summary    (~20 lines, token-efficient)
Full: cat Docs/Tests/contracts-agent.log
```

---

## Gate Check

After completing T013-T022:

1. Run: `zsh scripts/run-tests-external.sh -n contracts-agent tests/unit/test_contracts_agent.py`
2. Poll `Docs/Tests/contracts-agent.status` until PASSED or FAILED
3. If FAILED, read the summary, fix the test, and re-run
4. When PASSED, notify the Orchestrator that A2 is complete
