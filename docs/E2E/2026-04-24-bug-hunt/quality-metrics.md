# Quality Baseline — 2026-05-04

> **Status**: Wave 3 partial — RAGAS scores deferred (Python 3.14 / ragas 0.2.x
> incompatibility, see Known Limitations §1). Qualitative baseline captured via
> structured sweep against all 20 golden Q&A pairs.

## Per-category outcome (qualitative baseline)

Source data: [`baseline-sweep-2026-05-04.json`](baseline-sweep-2026-05-04.json) —
each pair queried once via `/api/chat` with `collection_ids=[NAG_COLLECTION]`.
"Declined" = response contained one of the system's decline markers (e.g.
`"none were sufficiently relevant"`) OR returned 0 citations.

| Category     | Pairs | Answered | Declined | Errored | Answer rate |
|:-------------|:-----:|:--------:|:--------:|:-------:|:-----------:|
| Factoid      |  10   |    2     |    8     |    0    |   **20%**   |
| Analytical   |   4   |    1     |    3     |    0    |   **25%**   |
| Follow-up    |   3   |    0     |    3     |    0    |    **0%**   |
| Out-of-scope |   2   |    0     |    2     |    0    |    100%¹    |
| Ambiguous    |   1   |    1     |    0     |    0    |    100%²    |
| **Overall**  |  20   |    4     |   16     |    0    |   **20%**   |

¹ Out-of-scope pairs SHOULD decline — 2/2 declined correctly (H4 CONFIRMED).
² Q-020 attempted disambiguation rather than asking for clarification — manual review needed.

### Pairs that answered

- **Q-001** (factoid, NAG-200 §1.1) — 5 citations, 28.4s
- **Q-009** (factoid) — 5 citations, 33.6s
- **Q-013** (analytical) — 5 citations, 33.3s
- **Q-020** (ambiguous, attempted disambiguation) — 5 citations, 34.7s

### Pairs that declined despite a reference answer existing in the corpus

All 13 listed below have reference answers verified extractable from the NAG
corpus per `golden-qa.yaml` author validation, yet the system returned 0
citations and a decline phrase:

- Factoid: Q-002, Q-003, Q-004, Q-005, Q-006, Q-007, Q-008, Q-010
- Analytical: Q-011, Q-012, Q-014
- Follow-up: Q-015, Q-016, Q-017

## Hypothesis verdicts

- **H1** — Spanish-on-English-embedder degradation: **PARTIALLY OBSERVED, DEFERRED**.
  An 80% decline rate on factoid questions whose answers exist in the corpus is
  consistent with H1 but does not isolate the embedder from the reranker or the
  confidence threshold. Verifying H1 specifically requires per-stage retrieval
  instrumentation (raw dense scores vs reranker scores vs final confidence) on
  the declined pairs. Re-evaluate during the follow-up RAGAS run with stage
  metrics enabled.

- **H2** — PDF table extraction edges: **NOT VERIFIABLE**. The questions targeting
  numeric tables (Q-005 reguladores, Q-006 diámetros, Q-013 cross-reference)
  mostly declined → no retrieved contexts to inspect. Q-013 answered with 5
  citations; manual inspection of those passages is the next step.

- **H3** — Citation cross-reference grounding: **PARTIALLY VERIFIABLE**. Q-013
  (analytical, requires cross-doc grounding) DID answer with 5 citations.
  Q-011/Q-012/Q-014 declined → no data. Manual inspection of Q-013's citation
  set is required to confirm cross-document grounding.

- **H4** — Out-of-scope graceful decline: **CONFIRMED**. Both user-authored
  out-of-scope pairs (Q-018 electrical wiring, Q-019 post-2024 amendment)
  declined cleanly. Q-020 (ambiguous, diameter polysemy) attempted partial
  disambiguation rather than asking for clarification — flag for manual review.
  **Note**: the system's actual decline phrasing is `"none were sufficiently
  relevant"` and `"the documents may not cover this specific topic"` — not the
  Spanish-language phrases the spec originally listed. The expected-decline
  phrase set in `tests/quality/test_ragas_baseline.py` was extended in the
  baseline sweep to include the system's actual phrasing.

## New findings (not in original H1–H4 set)

- **F1 — Over-aggressive quality gate on Spanish corpus**. 16/17 (94%) of
  answerable questions declined despite having extractable reference answers in
  the corpus. The decline path triggers AFTER hybrid retrieval returns
  candidates, suggesting the bottleneck is downstream: cross-encoder reranker
  scores, the 60-point confidence threshold, or the LLM's self-judgment that
  the retrieved context is "not sufficiently relevant". Recommended
  investigation in a follow-up spec:
    1. Lower `confidence_threshold` to 30 or 40 and re-sweep — does answer rate climb?
    2. Inspect raw dense + sparse + reranker scores on declined pairs.
    3. Test with a multilingual embedding model (BGE-M3, multilingual-e5).

- **F2 — Non-determinism on borderline questions**. Q-001 declined in an
  earlier dry-run but answered in this sweep; Q-002 answered in the earlier
  dry-run but declined here. The confidence threshold appears to be near the
  scoring distribution mean for several pairs, producing run-to-run variance.

## Known limitations

### 1. RAGAS execution blocked by Python 3.14 + ragas 0.2.x

The Wave 2 RAGAS harness (`tests/quality/test_ragas_baseline.py`) is **scaffold-
ready but cannot execute** on the project's current Python 3.14 runtime.

**Root cause**: `ragas==0.2.15` wraps every metric call in
`asyncio.wait_for(self._single_turn_ascore(...), timeout=...)`. Python 3.14
hardened `asyncio.Timeout` to require an active asyncio task; combined with
ragas's `nest_asyncio.apply()` (which ragas auto-applies at import), the wait_for
runs outside the new task-required scope and raises
`RuntimeError: Timeout should be used inside a task`. All metric jobs return
NaN as a result — see `Docs/Tests/spec28-ragas.log` for the full trace.

**Wave 2 bugs found and fixed during Wave 3 unblocking** (preserved in the
harness so the next attempt has fewer surprises):
1. `tests/quality/conftest.py:185` used `llm_factory(model, provider="openai", client=client)` — neither `provider` nor `client` exist in ragas 0.2.15's signature. Fixed: pass `model` + `base_url` kwargs.
2. `AnswerRelevancy` was constructed without an embedder. ragas's
   `embedding_factory()` only supports OpenAI proper, so the harness now wires
   `LangchainEmbeddingsWrapper(OllamaEmbeddings(...))` and passes it explicitly.
3. The original `httpx.AsyncClient` fixture × ragas's `nest_asyncio.apply()`
   broke `sniffio.current_async_library()` for every backend call. Fixed: use
   sync `httpx.Client` (no parallelism benefit lost — the sweep is sequential).

**Resolution path**: tracked in a follow-up issue. Two viable approaches —
(a) upgrade to ragas 0.4.x and adapt to the renamed metrics API, or (b) run the
eval under a Python 3.13 sub-environment. The harness skip-marker can be
removed once either path lands.

### 2. Self-bias risk in judge LLM (planned)

Future RAGAS runs default to `RAGAS_JUDGE=local` → Ollama `qwen2.5:7b`, the
same model the backend uses. This is documented self-bias risk. Mitigation
path: set `RAGAS_JUDGE=openrouter:<model>` (provider wiring not yet
implemented; tracked separately).

### 3. Q-020 (ambiguous) attempted partial answer

Q-020 ("¿Cuál es el diámetro mínimo permitido según la NAG-200?") is
intentionally ambiguous — the corpus contains diameter requirements at multiple
levels (cañería, regulador, etc.) and the system should ask for clarification.
Instead it answered partially. Behavior is documented for future ambiguity-
handling work; no bug filed because spec-28 lists this as informational.

## Reproduction

### Qualitative sweep (this baseline)

- **Dataset**: `docs/E2E/2026-04-24-bug-hunt/golden-qa.yaml` (20 pairs, locked at FR-014/FR-019)
- **Sweep script**: `/tmp/baseline_sweep.py` (one-off; see commit message for full source)
- **Backend**: `develop` branch + Wave 3 `RAGAS_COLLECTION_ID` scoping patch
- **Stack state**: warm — backend container had been up ~1 h with ~5 prior queries
- **Collection scope**: NAG corpus only (`22923ab5-ea0d-4bea-8ef2-15bf0262674f`) via `RAGAS_COLLECTION_ID` env var (default in test_ragas_baseline.py)
- **Sweep duration**: 568 s (avg 28 s/question)
- **Output**: `baseline-sweep-2026-05-04.json`
- **Backend git SHA**: 1e46864

### Future RAGAS run (when blocker resolved)

- **Command**: `zsh scripts/run-tests-external.sh -n spec28-ragas tests/quality/test_ragas_baseline.py`
- **Test currently skips** with a clear reason; remove the `pytest.skip` once the Python/ragas compatibility is addressed
- **Judge LLM**: Ollama `qwen2.5:7b` — same model as the backend; documents self-bias risk (neutral cloud judge: set `RAGAS_JUDGE=openrouter:<model>`)
- **Collection**: `RAGAS_COLLECTION_ID` env var, defaults to NAG corpus

## Ship-gate note

Per FR-018 and spec-28 Assumptions, this baseline is **informational, not a
ship gate** — no score floor blocks v1.0.0. The 20% answer rate is itself the
signal: it surfaces a real quality gap (F1) that a follow-up spec should
investigate. Subsequent runs of the harness compare against this snapshot;
regressions are flagged for review.
