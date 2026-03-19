# Spec 05: Accuracy, Precision & Robustness -- Implementation Context

> **READ THIS SECTION FIRST. Do not skip ahead to code specifications.**

## Agent Team Orchestration Protocol

> **MANDATORY**: Agent Teams is REQUIRED for this spec. You MUST be running
> inside tmux. Agent Teams auto-detects tmux and spawns each teammate in its
> own split pane (the default `"auto"` teammateMode).
>
> **Enable**: Set `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in `~/.claude/settings.json`:
> ```json
> {
>   "env": { "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1" }
> }
> ```
>
> **tmux multi-pane spawning is REQUIRED.** Each agent gets its own tmux pane
> for real-time visibility. Do NOT run agents sequentially in a single pane.

### Architecture

The **lead session** (you, the orchestrator) coordinates all work via Claude Code Agent Teams:

| Component | Role |
|-----------|------|
| **Lead** | Creates team, creates tasks with dependencies, spawns teammates, runs checkpoint gates, synthesizes results |
| **Teammates** | Independent Claude Code instances, each in its own tmux pane, executing assigned tasks |
| **Task List** | Shared task list with dependency tracking -- teammates self-claim unblocked tasks |
| **Mailbox** | Inter-agent messaging for status updates and checkpoint coordination |

### Wave Execution Order

```
Wave 1 (A1):           Foundation + VERIFY_PROMPT    -> Checkpoint Gate
Wave 2 (A2 + A3 + A4): Nodes (parallel)              -> Checkpoint Gate
Wave 3 (A5 + A6 + A7): CB + Metadata + Integration   -> Checkpoint Gate
Wave 4 (A1):           Polish + full regression       -> Checkpoint Gate
```

### Step 1: Create the Team

```
Create an agent team called "spec05-accuracy" to implement the Accuracy,
Precision & Robustness feature.
```

The lead creates the team. All teammates will appear in their own tmux panes automatically.

### Step 2: Create Tasks with Dependencies

Create tasks in the shared task list so teammates can self-claim. Tasks encode the wave dependency chain:

```
Create the following tasks for the team:

Wave 1 -- Foundation:
- T001-T007: Audit stubs, test scaffolding, VERIFY_PROMPT, settings verification (assign to A1)

Wave 2 -- Nodes (parallel, after Wave 1 completes):
- T008-T012: verify_groundedness + _apply_groundedness_annotations + US1 tests (assign to A2, depends on Wave 1)
- T013-T017: validate_citations + _extract_claim_for_citation + US2 tests (assign to A3, depends on Wave 1)
- T022-T025: TIER_PARAMS + rewrite_query extension + US4 tests (assign to A4, depends on Wave 1)

Wave 3 -- CB + Metadata + Integration (after Wave 2 completes):
- T027-T034, T044-T047: QdrantClient + inference circuit breakers + error handling + US6 tests (assign to A5, depends on Wave 2)
- T018-T021: NDJSON metadata frame + US3 tests (assign to A6, depends on Wave 2)
- T035-T039: Integration tests (assign to A7, depends on A5 + A6)

Wave 4 -- Polish (after Wave 3 completes):
- T040-T043, T048-T049: Full regression + ruff + contract validation + perf micro-tests (lead or A1)
```

### Step 3: Spawn Teammates per Wave

**Wave 1 -- Spawn A1 (Foundation):**
```
Spawn a teammate named "A1-setup-foundations" with model Sonnet.
Prompt: "Read your instruction file at Docs/PROMPTS/spec-05-accuracy/agents/A1-setup-foundations.md FIRST, then execute all assigned tasks."
```

Wait for A1 to complete. Run checkpoint gate (see below). Then proceed to Wave 2.

**Wave 2 -- Spawn A2 + A3 + A4 (parallel, each in own tmux pane):**
```
Spawn three teammates in parallel:

1. Teammate "A2-verify-groundedness" with model Opus:
   "Read your instruction file at Docs/PROMPTS/spec-05-accuracy/agents/A2-verify-groundedness.md FIRST, then execute all assigned tasks."

2. Teammate "A3-validate-citations" with model Sonnet:
   "Read your instruction file at Docs/PROMPTS/spec-05-accuracy/agents/A3-validate-citations.md FIRST, then execute all assigned tasks."

3. Teammate "A4-tier-params-rewrite" with model Sonnet:
   "Read your instruction file at Docs/PROMPTS/spec-05-accuracy/agents/A4-tier-params-rewrite.md FIRST, then execute all assigned tasks."
```

Wait for all three to complete. Run checkpoint gate. Then proceed to Wave 3.

**Wave 3 -- Spawn A5 + A6 (parallel), then A7 (after A5+A6):**
```
Spawn two teammates in parallel:

1. Teammate "A5-circuit-breakers" with model Opus:
   "Read your instruction file at Docs/PROMPTS/spec-05-accuracy/agents/A5-circuit-breakers.md FIRST, then execute all assigned tasks."

2. Teammate "A6-ndjson-metadata" with model Sonnet:
   "Read your instruction file at Docs/PROMPTS/spec-05-accuracy/agents/A6-ndjson-metadata.md FIRST, then execute all assigned tasks."
```

Wait for both A5 and A6. Run checkpoint gate. Then spawn A7:

```
Spawn a teammate named "A7-integration-tests" with model Sonnet.
Prompt: "Read your instruction file at Docs/PROMPTS/spec-05-accuracy/agents/A7-integration-tests.md FIRST, then execute all assigned tasks."
```

Wait for A7. Run checkpoint gate. Then proceed to Wave 4.

**Wave 4 -- Lead or A1 (Polish):**
```
Spawn a teammate named "A1-polish" with model Sonnet.
Prompt: "Read your instruction file at Docs/PROMPTS/spec-05-accuracy/agents/A1-setup-foundations.md FIRST, then execute Wave 4 tasks (T040-T043, T048-T049)."
```

### Step 4: Checkpoint Gates (Lead Runs After Each Wave)

The lead runs these verification commands after each wave completes. If a gate fails, message the relevant teammate to fix it before proceeding.

```bash
# Wave 1: Foundation ready
python -c "from backend.agent.prompts import VERIFY_PROMPT; print('VERIFY_PROMPT OK')"
python -c "from backend.config import settings; print(settings.groundedness_check_enabled, settings.citation_alignment_threshold, settings.circuit_breaker_failure_threshold)"
python -c "import tests.unit.test_accuracy_nodes; print('unit test file OK')"
python -c "import tests.integration.test_accuracy_integration; print('integration test file OK')"
ruff check .

# Wave 2: All node implementations importable + tests
python -c "from backend.agent.nodes import verify_groundedness, validate_citations, rewrite_query, TIER_PARAMS; print('nodes OK, tiers:', list(TIER_PARAMS.keys()))"
ruff check backend/agent/nodes.py backend/agent/prompts.py

# Wave 3: Circuit breakers + metadata + integration tests
python -c "from backend.storage.qdrant_client import QdrantClientWrapper; q = QdrantClientWrapper('x', 0); print('CB fields:', hasattr(q, '_last_failure_time'), hasattr(q, '_cooldown_secs'))"
python -c "import tests.integration.test_accuracy_integration; print('integration tests OK')"
ruff check backend/storage/qdrant_client.py backend/api/chat.py backend/agent/nodes.py

# Wave 4: Full test suite
zsh scripts/run-tests-external.sh -n spec05-full tests/
cat Docs/Tests/spec05-full.status
cat Docs/Tests/spec05-full.summary
```

### Step 5: Shutdown and Cleanup

After all waves complete and checkpoint gates pass:

```
Ask all teammates to shut down, then clean up the team.
```

This removes the shared team resources. Always shut down teammates before cleanup.

### Orchestration Rules

1. **Never skip checkpoint gates** -- a failed gate means the next wave's teammates will build on broken code.
2. **Use SendMessage for steering** -- if a teammate is going off-track, message them directly in their tmux pane or via the lead's messaging system.
3. **Parallel waves share files safely** -- A2, A3, A4 each modify different functions in `nodes.py`. A5 and A6 modify different sections of `chat.py`. No merge conflicts if agents stay in their assigned regions.
4. **Teammate prompts are minimal** -- just point to the instruction file. All context lives in the instruction files and CLAUDE.md.
5. **Model selection** -- A2 (GAV node, complex LLM structured output + annotation logic) and A5 (circuit breakers, state machine + retry + error handling) use Opus. All others use Sonnet for cost efficiency.
6. **Monitor via tmux** -- click into any teammate's pane to see their progress.
7. **If a teammate fails** -- shut it down and spawn a replacement with the same instruction file. The task list tracks which tasks are done.
8. **Never inline spec content in spawn prompts** -- agents MUST read their instruction file FIRST. All authoritative context lives in the instruction files and spec artifacts.

---

## Implementation Scope

### Files to Modify

| File | Action | Agent | Purpose |
|------|--------|-------|---------|
| `backend/agent/nodes.py` | Modify | A2, A3, A4, A5 | Implement verify_groundedness + validate_citations stubs, add TIER_PARAMS, extend rewrite_query, add inference CB |
| `backend/agent/prompts.py` | Modify | A1 | Add `VERIFY_PROMPT` constant |
| `backend/storage/qdrant_client.py` | Modify | A5 | Standardize circuit breaker (half-open + cooldown), add Tenacity retry |
| `backend/api/chat.py` | Modify | A5, A6 | A5: catch CircuitOpenError + emit error frame; A6: add groundedness to metadata frame |
| `tests/unit/test_accuracy_nodes.py` | Create | A1 (scaffold), A2-A6 (tests) | All unit tests |
| `tests/integration/test_accuracy_integration.py` | Create | A1 (scaffold), A7 (tests) | Integration tests |

### Files That Exist and Are NOT Modified (Verified via Serena)

- `backend/agent/schemas.py` -- `ClaimVerification` (lines 47-51), `GroundednessResult` (lines 54-57), `QueryAnalysis` (lines 15-22) already exist with correct fields. DO NOT MODIFY.
- `backend/agent/conversation_graph.py` -- `verify_groundedness` and `validate_citations` stubs are already wired into the graph. DO NOT MODIFY.
- `backend/agent/confidence.py` -- spec-03 R8 5-signal formula. DO NOT TOUCH.
- `backend/agent/state.py` -- `ConversationState` already has `groundedness_result: GroundednessResult | None` and `confidence_score: int`. No new fields needed.
- `backend/config.py` -- All accuracy/robustness settings already exist (lines 53-58). DO NOT ADD new fields.
- `backend/agent/research_nodes.py` -- Reads unchanged.
- `backend/ingestion/embedder.py` -- DOES NOT EXIST. Deferred to spec-06. DO NOT CREATE.

---

## Codebase Verification (Verified via Serena MCP)

These facts were verified against the live codebase. Agents MUST respect them.

1. **verify_groundedness stub** at `nodes.py:354-357`: `async def verify_groundedness(state: ConversationState, *, llm: Any = None) -> dict:` returns `{"groundedness_result": None}`. Uses `*, llm` keyword arg pattern.
2. **validate_citations stub** at `nodes.py:360-363`: `async def validate_citations(state: ConversationState, *, reranker: Any = None) -> dict:` returns `{"citations": state["citations"]}`. Uses `*, reranker` keyword arg pattern.
3. **rewrite_query** at `nodes.py:160-243`: `async def rewrite_query(state: ConversationState, *, llm: Any) -> dict:` -- existing implementation with retry + fallback logic. A4 extends this, does NOT rewrite it.
4. **ConversationState** at `state.py:16-29`: has `groundedness_result: GroundednessResult | None`, `confidence_score: int` (0-100), `citations: list[Citation]`, `sub_answers: list[SubAnswer]`, `final_response: str | None`.
5. **SubAnswer** at `schemas.py:95-100`: has `confidence_score: int = Field(ge=0, le=100)` and `chunks: list[RetrievedChunk]`.
6. **Citation** at `schemas.py:82-92`: has `passage_id`, `document_id`, `document_name`, `text`, `relevance_score`, `source_removed`.
7. **ClaimVerification** at `schemas.py:47-51`: `claim: str`, `verdict: Literal["supported","unsupported","contradicted"]`, `evidence_chunk_id: str | None`, `explanation: str`.
8. **GroundednessResult** at `schemas.py:54-57`: `verifications: list[ClaimVerification]`, `overall_grounded: bool`, `confidence_adjustment: float`.
9. **QueryAnalysis** at `schemas.py:15-22`: has `complexity_tier: Literal["factoid","lookup","comparison","analytical","multi_hop"]`.
10. **Settings** at `config.py:53-58`: `groundedness_check_enabled: bool = True`, `citation_alignment_threshold: float = 0.3`, `circuit_breaker_failure_threshold: int = 5`, `circuit_breaker_cooldown_secs: int = 30`, `retry_max_attempts: int = 3`, `retry_backoff_initial_secs: float = 1.0`. ALL EXIST -- do not add.
11. **QdrantClientWrapper** at `qdrant_client.py:13-104`: has `_circuit_open`, `_failure_count`, `_max_failures` but MISSING `_last_failure_time` and `_cooldown_secs`. Has rudimentary CB in `search()` and `health_check()` but NO half-open/cooldown logic. A5 standardizes this.
12. **HybridSearcher** CB pattern at `searcher.py:47-63`: `_check_circuit` (raise if open), `_record_success` (reset count + close), `_record_failure` (increment + open at threshold). Simple consecutive-count, NO half-open. Spec-05 extends QdrantClientWrapper with FULL half-open + cooldown per ADR-001.
13. **chat.py metadata frame** at `chat.py:149-156`: currently emits `{type: "metadata", trace_id, confidence, citations, latency_ms}`. Does NOT include `groundedness`. A6 adds it.
14. **Existing prompts** in `prompts.py`: `VERIFY_GROUNDEDNESS_SYSTEM` exists (line 10 area) as an early constant. `VERIFY_PROMPT` is the NEW constant A1 adds -- this is the full GAV prompt with `{context}` and `{answer}` placeholders.
15. **format_response** at `nodes.py:413-477`: already handles `groundedness_result is not None` case with a Phase 2 comment. GAV annotations now happen in `verify_groundedness` itself (via `_apply_groundedness_annotations`), not in `format_response`.

---

## Code Specifications

### Critical Patterns (ALL Nodes MUST Follow)

```python
# nodes.py uses keyword-arg injection pattern (NOT config DI)
async def node_name(state: ConversationState, *, llm: Any = None) -> dict:
    # Import settings at module level
    from backend.config import settings

# Return partial dict, NOT {**state, ...}
return {"field_a": value_a, "field_b": value_b}

# structlog pattern
logger = structlog.get_logger(__name__)
```

> **IMPORTANT**: `nodes.py` uses `*, llm` / `*, reranker` keyword-arg injection.
> This is different from `research_nodes.py` which uses `config: RunnableConfig = None`.
> Follow the established `nodes.py` pattern.

---

### backend/agent/prompts.py (MODIFY -- add VERIFY_PROMPT)

Add `VERIFY_PROMPT` as a new constant. This is the system prompt for the GAV LLM call. It instructs the LLM to evaluate ALL claims in the answer against the retrieved context in a single call and return structured `GroundednessResult` output.

```python
VERIFY_PROMPT = """You are a claim verification assistant. Given ONLY the retrieved
context below, evaluate every factual claim in the proposed answer.

For each distinct factual claim in the answer, classify it as:
- SUPPORTED: the retrieved context contains direct evidence for this claim
- UNSUPPORTED: no evidence for this claim exists in the retrieved context
- CONTRADICTED: the retrieved context directly contradicts this claim

For each claim, provide:
1. The exact claim text as it appears in the answer
2. Your verdict (supported / unsupported / contradicted)
3. The chunk ID of the evidence (if supported or contradicted), or null if unsupported
4. A brief explanation of your reasoning

Also compute:
- overall_grounded: True if >= 50% of claims are SUPPORTED
- confidence_adjustment: a float between 0.0 and 1.0 representing
  (supported_count / max(total_claims, 1)). A fully grounded answer
  has confidence_adjustment = 1.0; an answer with no supported claims
  has confidence_adjustment = 0.0.

Retrieved Context:
{context}

Proposed Answer:
{answer}"""
```

---

### backend/agent/nodes.py -- TIER_PARAMS constant (A4)

Add as a module-level constant, after existing constants:

```python
TIER_PARAMS: dict[str, dict] = {
    "factoid":    {"top_k": 5,  "max_iterations": 3,  "max_tool_calls": 3, "confidence_threshold": 0.7},
    "lookup":     {"top_k": 10, "max_iterations": 5,  "max_tool_calls": 5, "confidence_threshold": 0.6},
    "comparison": {"top_k": 15, "max_iterations": 7,  "max_tool_calls": 6, "confidence_threshold": 0.55},
    "analytical": {"top_k": 25, "max_iterations": 10, "max_tool_calls": 8, "confidence_threshold": 0.5},
    "multi_hop":  {"top_k": 30, "max_iterations": 10, "max_tool_calls": 8, "confidence_threshold": 0.45},
}
```

---

### backend/agent/nodes.py -- rewrite_query extension (A4)

Extend the existing `rewrite_query` function. After each successful `analysis = await structured_llm.ainvoke(messages)` return, add the tier lookup:

```python
# EXISTING CODE (keep as-is):
analysis = await structured_llm.ainvoke(messages)
log.info(
    "query_analyzed",
    is_clear=analysis.is_clear,
    sub_questions=len(analysis.sub_questions),
    complexity=analysis.complexity_tier,
)
# NEW: look up tier params for downstream Send() config
tier_params = TIER_PARAMS.get(analysis.complexity_tier, TIER_PARAMS["lookup"])
return {"query_analysis": analysis, "retrieval_params": tier_params}
```

Apply the same pattern to all three return points in `rewrite_query` (first attempt, retry, fallback). The fallback `QueryAnalysis` uses `complexity_tier="lookup"` so `TIER_PARAMS["lookup"]` is the correct default.

---

### backend/agent/nodes.py -- _apply_groundedness_annotations helper (A2)

```python
def _apply_groundedness_annotations(response: str, result: GroundednessResult) -> str:
    """Annotate unsupported claims and remove contradicted claims.

    - UNSUPPORTED claims: append [unverified] to the claim text
    - CONTRADICTED claims: remove claim text, append brief explanation
    - >50% unsupported: prepend warning banner
    """
    annotated = response

    notes: list[str] = []
    for v in result.verifications:
        if v.verdict == "unsupported":
            annotated = annotated.replace(v.claim, f"{v.claim} [unverified]", 1)
        elif v.verdict == "contradicted":
            annotated = annotated.replace(v.claim, "", 1)
            notes.append(f"Removed contradicted claim: {v.explanation}")

    if not result.overall_grounded:
        banner = (
            "**Warning**: Insufficient evidence for most claims in this answer. "
            "Please verify the information independently.\n\n"
        )
        annotated = banner + annotated

    if notes:
        annotated += "\n\n---\n" + "\n".join(notes)

    return annotated
```

---

### backend/agent/nodes.py -- verify_groundedness implementation (A2)

Replace the stub at lines 354-357:

```python
async def verify_groundedness(state: ConversationState, *, llm: Any = None) -> dict:
    """Grounded Answer Verification -- evaluate claims against retrieved context.

    (1) Guard on settings.groundedness_check_enabled
    (2) Build context string from state["sub_answers"] chunk texts
    (3) Low-temperature llm.with_structured_output(GroundednessResult) call
    (4) Call _apply_groundedness_annotations
    (5) Compute GAV-adjusted confidence: int(mean(sub_scores) * confidence_adjustment)
    (6) Return partial dict
    (7) Catch all exceptions -> graceful degradation
    """
    from backend.agent.prompts import VERIFY_PROMPT
    from backend.agent.schemas import GroundednessResult
    from backend.config import settings

    log = logger.bind(session_id=state["session_id"])

    # (1) Guard: operator can disable groundedness check
    if not settings.groundedness_check_enabled:
        log.info("groundedness_check_disabled")
        return {"groundedness_result": None}

    final_response = state.get("final_response") or ""
    sub_answers = state.get("sub_answers", [])

    if not final_response or not sub_answers:
        log.info("verify_groundedness_skip_empty")
        return {"groundedness_result": None}

    # (2) Build context from retrieved chunks
    context = "\n\n".join(
        chunk.text
        for sa in sub_answers
        for chunk in sa.chunks
    )

    if not context.strip():
        log.info("verify_groundedness_skip_no_context")
        return {"groundedness_result": None}

    try:
        # (3) Structured LLM call
        _check_inference_circuit()  # FR-017 inference CB guard
        structured_llm = llm.with_structured_output(GroundednessResult)
        prompt = VERIFY_PROMPT.format(context=context, answer=final_response)
        result = await structured_llm.ainvoke(prompt)
        _record_inference_success()

        # (4) Apply annotations
        annotated = _apply_groundedness_annotations(final_response, result)

        # (5) GAV-adjusted confidence
        sub_scores = [sa.confidence_score for sa in sub_answers]
        if sub_scores:
            base = sum(sub_scores) / len(sub_scores)
        else:
            base = 0
        adjusted = int(base * result.confidence_adjustment)
        adjusted = max(0, min(100, adjusted))

        log.info(
            "verify_groundedness_complete",
            supported=sum(1 for v in result.verifications if v.verdict == "supported"),
            unsupported=sum(1 for v in result.verifications if v.verdict == "unsupported"),
            contradicted=sum(1 for v in result.verifications if v.verdict == "contradicted"),
            overall_grounded=result.overall_grounded,
            confidence_raw=int(base),
            confidence_adjusted=adjusted,
        )

        # (6) Return partial dict
        return {
            "groundedness_result": result,
            "confidence_score": adjusted,
            "final_response": annotated,
        }

    except Exception as exc:
        # (7) Graceful degradation (FR-005)
        _record_inference_failure()
        log.warning("verify_groundedness_failed", error=str(exc))
        return {"groundedness_result": None}
```

---

### backend/agent/nodes.py -- _extract_claim_for_citation helper (A3)

```python
import re

def _extract_claim_for_citation(text: str, marker: str) -> str:
    """Return the sentence containing the citation marker.

    Splits on sentence boundaries (.!?), finds the sentence with the marker.
    Falls back to the first 200 characters if no sentence match.
    """
    sentences = re.split(r'(?<=[.!?])\s+', text)
    for sentence in sentences:
        if marker in sentence:
            return sentence.strip()
    return text[:200]
```

---

### backend/agent/nodes.py -- validate_citations implementation (A3)

Replace the stub at lines 360-363:

```python
async def validate_citations(state: ConversationState, *, reranker: Any = None) -> dict:
    """Cross-encoder alignment check for each inline citation.

    (1) For each citation: extract claim text via _extract_claim_for_citation
    (2) Score (claim_text, chunk.text) pairs via reranker
    (3) If score < threshold: remap to highest-scoring chunk or strip
    (4) Return corrected citations
    (5) Catch all exceptions -> pass-through unvalidated
    """
    from backend.config import settings

    log = logger.bind(session_id=state["session_id"])

    citations = state.get("citations", [])
    final_response = state.get("final_response") or ""
    sub_answers = state.get("sub_answers", [])

    if not citations or not reranker:
        return {"citations": citations}

    # Flatten all chunks from all sub-answers
    all_chunks = [chunk for sa in sub_answers for chunk in sa.chunks]
    if not all_chunks:
        return {"citations": citations}

    threshold = settings.citation_alignment_threshold

    try:
        corrected: list = []
        for i, citation in enumerate(citations):
            marker = f"[{i + 1}]"
            claim_text = _extract_claim_for_citation(final_response, marker)

            # Score the cited chunk against the claim
            cited_chunk_text = citation.text
            pairs = [(claim_text, cited_chunk_text)]
            scores = reranker.model.rank(
                claim_text, [cited_chunk_text], return_documents=False
            )
            cite_score = scores[0]["score"] if scores else 0.0

            if cite_score >= threshold:
                corrected.append(citation)
                continue

            # Remap: find best chunk that clears threshold
            all_texts = [c.text for c in all_chunks]
            all_scores = reranker.model.rank(
                claim_text, all_texts, return_documents=False
            )
            ranked = sorted(all_scores, key=lambda x: x["score"], reverse=True)

            if ranked and ranked[0]["score"] >= threshold:
                best_idx = all_scores.index(ranked[0])
                best_chunk = all_chunks[best_idx]
                # Remap citation to best chunk
                citation.passage_id = best_chunk.chunk_id
                citation.text = best_chunk.text[:200]
                citation.relevance_score = ranked[0]["score"]
                corrected.append(citation)
                log.info("citation_remapped", index=i + 1, new_score=ranked[0]["score"])
            else:
                # Strip citation entirely
                log.info("citation_stripped", index=i + 1)

        log.info(
            "validate_citations_complete",
            original=len(citations),
            corrected=len(corrected),
        )
        return {"citations": corrected}

    except Exception as exc:
        # FR-008: pass-through on failure
        log.warning("validate_citations_failed", error=str(exc))
        return {"citations": citations}
```

---

### backend/agent/nodes.py -- Inference Circuit Breaker (A5)

Add module-level state and functions after existing imports and before node functions:

```python
import time

# --- Inference Service Circuit Breaker (FR-017, ADR-001) ---
_inf_circuit_open: bool = False
_inf_failure_count: int = 0
_inf_last_failure_time: float | None = None
_inf_max_failures: int = 5  # overridden from settings at first call
_inf_cooldown_secs: int = 30  # overridden from settings at first call


def _check_inference_circuit() -> None:
    """Check inference circuit breaker. Raises CircuitOpenError if open."""
    global _inf_circuit_open, _inf_max_failures, _inf_cooldown_secs
    from backend.config import settings
    from backend.errors import CircuitOpenError

    _inf_max_failures = settings.circuit_breaker_failure_threshold
    _inf_cooldown_secs = settings.circuit_breaker_cooldown_secs

    if _inf_circuit_open:
        if (
            _inf_last_failure_time is not None
            and time.monotonic() - _inf_last_failure_time >= _inf_cooldown_secs
        ):
            # Half-open: allow one probe request
            _inf_circuit_open = False
            logger.info("inference_circuit_half_open")
        else:
            raise CircuitOpenError("Inference service circuit breaker is open")


def _record_inference_success() -> None:
    """Reset inference circuit breaker on success."""
    global _inf_failure_count, _inf_circuit_open
    _inf_failure_count = 0
    _inf_circuit_open = False


def _record_inference_failure() -> None:
    """Increment inference failure count, open circuit if threshold reached."""
    global _inf_failure_count, _inf_circuit_open, _inf_last_failure_time
    _inf_failure_count += 1
    _inf_last_failure_time = time.monotonic()
    if _inf_failure_count >= _inf_max_failures:
        _inf_circuit_open = True
        logger.error("inference_circuit_opened", failure_count=_inf_failure_count)
```

> **NOTE**: A5 must also add `CircuitOpenError` to `backend/errors.py` if it does not already exist:
> ```python
> class CircuitOpenError(EmbeddinatorError):
>     """Raised when a circuit breaker is open."""
> ```

---

### backend/storage/qdrant_client.py -- Circuit Breaker Standardization (A5)

Extend `QdrantClientWrapper.__init__` to add missing fields:

```python
def __init__(self, host: str, port: int):
    from backend.config import settings
    self.host = host
    self.port = port
    self.client: AsyncQdrantClient | None = None
    self._circuit_open = False
    self._failure_count = 0
    self._last_failure_time: float | None = None
    self._max_failures = settings.circuit_breaker_failure_threshold
    self._cooldown_secs = settings.circuit_breaker_cooldown_secs
```

Add `_check_circuit`, `_record_success`, `_record_failure` methods:

```python
def _check_circuit(self) -> None:
    """Check circuit breaker state. Raises CircuitOpenError if open."""
    from backend.errors import CircuitOpenError
    if self._circuit_open:
        if (
            self._last_failure_time is not None
            and time.monotonic() - self._last_failure_time >= self._cooldown_secs
        ):
            # Half-open: allow one probe request through
            self._circuit_open = False
            logger.info("qdrant_circuit_half_open")
        else:
            logger.warning("qdrant_circuit_open", failure_count=self._failure_count)
            raise CircuitOpenError("Qdrant circuit breaker is open")

def _record_success(self) -> None:
    """Reset circuit breaker on success."""
    self._failure_count = 0
    self._circuit_open = False

def _record_failure(self) -> None:
    """Increment failure count, open circuit if threshold reached."""
    self._failure_count += 1
    self._last_failure_time = time.monotonic()
    if self._failure_count >= self._max_failures:
        self._circuit_open = True
        logger.error("qdrant_circuit_opened", failure_count=self._failure_count)
```

Wrap existing public methods (`search`, `upsert`, `ensure_collection`, `health_check`) with `self._check_circuit()` at the start, `self._record_success()` on success, `self._record_failure()` on exception.

Add Tenacity `@retry` decorator to public methods:

```python
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    wait_random,
)

# Apply to search, upsert, ensure_collection:
@retry(
    stop=stop_after_attempt(settings.retry_max_attempts),
    wait=wait_exponential(multiplier=settings.retry_backoff_initial_secs, min=1, max=10)
    + wait_random(0, 1),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
```

> **NOTE**: `_record_failure` must be called only on FINAL failure (after all retries exhausted), not on each individual retry. Place the CB recording OUTSIDE the retry wrapper. Pattern:
> ```python
> async def search(self, ...):
>     self._check_circuit()
>     try:
>         result = await self._search_with_retry(...)
>         self._record_success()
>         return result
>     except Exception:
>         self._record_failure()
>         raise
> ```

---

### backend/api/chat.py -- NDJSON Metadata Frame Update (A6)

Update the metadata frame emission (around line 149-156) to include the `groundedness` object:

```python
# Build groundedness summary from final state
groundedness_result = final_state.get("groundedness_result")
groundedness_obj = None
if groundedness_result is not None:
    groundedness_obj = {
        "supported": sum(
            1 for v in groundedness_result.verifications
            if v.verdict == "supported"
        ),
        "unsupported": sum(
            1 for v in groundedness_result.verifications
            if v.verdict == "unsupported"
        ),
        "contradicted": sum(
            1 for v in groundedness_result.verifications
            if v.verdict == "contradicted"
        ),
        "overall_grounded": groundedness_result.overall_grounded,
    }

yield json.dumps({
    "type": "metadata",
    "trace_id": db_trace_id,
    "confidence": final_state.get("confidence_score", 0),
    "groundedness": groundedness_obj,
    "citations": [
        c.model_dump() for c in final_state.get("citations", [])
    ],
    "latency_ms": latency_ms,
}) + "\n"
```

---

### backend/api/chat.py -- CircuitOpenError Handling (A5)

Inside the `generate()` function, update the outer `except` block to handle `CircuitOpenError` specifically:

```python
from backend.errors import CircuitOpenError

try:
    # ... existing streaming code ...
except CircuitOpenError:
    logger.warning("circuit_open_during_chat", session_id=session_id)
    yield json.dumps({
        "type": "error",
        "message": "A required service is temporarily unavailable. Please try again in a few seconds.",
        "code": "circuit_open",
    }) + "\n"
except Exception as e:
    logger.error("chat_stream_error", error=str(e), session_id=session_id)
    yield json.dumps({
        "type": "error",
        "message": "Unable to process your request. Please retry.",
        "code": "service_unavailable",
    }) + "\n"
```

> **IMPORTANT**: `CircuitOpenError` catch MUST come before the generic `Exception` catch.

---

## Configuration

All settings fields ALREADY EXIST in `backend/config.py` (lines 53-58). **No additions needed.**

| Field | Type | Default | Location | Description |
|-------|------|---------|----------|-------------|
| `groundedness_check_enabled` | `bool` | `True` | `config.py:53` | Enable/disable GAV |
| `citation_alignment_threshold` | `float` | `0.3` | `config.py:54` | Min cross-encoder score for citation alignment |
| `circuit_breaker_failure_threshold` | `int` | `5` | `config.py:55` | Consecutive failures to open circuit |
| `circuit_breaker_cooldown_secs` | `int` | `30` | `config.py:56` | Seconds before half-open probe |
| `retry_max_attempts` | `int` | `3` | `config.py:57` | Tenacity retry attempts |
| `retry_backoff_initial_secs` | `float` | `1.0` | `config.py:58` | Exponential backoff multiplier |

---

## Error Handling

| Location | Error | Recovery |
|----------|-------|----------|
| `verify_groundedness` | LLM call fails | Return `{"groundedness_result": None}`, log warning (FR-005) |
| `verify_groundedness` | Empty sub_answers/context | Return `{"groundedness_result": None}`, skip verification |
| `validate_citations` | Reranker raises exception | Return `{"citations": state["citations"]}`, pass-through (FR-008) |
| `validate_citations` | No reranker provided | Return `{"citations": state["citations"]}`, skip validation |
| `rewrite_query` | tier lookup | `TIER_PARAMS.get(tier, TIER_PARAMS["lookup"])` -- safe default |
| `QdrantClientWrapper` | Circuit open | Raise `CircuitOpenError` (caught in `chat.py`) |
| `QdrantClientWrapper` | Transient failure | Tenacity retry (3 attempts, exponential backoff + jitter) |
| Inference CB | Circuit open | Raise `CircuitOpenError` (caught in `chat.py`) |
| `chat.py` | CircuitOpenError | Emit `{"type": "error", "code": "circuit_open"}` NDJSON frame |
| `chat.py` | Generic exception | Emit `{"type": "error", "code": "service_unavailable"}` NDJSON frame |

---

## Testing Protocol

**NEVER run pytest inside Claude Code.** All test execution uses the external runner.

```bash
# Unit tests (per user story):
zsh scripts/run-tests-external.sh -n spec05-us1 --no-cov tests/unit/test_accuracy_nodes.py::TestVerifyGroundedness
zsh scripts/run-tests-external.sh -n spec05-us2 --no-cov tests/unit/test_accuracy_nodes.py::TestValidateCitations
zsh scripts/run-tests-external.sh -n spec05-us3 --no-cov tests/unit/test_accuracy_nodes.py::TestConfidenceIndicator
zsh scripts/run-tests-external.sh -n spec05-us4 --no-cov tests/unit/test_accuracy_nodes.py::TestTierParams
zsh scripts/run-tests-external.sh -n spec05-us6 --no-cov tests/unit/test_accuracy_nodes.py::TestCircuitBreaker

# Integration tests:
zsh scripts/run-tests-external.sh -n spec05-integration tests/integration/test_accuracy_integration.py

# Full regression (all specs):
zsh scripts/run-tests-external.sh -n spec05-full tests/

# Check status:
cat Docs/Tests/spec05-us1.status       # RUNNING | PASSED | FAILED | ERROR
cat Docs/Tests/spec05-us1.summary      # ~20 lines summary
```

---

## Done Criteria

- [ ] `VERIFY_PROMPT` constant added to `prompts.py` with `{context}` and `{answer}` placeholders
- [ ] `_apply_groundedness_annotations` helper annotates unsupported claims with `[unverified]`, removes contradicted claims, prepends warning banner when >50% unsupported
- [ ] `verify_groundedness` node replaces stub: guards on settings, calls LLM with structured output, applies annotations, computes GAV-adjusted confidence, degrades gracefully on failure
- [ ] `_extract_claim_for_citation` helper extracts sentence containing citation marker, falls back to first 200 chars
- [ ] `validate_citations` node replaces stub: scores citations via cross-encoder, remaps below-threshold citations, strips if no valid alternative, degrades gracefully on failure
- [ ] `TIER_PARAMS` dict with exactly 5 tiers (factoid, lookup, comparison, analytical, multi_hop)
- [ ] `rewrite_query` extended to include `retrieval_params` from `TIER_PARAMS` lookup in all 3 return paths
- [ ] `QdrantClientWrapper` has full circuit breaker: `_check_circuit` (with half-open/cooldown), `_record_success`, `_record_failure`, all public methods wrapped
- [ ] `QdrantClientWrapper` has Tenacity retry on public methods with exponential backoff + jitter
- [ ] Inference circuit breaker (module-level in `nodes.py`) with half-open/cooldown, wraps LLM calls
- [ ] `CircuitOpenError` defined in `errors.py` and caught in `chat.py` with informative NDJSON error frame
- [ ] NDJSON metadata frame includes `groundedness` object (or null) per `contracts/sse-events.md`
- [ ] Confidence value in metadata frame is the GAV-adjusted score (int 0-100)
- [ ] US5 (embedding validation) correctly deferred -- no `embedder.py` created
- [ ] Unit tests pass for all user stories (US1-US4, US6)
- [ ] Integration tests pass for end-to-end GAV, citation alignment, tier params, circuit breaker flows
- [ ] Performance micro-tests: citation validation < 50ms (SC-010), circuit-open rejection < 1s (SC-008)
- [ ] `ruff check .` passes on all modified files
- [ ] Full regression suite passes with 0 regressions from spec-04 baseline
