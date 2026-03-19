# A2 — Unit Tests: Retrieval (Wave 2)

**Agent type**: `python-expert`
**Model**: `claude-sonnet-4-6`
**Wave**: 2 (parallel with A3)
**Gate requirement**: `Docs/Tests/spec16-scaffold.status` must equal `PASSED` before starting.

Read `specs/016-testing-strategy/tasks.md` then await orchestrator instructions before proceeding.

---

## Assigned Tasks

| Task | File to Create |
|------|----------------|
| T012 | `tests/unit/test_reranker.py` |
| T013 | `tests/unit/test_score_normalizer.py` |
| T014 | `tests/unit/test_storage_chunker.py` |
| T017 | Gate run (see below) |

---

## Pre-Task Check

Before writing any file, verify the gate:
```bash
cat Docs/Tests/spec16-scaffold.status   # must be PASSED
```

Also verify these production symbols exist at expected paths:
```bash
python -c "from backend.retrieval.reranker import Reranker; print('OK')"
python -c "from backend.retrieval.score_normalizer import normalize_scores; print('OK')"
python -c "from backend.storage.chunker import chunk_text; print('OK')"
```

---

## T012 — tests/unit/test_reranker.py

**Import**: `from backend.retrieval.reranker import Reranker`
**Symbol**: class with `__init__(self, settings)` and `rerank(chunks, query, top_k)` method.

Mock the cross-encoder model via `unittest.mock.patch` — do NOT load real `sentence_transformers` weights. Real model loading takes > 1 second, violating SC-003.

Required test cases (minimum 5):
1. `Reranker` instantiates with a `Settings` object without error.
2. `reranker.rerank(chunks, query)` calls the underlying model's scoring method.
3. Results are returned in descending score order (highest rerank_score first).
4. `top_k` parameter truncates results to at most `top_k` items.
5. `RerankerError` is raised when the model is unavailable (mock the model to raise).

`RerankerError` import: `from backend.errors import RerankerError`
`Settings` import: `from backend.config import Settings`

**Shared fixture available**: `sample_chunks` from `tests/conftest.py` provides `list[RetrievedChunk]` with 3 items.

---

## T013 — tests/unit/test_score_normalizer.py

**Import**: `from backend.retrieval.score_normalizer import normalize_scores`
**Symbol**: module-level FUNCTION — do NOT call `ScoreNormalizer(...)`, no such class exists.

Required test cases (minimum 5):
1. Empty list input returns empty list.
2. Single item returns the item unchanged (or with score mapped to 0.0/1.0 per implementation).
3. When all scores are equal, output is valid (no division-by-zero crash).
4. Minimum score in input maps to 0.0 in output.
5. Maximum score in input maps to 1.0 in output.
6. Order of items is preserved after normalization.

---

## T014 — tests/unit/test_storage_chunker.py

**Import**: `from backend.storage.chunker import chunk_text`
**Symbol**: module-level FUNCTION.

Required test cases (minimum 5):
1. Empty string input returns empty list.
2. Text shorter than `chunk_size` returns exactly one chunk.
3. Long text returns multiple chunks (each within size limit).
4. No individual chunk exceeds `max_size` characters.
5. Overlap parameter is respected (if supported by implementation).

---

## T017 — Gate Run

After creating all three test files, run the gate:

```bash
zsh scripts/run-tests-external.sh -n spec16-a2 --no-cov tests/unit/test_reranker.py tests/unit/test_score_normalizer.py tests/unit/test_storage_chunker.py
```

Then verify:
```bash
cat Docs/Tests/spec16-a2.status   # must be PASSED
```

Also run a regression check to confirm existing tests are unaffected:
```bash
zsh scripts/run-tests-external.sh -n spec16-a2-regression --no-cov tests/unit/
cat Docs/Tests/spec16-a2-regression.status   # must be PASSED
```

Report `spec16-a2.status` result to the orchestrator when complete.

---

## Critical Gotchas

- `normalize_scores` is a function, not a class. `ScoreNormalizer` does not exist.
- `Reranker` takes `Settings` in `__init__` — check the actual signature before writing tests.
- `sample_chunks` items use fields: `chunk_id`, `text`, `source_file`, `page`, `breadcrumb`, `parent_id`, `collection`, `dense_score`, `sparse_score`, `rerank_score`. NOT `id`, `content`, `score`.
- NEVER run `pytest` directly. Always use `zsh scripts/run-tests-external.sh`.
- Use `--no-cov` for development runs to avoid the 80% coverage hard gate during iteration.
