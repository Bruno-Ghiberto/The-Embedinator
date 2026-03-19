# Quickstart: ConversationGraph Development

**Date**: 2026-03-10
**Feature**: [spec.md](spec.md)

## Prerequisites

- Python 3.14+ with virtual environment
- Docker Compose running (Qdrant + Ollama services)
- Phase 1 codebase on branch `001-vision-arch` merged to `main`

## Setup

### 1. Install new dependency

```bash
pip install langgraph-checkpoint-sqlite>=2.0
```

Add to `requirements.txt`:
```
langgraph-checkpoint-sqlite>=2.0
```

### 2. Verify existing modules

Confirm Phase 1 modules are present and importable:

```python
from backend.agent.state import ConversationState, ResearchState
from backend.agent.schemas import QueryAnalysis, Citation, SubAnswer
from backend.agent.prompts import SYSTEM_PROMPT
from backend.agent.retrieval import retrieve_passages
from backend.agent.citations import build_citations
from backend.agent.confidence import compute_confidence
```

### 3. Run existing tests

```bash
pytest tests/unit/ -v
```

All 61 tests should pass before starting implementation.

## Development Order

### Step 1: Scaffold

```bash
# Extend state.py — add intent field
# Extend prompts.py — add new prompt constants
# Create edges.py — routing functions
```

Verify: `python -c "from backend.agent.state import ConversationState; print('OK')"`

### Step 2: Node Implementations

Create `backend/agent/nodes.py` with all node functions. Each function:
- Takes `state: ConversationState` as first argument
- Returns a `dict` with updated state fields
- Is stateless and pure (no side effects beyond injected dependencies)

```python
# Example node signature
async def classify_intent(state: ConversationState, *, llm) -> dict:
    ...
```

### Step 3: Graph Wiring

Create `backend/agent/conversation_graph.py`:

```python
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

def build_conversation_graph(research_graph, checkpointer=None):
    graph = StateGraph(ConversationState)
    # Add nodes, edges, compile
    return graph.compile(checkpointer=checkpointer)
```

### Step 4: API Refactor

Update `backend/api/chat.py` to invoke the graph:

```python
# Before: direct pipeline
passages = await retrieve_passages(...)
answer = await generate_answer_stream(...)

# After: graph invocation
async for chunk, metadata in graph.astream(state, stream_mode="messages", config=config):
    yield json.dumps({"type": "chunk", "text": chunk.content}) + "\n"
```

### Step 5: Tests

```bash
# Unit tests
pytest tests/unit/test_nodes.py tests/unit/test_edges.py -v

# Integration tests
pytest tests/integration/test_conversation_graph.py -v

# Full suite
pytest -v --cov=backend --cov-report=term-missing
```

## Key Files Reference

| File | Role | Status |
|------|------|--------|
| `backend/agent/conversation_graph.py` | Graph definition | NEW |
| `backend/agent/nodes.py` | Node functions | NEW |
| `backend/agent/edges.py` | Edge/routing functions | NEW |
| `backend/agent/prompts.py` | Prompt constants | EXTEND |
| `backend/agent/state.py` | State schemas | EXTEND (add `intent`) |
| `backend/api/chat.py` | Chat endpoint | REFACTOR |
| `backend/main.py` | App factory | EXTEND (add checkpointer) |

## Testing with Mock ResearchGraph

Until spec-03 is implemented, use the mock research graph:

```python
# tests/conftest.py
@pytest.fixture
def mock_research_graph():
    from tests.mocks import build_mock_research_graph
    return build_mock_research_graph()

@pytest.fixture
def conversation_graph(mock_research_graph):
    from backend.agent.conversation_graph import build_conversation_graph
    return build_conversation_graph(mock_research_graph)
```

## Common Issues

- **Import errors**: Ensure `backend/` is on `PYTHONPATH` or use `pip install -e .`
- **Ollama not running**: Start with `docker compose up ollama -d`. First model download takes ~5 min.
- **Checkpoint DB locked**: Only one process can write to `data/checkpoints.db`. Stop other instances.
- **Token counting**: `count_tokens_approximately` is a heuristic (~80-90% accuracy). If tests fail on exact token counts, use a tolerance margin.
