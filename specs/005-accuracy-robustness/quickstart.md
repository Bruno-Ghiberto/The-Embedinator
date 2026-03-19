# Developer Quickstart: Accuracy, Precision & Robustness

**Branch**: `005-accuracy-robustness`

## Prerequisites

- Project running: `docker compose up` (Qdrant + Ollama + backend + frontend)
- Python venv: handled automatically by `scripts/run-tests-external.sh`

## What This Feature Implements

| Component | File | Status |
|-----------|------|--------|
| `verify_groundedness` node body | `backend/agent/nodes.py` | Replace Phase 2 stub |
| `validate_citations` node body | `backend/agent/nodes.py` | Replace Phase 2 stub |
| `VERIFY_PROMPT` constant | `backend/agent/prompts.py` | New constant |
| Tier-based retrieval params | `backend/agent/nodes.py` (rewrite_query) | Extend existing function |
| Circuit breaker in QdrantClient | `backend/storage/qdrant_client.py` | Extend existing class |

## Key Configuration (already in `backend/config.py`)

```python
groundedness_check_enabled: bool = True      # Toggle GAV on/off
citation_alignment_threshold: float = 0.3    # Citation remap threshold
circuit_breaker_failure_threshold: int = 5   # Failures before circuit opens
circuit_breaker_cooldown_secs: int = 30      # Cooldown before half-open probe
retry_max_attempts: int = 3                  # Tenacity retry attempts
retry_backoff_initial_secs: float = 1.0      # Initial backoff
```

Override via `.env`:
```env
GROUNDEDNESS_CHECK_ENABLED=false  # Disable GAV for development
CITATION_ALIGNMENT_THRESHOLD=0.2  # Lower threshold for testing
```

## Running Tests (External Runner — NEVER pytest inside Claude Code)

```zsh
# Unit tests only (fast, no services needed)
zsh scripts/run-tests-external.sh -n spec05-unit --no-cov tests/unit/

# Integration tests (requires running Qdrant + Ollama)
zsh scripts/run-tests-external.sh -n spec05-integration tests/integration/

# Full suite
zsh scripts/run-tests-external.sh -n spec05-full tests/

# Poll status
cat Docs/Tests/spec05-full.status

# Read summary
cat Docs/Tests/spec05-full.summary
```

## Implementing verify_groundedness

```python
# backend/agent/nodes.py — replace the Phase 2 stub body

async def verify_groundedness(state: ConversationState, *, llm: Any = None) -> dict:
    if not settings.groundedness_check_enabled or llm is None:
        return {"groundedness_result": None}

    # 1. Build context from sub-answers
    context = "\n\n".join(
        f"[{i+1}] {sa.answer}" for i, sa in enumerate(state["sub_answers"])
    )

    # 2. Low-temperature structured LLM call
    structured_llm = llm.with_structured_output(GroundednessResult)
    messages = [
        SystemMessage(content=VERIFY_PROMPT.format(
            context=context, answer=state["final_response"]
        ))
    ]

    try:
        result: GroundednessResult = await structured_llm.ainvoke(messages)
    except Exception as exc:
        log.warning("verify_groundedness_failed", error=str(exc))
        return {"groundedness_result": None}

    # 3. Apply annotations to final_response
    annotated = _apply_groundedness_annotations(state["final_response"], result)

    # 4. Compute confidence adjustment
    sub_scores = [sa.confidence_score for sa in state["sub_answers"]]
    raw = sum(sub_scores) / max(1, len(sub_scores))
    adjusted = max(0, min(100, int(raw * result.confidence_adjustment)))

    return {
        "groundedness_result": result,
        "confidence_score": adjusted,
        "final_response": annotated,
    }
```

## TIER_PARAMS Pattern

```python
# backend/agent/nodes.py — module-level constant

TIER_PARAMS: dict[str, dict] = {
    "factoid":    {"top_k": 5,  "max_iterations": 3,  "max_tool_calls": 3,  "confidence_threshold": 0.7},
    "lookup":     {"top_k": 10, "max_iterations": 5,  "max_tool_calls": 5,  "confidence_threshold": 0.6},
    "comparison": {"top_k": 15, "max_iterations": 7,  "max_tool_calls": 6,  "confidence_threshold": 0.55},
    "analytical": {"top_k": 25, "max_iterations": 10, "max_tool_calls": 8,  "confidence_threshold": 0.5},
    "multi_hop":  {"top_k": 30, "max_iterations": 10, "max_tool_calls": 8,  "confidence_threshold": 0.45},
}
```

## Agent Teams Spawn Protocol

Instruction files: `Docs/PROMPTS/spec-05-accuracy/agents/`

Spawn: `"Read your instruction file at Docs/PROMPTS/spec-05-accuracy/agents/<file> FIRST, then execute all assigned tasks."`
