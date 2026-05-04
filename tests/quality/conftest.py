"""pytest fixtures for the RAGAS quality baseline harness — spec-28.

Design principles:
- Boring and explicit: no abstraction, one fixture = one responsibility.
- All ragas/openai/datasets imports are LAZY (inside fixture bodies).
  This allows `python -c "import tests.quality.conftest"` to succeed even
  when the [quality] extras are not installed (e.g. the default CI runner).
- Session dir is hard-coded to 2026-04-24-bug-hunt per session-directory-contract.md.
  Do NOT derive from $(date) — that resolves to today's date and would miss the fixture file.
"""

from __future__ import annotations

import os
from collections import Counter
from pathlib import Path
from typing import Iterator

import httpx
import pytest
import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Hard-coded per Override 3 in the orchestrator's Wave 2 instructions.
SESSION_DIR = Path("docs/E2E/2026-04-24-bug-hunt")
GOLDEN_QA_PATH = SESSION_DIR / "golden-qa.yaml"

# Expected scaffold-reviewed pair distribution per FR-014 + FR-019.
_EXPECTED_SCAFFOLD_DISTRIBUTION: dict[str, int] = {
    "factoid": 10,
    "analytical": 4,
    "follow-up": 3,
}

# Backend base URL — same as used in integration tests.
_BACKEND_BASE_URL = "http://localhost:8000"

# Timeout for a single chat question (analytical questions can take 30 s+).
_REQUEST_TIMEOUT = httpx.Timeout(60.0)


# ---------------------------------------------------------------------------
# Fixture: golden_dataset
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def golden_dataset() -> list[dict]:
    """Load and validate docs/E2E/2026-04-24-bug-hunt/golden-qa.yaml.

    Validates:
    - File exists and is a YAML list.
    - Scaffold-reviewed pairs: exactly 17, distribution 10/4/3 per category.
    - All scaffold-reviewed entries have authored_by == "scaffold-reviewed".
    - All scaffold-reviewed entries have expected_behavior == "answer".
    - follow-up entries reference a valid earlier Q id in the file.

    Raises pytest.fail(...) on any violation so failures are human-readable.
    """
    if not GOLDEN_QA_PATH.exists():
        pytest.fail(
            f"golden-qa.yaml not found at {GOLDEN_QA_PATH}. "
            "Run T034 (scaffold pairs) before executing the quality harness."
        )

    with GOLDEN_QA_PATH.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    if not isinstance(data, list) or len(data) == 0:
        pytest.fail("golden-qa.yaml must be a non-empty YAML list.")

    # --- Scaffold-reviewed subset validation ---
    scaffold_pairs = [d for d in data if d.get("authored_by") == "scaffold-reviewed"]

    if len(scaffold_pairs) != 17:
        pytest.fail(
            f"Expected exactly 17 scaffold-reviewed pairs, found {len(scaffold_pairs)}. "
            f"Total entries in file: {len(data)}."
        )

    scaffold_counts = Counter(d["category"] for d in scaffold_pairs)
    if dict(scaffold_counts) != _EXPECTED_SCAFFOLD_DISTRIBUTION:
        pytest.fail(
            f"Wrong scaffold-reviewed category distribution. "
            f"Expected {_EXPECTED_SCAFFOLD_DISTRIBUTION}, got {dict(scaffold_counts)}."
        )

    # All scaffold pairs must have expected_behavior: answer
    non_answer = [d["id"] for d in scaffold_pairs if d.get("expected_behavior") != "answer"]
    if non_answer:
        pytest.fail(f"Scaffold-reviewed pairs must have expected_behavior='answer'. Violations: {non_answer}.")

    # follow-up pairs must reference a valid earlier Q id
    all_ids = [d["id"] for d in data]
    for pair in scaffold_pairs:
        if pair["category"] == "follow-up":
            ref = pair.get("follow_up_of")
            if ref is None or ref not in all_ids:
                pytest.fail(
                    f"follow-up pair {pair['id']} has invalid follow_up_of={ref!r}. "
                    f"Must reference an existing Q id in the file."
                )
            if all_ids.index(ref) >= all_ids.index(pair["id"]):
                pytest.fail(
                    f"follow-up pair {pair['id']}: follow_up_of={ref!r} must reference "
                    f"an EARLIER Q id (comes before {pair['id']} in the list)."
                )
        else:
            if pair.get("follow_up_of") is not None:
                pytest.fail(
                    f"Non-follow-up pair {pair['id']} must have follow_up_of=null, got {pair['follow_up_of']!r}."
                )

    return data


# ---------------------------------------------------------------------------
# Fixture: backend_client
# ---------------------------------------------------------------------------


@pytest.fixture
def backend_client() -> Iterator[httpx.Client]:
    """Sync httpx Client pointing at http://localhost:8000 with 60 s timeout.

    Analytical questions can take 30 s+ end-to-end on the local GPU stack.

    NOTE: sync (not AsyncClient) deliberately. ragas auto-applies nest_asyncio,
    which patches the asyncio event-loop policy and breaks sniffio's async-library
    detection inside httpx.AsyncClient. Since this test runs queries sequentially
    (no parallelism benefit), sync is the correct choice.
    """
    with httpx.Client(
        base_url=_BACKEND_BASE_URL,
        timeout=_REQUEST_TIMEOUT,
    ) as client:
        yield client


# ---------------------------------------------------------------------------
# Fixture: ragas_metrics
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def ragas_metrics() -> list:
    """Return initialized RAGAS metric instances using the configured judge LLM.

    Metrics returned (in order):
        ContextPrecision, ContextRecall, AnswerRelevancy, Faithfulness.

    Judge LLM configuration (RAGAS_JUDGE env var):
        "local" (default) → Ollama at http://localhost:11434, model from
                             EMBEDINATOR_DEFAULT_LLM_MODEL (default: qwen2.5:7b).
        Any other value   → TODO: implement provider-specific wiring.
                             Falls back to local Ollama with a warning.

    Note: self-bias risk — using the same local model as the backend judge means
    the model evaluates its own answers. Document this risk in quality-metrics.md
    Reproduction section. Use RAGAS_JUDGE=openrouter:<model> for a neutral cloud
    judge in follow-up runs.

    All ragas / langchain imports are lazy so this module can be imported without
    [quality] extras installed (import smoke check must pass).
    """
    # Lazy imports — not available in default install; installed via pip install ragas etc.
    from langchain_ollama import OllamaEmbeddings  # type: ignore[import]
    from ragas.embeddings import LangchainEmbeddingsWrapper  # type: ignore[import]
    from ragas.llms import llm_factory  # type: ignore[import]
    from ragas.metrics import (  # type: ignore[import]
        AnswerRelevancy,
        ContextPrecision,
        ContextRecall,
        Faithfulness,
    )

    judge_spec = os.environ.get("RAGAS_JUDGE", "local")
    ollama_base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    default_model = os.environ.get("EMBEDINATOR_DEFAULT_LLM_MODEL", "qwen2.5:7b")
    embed_model = os.environ.get("EMBEDINATOR_DEFAULT_EMBEDDING_MODEL", "nomic-embed-text")

    if judge_spec != "local":
        import warnings

        warnings.warn(
            f"RAGAS_JUDGE={judge_spec!r} is set but provider-specific wiring is not "
            f"yet implemented. Falling back to local Ollama ({default_model}). "
            f"Implement provider wiring in a follow-up run for a neutral cloud judge.",
            stacklevel=2,
        )

    # llm_factory builds a langchain_openai.ChatOpenAI internally; OPENAI_API_KEY
    # must be set (Ollama ignores the value but the OpenAI SDK requires SOMETHING).
    os.environ.setdefault("OPENAI_API_KEY", "ollama")
    evaluator_llm = llm_factory(
        model=default_model,
        base_url=f"{ollama_base}/v1",
    )

    # AnswerRelevancy needs an embedder; ragas's embedding_factory only supports
    # OpenAI proper, so wire OllamaEmbeddings through LangchainEmbeddingsWrapper.
    evaluator_embeddings = LangchainEmbeddingsWrapper(OllamaEmbeddings(base_url=ollama_base, model=embed_model))

    return [
        ContextPrecision(llm=evaluator_llm),
        ContextRecall(llm=evaluator_llm),
        AnswerRelevancy(llm=evaluator_llm, embeddings=evaluator_embeddings),
        Faithfulness(llm=evaluator_llm),
    ]


# ---------------------------------------------------------------------------
# Fixture: session_id
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def session_id() -> str:
    """Session identifier — matches the docs/E2E/ directory name.

    Hard-coded per session-directory-contract.md and Override 3.
    Format: YYYY-MM-DD-bug-hunt.
    """
    return "2026-04-24-bug-hunt"
