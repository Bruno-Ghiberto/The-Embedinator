# Spec 03: ResearchGraph — Specify Prompt Coherence Review

## Status
- **03-specify.md**: Reviewed and fixed — 7 issues corrected
- **Next step**: `/speckit.specify` (Step 2 of workflow)

## Fixes Applied
1. `fan_out` node → `route_fan_out()` edge function (spec-02 design deviation)
2. Removed `tiktoken` dependency — use `count_tokens_approximately` from langchain_core
3. Node signatures: `*, llm: BaseChatModel` → `config: RunnableConfig`, return `dict` (LangGraph convention)
4. Added confidence computation rule: measurable retrieval signals, NOT LLM self-assessment
5. Added SubAnswer scale conversion note: `float` (0.0–1.0) → `int` (0–100)
6. Python 3.14 type hints: `list[str]`, `str | None` instead of `List[str]`, `Optional[str]`
7. Noted Send() target node name is `"research"`

## Key Findings for Future Specs
- Spec-02 design deviations (route_after_rewrite combining should_clarify + route_fan_out, dead fan_out stub) propagate as incoherencies in downstream spec prompts
- All pre-written context prompts use old typing style — will need fixing in each spec
- Node signature pattern must use `(state, config: RunnableConfig) -> dict`, not `(state, *, llm: BaseChatModel) -> State`
- tiktoken was listed as a dep in original prompts but spec-02 research rejected it
