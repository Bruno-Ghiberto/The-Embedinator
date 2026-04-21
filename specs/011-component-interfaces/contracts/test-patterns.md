# Contract Test Patterns

**Feature**: 011-component-interfaces
**Date**: 2026-03-17

## Overview

Seven test patterns cover all contract validation needs. Each pattern uses Python's `inspect` module for signature introspection — no application logic is executed, no services are required.

## Pattern 1: Function Signature Verification

Verify parameter names, order, and kinds (KEYWORD_ONLY, POSITIONAL_OR_KEYWORD, VAR_KEYWORD).

```python
import inspect

def test_classify_intent_signature():
    from backend.agent.nodes import classify_intent
    sig = inspect.signature(classify_intent)
    params = list(sig.parameters.keys())
    assert params == ["state", "llm"]
    assert sig.parameters["state"].kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert sig.parameters["llm"].kind == inspect.Parameter.KEYWORD_ONLY
```

**Applies to**: All 20 node functions, 7 edge functions, tool factory, graph builders

## Pattern 2: Class Method Existence

Verify all documented methods exist on a class.

```python
def test_sqlite_db_methods():
    from backend.storage.sqlite_db import SQLiteDB
    required = [
        "create_collection", "get_collection", "list_collections",
        "create_document", "get_document", "get_document_by_hash",
        "create_query_trace", "list_traces", "get_trace",
        # ... all 35+ methods
    ]
    for name in required:
        assert hasattr(SQLiteDB, name), f"SQLiteDB missing: {name}"
```

**Applies to**: SQLiteDB (35+), QdrantStorage (12+), HybridSearcher, Reranker, BatchEmbedder, IngestionPipeline, ProviderRegistry, KeyManager

## Pattern 3: Error Hierarchy Verification

Verify all exception classes exist and inherit correctly.

```python
def test_error_hierarchy():
    from backend.errors import (
        EmbeddinatorError, QdrantConnectionError, OllamaConnectionError,
        SQLiteError, LLMCallError, EmbeddingError, IngestionError,
        SessionLoadError, StructuredOutputParseError, RerankerError,
        CircuitOpenError,
    )
    for cls in [QdrantConnectionError, OllamaConnectionError, SQLiteError,
                LLMCallError, EmbeddingError, IngestionError, SessionLoadError,
                StructuredOutputParseError, RerankerError, CircuitOpenError]:
        assert issubclass(cls, EmbeddinatorError), f"{cls.__name__} not subclass"
```

**Applies to**: 11 error classes in backend/errors.py

## Pattern 4: Dataclass vs Pydantic Distinction

Verify structural type (dataclass vs BaseModel).

```python
import dataclasses
from pydantic import BaseModel

def test_ingestion_result_is_dataclass():
    from backend.ingestion.pipeline import IngestionResult
    assert dataclasses.is_dataclass(IngestionResult)
    assert not issubclass(IngestionResult, BaseModel)
    field_names = [f.name for f in dataclasses.fields(IngestionResult)]
    assert "error" in field_names
    assert "error_msg" not in field_names  # Common wrong name
    assert "elapsed_ms" not in field_names  # Does not exist
```

**Applies to**: IngestionResult (dataclass), all Pydantic schemas (BaseModel)

## Pattern 5: ABC Enforcement

Verify abstract base classes have the correct abstract methods.

```python
import abc

def test_llm_provider_abstract():
    from backend.providers.base import LLMProvider
    assert abc.ABC in LLMProvider.__mro__
    abstract_methods = {
        n for n, m in vars(LLMProvider).items()
        if getattr(m, "__isabstractmethod__", False)
    }
    assert abstract_methods == {"generate", "generate_stream", "health_check", "get_model_name"}
```

**Applies to**: LLMProvider (4 methods), EmbeddingProvider (4 methods)

## Pattern 6: Dual Confidence Scale

Verify type annotations distinguish int (user-facing) from float (internal).

```python
import typing

def test_dual_confidence_scale():
    from backend.agent.state import ConversationState, ResearchState
    conv = typing.get_type_hints(ConversationState)
    research = typing.get_type_hints(ResearchState)
    assert conv["confidence_score"] is int, "Must be int (0-100)"
    assert research["confidence_score"] is float, "Must be float (0.0-1.0)"
```

**Applies to**: ConversationState.confidence_score, ResearchState.confidence_score

## Pattern 7: Negative Assertions (Phantom Methods)

Verify commonly-confused methods do NOT exist.

```python
def test_no_phantom_methods():
    from backend.retrieval.reranker import Reranker
    from backend.ingestion.pipeline import IngestionPipeline
    from backend.storage.sqlite_db import SQLiteDB

    assert not hasattr(Reranker, "score_pair")
    assert not hasattr(IngestionPipeline, "check_duplicate")
    assert not hasattr(SQLiteDB, "find_by_hash")
    assert not hasattr(SQLiteDB, "store_parent_chunks")
    assert not hasattr(SQLiteDB, "store_trace")
    assert not hasattr(SQLiteDB, "get_all_settings")
```

**Applies to**: All known wrong method names from the 11-specify.md coherence review
