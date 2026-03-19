# Quickstart: ResearchGraph

**Feature**: 003-research-graph | **Date**: 2026-03-11

## Prerequisites

- Docker Compose running (`docker compose up`): qdrant, ollama, backend, frontend
- Ollama model downloaded (e.g., `qwen2.5:7b`)
- At least one collection with indexed documents in Qdrant
- Python 3.14+ with dependencies from `requirements.txt`

## How It Works

The ResearchGraph is an internal component — you don't call it directly. It is automatically spawned by the ConversationGraph when a user asks a question via `POST /api/chat`.

### Flow

1. User sends a chat message
2. ConversationGraph decomposes the question into sub-questions
3. For each sub-question, a ResearchGraph instance is spawned via `Send()`
4. Each ResearchGraph runs an orchestrator loop:
   - LLM decides which search tools to call
   - Tools execute (Qdrant search, reranking, parent chunk fetch)
   - Results are deduplicated and accumulated
   - Loop continues until confidence is sufficient or budget is exhausted
5. Each ResearchGraph returns a `SubAnswer` with citations
6. ConversationGraph aggregates all sub-answers into the final response

### Key Constants

| Constant | Value | Meaning |
|----------|-------|---------|
| MAX_ITERATIONS | 10 | Maximum orchestrator loop cycles |
| MAX_TOOL_CALLS | 8 | Maximum tool invocations (including retries) |
| CONFIDENCE_THRESHOLD | 0.6 | Minimum confidence to accept results |
| Compression trigger | 75% | Context window usage that triggers compression |

## Development

### Running Tests

```bash
# Unit tests
zsh scripts/run-tests-external.sh -n research-unit tests/unit/test_research_nodes.py tests/unit/test_research_edges.py tests/unit/test_tools.py tests/unit/test_retrieval.py tests/unit/test_confidence.py

# Integration tests (requires Docker services)
zsh scripts/run-tests-external.sh -n research-integration tests/integration/test_research_graph.py

# Check status
cat Docs/Tests/research-unit.status
cat Docs/Tests/research-unit.summary
```

### Key Files

| File | Purpose |
|------|---------|
| `backend/agent/research_graph.py` | Graph definition + `build_research_graph()` |
| `backend/agent/research_nodes.py` | 6 node functions |
| `backend/agent/research_edges.py` | 2 edge/routing functions |
| `backend/agent/tools.py` | 6 @tool-decorated search tools |
| `backend/retrieval/searcher.py` | Qdrant hybrid search |
| `backend/retrieval/reranker.py` | Cross-encoder reranking |
| `backend/storage/parent_store.py` | SQLite parent chunk reads |
| `backend/agent/confidence.py` | Signal-based confidence scoring |

### Mock for Testing

```python
from tests.mocks import build_mock_research_graph

# Returns a simple graph that immediately returns a canned SubAnswer
# Use for ConversationGraph unit tests that don't need real retrieval
mock_graph = build_mock_research_graph()
conversation_graph = build_conversation_graph(research_graph=mock_graph)
```
