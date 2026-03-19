# Quickstart: Component Interface Contracts

**Feature**: 011-component-interfaces
**Date**: 2026-03-17

## Prerequisites

- Python 3.14+ with venv at `.venv/`
- All backend dependencies installed (`pip install -r requirements.txt`)
- No external services required (Qdrant, Ollama, SQLite not needed)

## Running Contract Tests

### All contract tests at once

```bash
zsh scripts/run-tests-external.sh -n contracts tests/unit/test_contracts_agent.py tests/unit/test_contracts_storage.py tests/unit/test_contracts_retrieval.py tests/unit/test_contracts_ingestion.py tests/unit/test_contracts_providers.py tests/unit/test_contracts_cross_cutting.py
```

### Individual test files

```bash
# Agent layer (state schemas, nodes, edges, tools, graph builders)
zsh scripts/run-tests-external.sh -n contracts-agent tests/unit/test_contracts_agent.py

# Storage layer (SQLiteDB, QdrantStorage, ParentStore)
zsh scripts/run-tests-external.sh -n contracts-storage tests/unit/test_contracts_storage.py

# Retrieval layer (HybridSearcher, Reranker, ScoreNormalizer)
zsh scripts/run-tests-external.sh -n contracts-retrieval tests/unit/test_contracts_retrieval.py

# Ingestion layer (Pipeline, Embedder, Chunker, IncrementalChecker)
zsh scripts/run-tests-external.sh -n contracts-ingestion tests/unit/test_contracts_ingestion.py

# Provider layer (ABCs, Registry, KeyManager, concrete providers)
zsh scripts/run-tests-external.sh -n contracts-providers tests/unit/test_contracts_providers.py

# Cross-cutting (errors, schemas, NDJSON events, config)
zsh scripts/run-tests-external.sh -n contracts-cross tests/unit/test_contracts_cross_cutting.py
```

### Full regression (contract tests + all existing tests)

```bash
zsh scripts/run-tests-external.sh -n full-regression tests/
```

## Checking Results

```bash
# Poll status (1 line)
cat Docs/Tests/contracts.status     # RUNNING | PASSED | FAILED | ERROR

# Read summary (~20 lines)
cat Docs/Tests/contracts.summary

# Debug specific failures only
grep "FAILED" Docs/Tests/contracts.log
grep -A5 "test_specific_name" Docs/Tests/contracts.log
```

## What the Tests Verify

Contract tests use `inspect.signature()` to verify:
- Method/function existence on documented classes/modules
- Parameter names and order
- Parameter kinds (keyword-only vs positional vs **kwargs)
- Default values (e.g., `config: RunnableConfig = None`)
- Class inheritance (error hierarchy, ABC enforcement)
- Structural type (dataclass vs Pydantic BaseModel)
- Type annotations on state schema fields

Contract tests do NOT:
- Execute application logic
- Connect to databases or services
- Test behavioral correctness (that's specs 02-10)
