# Agent A4: Provider, Ingestion, and Cross-Cutting Contract Tests

## Agent: python-expert | Model: sonnet | Wave: 3

## Role

You are the Wave 3 agent for spec-11. You write 3 test files covering providers,
ingestion, and cross-cutting contracts. You run sequentially after Wave 2 (A2 and A3)
has completed. You work alone in this wave.

---

## Assigned Tasks

### Provider Contracts (test_contracts_providers.py)

**T030** -- Create `tests/unit/test_contracts_providers.py` with imports. Import `inspect`,
`abc`, all provider modules (`base`, `registry`, `key_manager`, `ollama`, `openrouter`,
`openai`, `anthropic`).

**T031** -- Write LLMProvider ABC tests (FR-016, Pattern 5): verify:
- `abc.ABC` is in `LLMProvider.__mro__`
- 4 abstract methods: `generate`, `generate_stream`, `health_check`, `get_model_name`
- `generate` params include `prompt` and `system_prompt`
- Cannot instantiate `LLMProvider` directly (raises `TypeError`)

**T032** -- Write EmbeddingProvider ABC tests (FR-016, Pattern 5): verify:
- 4 abstract methods: `embed`, `embed_single`, `get_model_name`, `get_dimension`
- `embed` has an optional `model` parameter (added by spec-10 FR-006)

**T033** -- Write ProviderRegistry tests (FR-016): verify:
- Constructor takes `settings` (NOT `SQLiteDB`)
- Methods exist: `get_active_llm`, `get_active_langchain_model`,
  `get_embedding_provider`, `set_active_provider`
- `get_embedding_provider` has NO `db` param (it uses the internal provider directly)

**T034** -- Write KeyManager and concrete provider tests (FR-016): verify:
- `KeyManager` has `encrypt`, `decrypt`, `is_valid_key` methods
- 4 concrete LLMProvider subclasses: `OllamaLLMProvider`, `OpenRouterLLMProvider`,
  `OpenAILLMProvider`, `AnthropicLLMProvider`
- 1 concrete EmbeddingProvider subclass: `OllamaEmbeddingProvider`
- `ProviderRateLimitError` exists in `backend/providers/base.py`

### Retrieval Contracts (T039 -- run providers + retrieval tests)

**T039** -- Run provider and retrieval contract tests and fix any failures.

### Ingestion Contracts (test_contracts_ingestion.py)

**T040** -- Create `tests/unit/test_contracts_ingestion.py` with imports. Import `inspect`,
`dataclasses`, `pydantic.BaseModel`, all ingestion modules (`pipeline`, `embedder`,
`chunker`, `incremental`).

**T041** -- Write IngestionPipeline constructor tests (FR-013): verify:
- Constructor takes exactly 3 params: `db`, `qdrant`, `embedding_provider`
- `qdrant` receives `QdrantClientWrapper` (NOT `QdrantStorage`) -- check the import or
  type annotation
- `check_duplicate` does NOT exist on `IngestionPipeline` (Pattern 7)

**T042** -- Write IngestionResult tests (FR-014, Pattern 4): verify:
- Is a `@dataclass` via `dataclasses.is_dataclass()` -- NOT `BaseModel`
- Fields include: `document_id`, `job_id`, `status`, `chunks_processed`,
  `chunks_skipped`, `error`
- `error_msg` does NOT exist (common wrong name)
- `elapsed_ms` does NOT exist

**T043** -- Write BatchEmbedder tests (FR-012): verify:
- Method is `embed_chunks` (NOT `embed_batch`)
- `validate_embedding` is a standalone module-level function in `embedder.py`
  (NOT a method on `BatchEmbedder`). Import it directly:
  `from backend.ingestion.embedder import validate_embedding`

**T044** -- Write IncrementalChecker, ChunkSplitter, and UpsertBuffer tests (FR-015):
verify:
- `check_duplicate` lives on `IncrementalChecker` (NOT `IngestionPipeline`)
- `compute_file_hash` exists on `IncrementalChecker`
- `ChunkSplitter` has methods: `split_into_parents`, `split_parent_into_children`,
  `prepend_breadcrumb`, `compute_point_id`
- `UpsertBuffer` class exists with `add`, `flush`, `pending_count` methods

**T045** -- Run ingestion contract tests and fix any failures.

### Cross-Cutting Contracts (test_contracts_cross_cutting.py)

**T046** -- Create `tests/unit/test_contracts_cross_cutting.py` with imports. Import
`inspect`, `typing`, all error classes, schema classes, Settings.

**T047** -- Write error hierarchy tests (FR-017, Pattern 3): import all 11 classes from
`backend/errors.py`:
- `EmbeddinatorError` (base class)
- `QdrantConnectionError`, `OllamaConnectionError`, `SQLiteError`
- `LLMCallError`, `EmbeddingError`, `IngestionError`
- `SessionLoadError`, `StructuredOutputParseError`, `RerankerError`
- `CircuitOpenError`
Verify all 10 specific errors are subclasses of `EmbeddinatorError`.

**T048** -- Write cross-layer Pydantic schema tests (FR-018): verify key fields on the
6 cross-layer schemas:
- `QueryAnalysis` has `complexity_tier` field with correct Literal type
- `ClaimVerification` has `verdict` field
- `GroundednessResult` has `overall_grounded` field
- `RetrievedChunk`, `Citation`, `SubAnswer` are `BaseModel` subclasses with expected
  key fields

**T049** -- Write API schema import tests (FR-018): verify all 30+ API models are
importable from `backend/agent/schemas.py`:
- `CollectionResponse`, `DocumentResponse`, `ChatRequest`, `ProviderResponse`,
  `HealthResponse`, `ErrorResponse`, `IngestionJobResponse`, `ModelInfo`,
  `SettingsResponse`, `QueryTraceResponse`, etc.
- Import check only -- no field validation needed for API schemas

**T050** -- Write NDJSON event model tests (FR-018): verify all 10 event models are
importable and are `BaseModel` subclasses:
- `SessionEvent`, `StatusEvent`, `ChunkEvent`, `CitationEvent`,
  `MetaReasoningEvent`, `ConfidenceEvent`, `GroundednessEvent`,
  `DoneEvent`, `ClarificationEvent`, `ErrorEvent`

**T051** -- Write Settings config test: verify `Settings` is a `BaseSettings` subclass
in `backend/config.py`, verify key fields exist: `confidence_threshold`,
`meta_relevance_threshold`, `meta_variance_threshold`.

**T052** -- Run cross-cutting contract tests and fix any failures.

---

## Output Files

- `tests/unit/test_contracts_providers.py`
- `tests/unit/test_contracts_ingestion.py`
- `tests/unit/test_contracts_cross_cutting.py`

---

## Key Technical Facts

1. **`IngestionResult` is a `@dataclass`, not a `BaseModel`**: Use
   `dataclasses.is_dataclass(IngestionResult)` to verify. Do NOT use
   `issubclass(IngestionResult, BaseModel)`.

2. **No `EmbeddingResult` class exists**: The embedder returns
   `tuple[list[list[float] | None], int]` directly.

3. **Method name: `embed_chunks`, not `embed_batch`**: The BatchEmbedder method name.

4. **`validate_embedding` is standalone**: It is a module-level function, not a method.

5. **`IngestionPipeline` takes 3 params**: `db`, `qdrant` (a `QdrantClientWrapper`),
   and `embedding_provider`. It creates `ChunkSplitter` and `BatchEmbedder` internally.

6. **`check_duplicate` is on `IncrementalChecker`**, not on `IngestionPipeline`.

7. **`IngestionResult.error`, not `error_msg`**: And there is no `elapsed_ms` field.

8. **ProviderRegistry constructor takes `settings: Settings`**, not `SQLiteDB`.

9. **`get_embedding_provider()` has no `db` param** -- it returns the internal Ollama
   embedding provider directly.

10. **Error hierarchy**: 11 classes total. `EmbeddinatorError` is the base. All 10
    specific errors inherit from it. `CircuitOpenError` is commonly missed.

---

## Testing Rule (MANDATORY)

```
NEVER run pytest directly inside Claude Code. Use ONLY:
  zsh scripts/run-tests-external.sh -n <name> <target>

Poll: cat Docs/Tests/<name>.status     (RUNNING | PASSED | FAILED | ERROR)
Read: cat Docs/Tests/<name>.summary    (~20 lines, token-efficient)
Full: cat Docs/Tests/<name>.log
```

Run each file separately:
```bash
zsh scripts/run-tests-external.sh -n contracts-providers tests/unit/test_contracts_providers.py
zsh scripts/run-tests-external.sh -n contracts-ingestion tests/unit/test_contracts_ingestion.py
zsh scripts/run-tests-external.sh -n contracts-cross tests/unit/test_contracts_cross_cutting.py
```

---

## Gate Check

After completing all tasks:

1. Run all 3 test files via external runner (can run in parallel)
2. Poll all 3 status files until PASSED or FAILED
3. If any FAILED, read the summary, fix the test, and re-run
4. When ALL 3 pass, notify the Orchestrator that A4 / Wave 3 is complete
