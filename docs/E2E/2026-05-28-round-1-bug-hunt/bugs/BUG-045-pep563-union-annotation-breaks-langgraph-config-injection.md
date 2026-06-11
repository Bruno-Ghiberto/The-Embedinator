# BUG-045: PEP 563 union annotation breaks LangGraph config injection

- **Severity**: BLOCKER
- **Layer**: Backend
- **Discovered**: 2026-06-11T12:55:00Z in Phase 2 (P2-S2)
- **Phase scenario**: P2-S2
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Run the stack on the post-3a5fe6b image (mypy cleanup merged via a1594c7).
2. Open chat, select ANY collection (reproduced on hunt-pdfs AND pre-existing nag-corpus-bm25), send any message.
3. Observe NDJSON: {"type":"session",...} then {"type":"error","message":"Unable to process your request. Please retry.","code":"SERVICE_UNAVAILABLE"} within ~0.15s (trace_ids 2ca0a881-831b-49d7-81d8-d47e2e51593d, 692e7bb2-8541-4e1a-a1d1-e2e91f1161c2).
4. Backend startup logs show build-time UserWarning "The 'config' parameter should be typed as 'RunnableConfig'..." at conversation_graph.py:53/54/62 + research_graph.py:49/52/54/55.
5. Runtime logs: agent_classify_intent_failed error=AttributeError, then http_chat_stream_error detail="'NoneType' object has no attribute 'with_structured_output'" (nodes.py:214).

## Expected
Chat streams an answer; LangGraph injects config["configurable"]["llm"] (set correctly by chat.py:182) into every node.

## Actual
Commit 3a5fe6b changed node signatures to `config: RunnableConfig | None = None`; under `from __future__ import annotations` (nodes.py:7, PEP 563) the annotation stringifies to "RunnableConfig | None", which LangGraph 1.2.4's special-parameter detection cannot resolve → config NOT injected → llm=None at nodes.py:171 → AttributeError → 100% of chats fail (5/5 since the 12:12Z restart loaded post-merge code; zero succeeded). Ollama never called (only /api/tags health polling); no query_traces row written. Container restart does NOT fix it.

Since-when evidence: last successful query_traces row 2026-05-05T20:24:58Z (981 rows, all pre-regression); chat globally broken since merge a1594c7 on 2026-06-10. Backend lifespan init is CLEAN (all 12 components, provider_providers_initialized + agent_graphs_compiled at 12:11:53Z). No LLM/Ollama circuit-breaker events ever — CB not involved.

## Artifacts
- Screenshot: screenshots/BUG-045-chat-error.png (gitignored)
- Log excerpt: logs/BUG-045-P2-S2-chat-backend.log (gitignored)
- Log excerpt: logs/BUG-045-startup-clean.log (gitignored)
- Trace: null

## Root-cause hypothesis
PEP 563 + framework reflection incompatibility — LangGraph resolves the bare annotation string "RunnableConfig" but not the union string "RunnableConfig | None"; mypy-correct code is runtime-broken. Hypotheses registry-init-failure and swallowed-exception were investigated and REFUTED (lifespan completed; get_active_langchain_model has no None path). Root-caused by on-demand Opus investigator, HIGH confidence.

CONFIRMED (dual-source): log-analyst independently confirmed by reading LangGraph source — langgraph/_internal/_runnable.py:147 KWARGS_CONFIG_KEYS accepts RunnableConfig, "RunnableConfig", Optional[RunnableConfig], "Optional[RunnableConfig]", or unannotated; the pipe-union form `RunnableConfig | None` is NOT in the list → add_node() emits the UserWarning and skips config injection (continue path). Affected signatures: classify_intent (~nodes.py:163), rewrite_query (~:249), verify_groundedness (~:494) + the research_nodes.py nodes flagged by research_graph.py:49/52/54/55 warnings. Registry live-verified in-container: get_active_langchain_model returns a working ChatOllama(model=qwen2.5:7b) whose with_structured_output works — the object simply never reaches the nodes.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: TBD
- **GitHub issue**: TBD
- **Rationale**: TBD

## Notes
BLOCKER-PATCHED gate evaluated and NOT FIRED — fix fails the zero-risk bar (removing future-annotations changes file-wide annotation semantics across nodes.py/research_nodes.py/meta_reasoning_nodes.py, needs forward-ref scan + image REBUILD + chat smoke test). Pilot path-1 decision: P2 continues S4-S6 (ingestion-only); supervised out-of-hunt fix after verify-2, before apply-3. CI gap: backend-test green on broken chat — no test exercises config injection through a compiled graph.

PREFERRED FIX: change the signatures to `config: Optional[RunnableConfig] = None` (+ `from typing import Optional` where missing) in backend/agent/nodes.py + research_nodes.py (+ meta_reasoning_nodes.py if same pattern; currently disabled). This form is BOTH mypy-clean (keeps PR #100's blocking gate green) AND in LangGraph's KWARGS_CONFIG_KEYS accept-list — no need to touch `from __future__ import annotations`. CORRECTION (Lead-verified): running container has NO source bind-mount (only data/ → /data) — fix requires image REBUILD + restart + chat smoke test; `docker compose restart` alone will NOT pick up source edits (analyst's no-rebuild claim was dev-compose-only). Verification signal post-fix: startup log clean of UserWarnings at conversation_graph.py:53/54/62 + research_graph.py:49/52/54/55, then one successful chat (first Ollama inference call since 2026-06-10).
